# Hybrid Retrieval Engine

## Overview
Production-grade hybrid retrieval system combining dense vector search (Pinecone) with sparse BM25 search (PostgreSQL) for optimal relevance and coverage.

## Architecture

### Retrieval Pipeline
```
User Query
    ↓
1. Query Classification (factual, comparative, temporal, conversational, multi-hop)
    ↓
2. Query Transformation (normalization + embedding with caching)
    ↓
3. Parallel Retrieval
    ├─→ Pinecone Vector Search (top 50)
    └─→ PostgreSQL BM25 Search (top 20)
    ↓
4. Result Merging & Deduplication
    ↓
5. Score Normalization
    ↓
6. Weighted Score Combination (0.7*vector + 0.2*bm25 + 0.1*recency)
    ↓
7. MMR Diversification (λ=0.7)
    ↓
8. Return Top K Results (default 5)
```

## Components

### 1. Query Classifier
**File**: `app/services/retrieval/query_classifier.py`

Classifies queries into types to optimize retrieval strategy:

- **FACTUAL**: Direct fact lookup (who, what, when, where)
  - Example: "What is the capital of France?"
  - Strategy: High relevance, low diversity (λ=0.5)
  
- **COMPARATIVE**: Comparison queries (vs, compare, difference)
  - Example: "Compare Python vs JavaScript"
  - Strategy: High diversity for balanced comparison (λ=0.7)
  
- **TEMPORAL**: Time-based queries (recent, before, after)
  - Example: "What are the latest updates?"
  - Strategy: High recency weight (0.3)
  
- **CONVERSATIONAL**: Follow-up or contextual queries
  - Example: "Tell me more about it"
  - Strategy: High semantic similarity (vector weight 0.8)
  
- **MULTI_HOP**: Complex multi-faceted queries
  - Example: "What caused X and how did it affect Y?"
  - Strategy: High diversity, more results (top_k=10, λ=0.8)

**Pattern-based Classification**:
```python
FACTUAL_PATTERNS = [
    r'\b(what|who|when|where|which)\b',
    r'\b(define|definition|explain)\b',
]

COMPARATIVE_PATTERNS = [
    r'\b(vs|versus|compare|difference)\b',
    r'\b(better|worse|more|less)\s+than\b',
]
```

### 2. Query Transformer
**File**: `app/services/retrieval/query_transformer.py`

Transforms queries for optimal retrieval:

**Features**:
- Query normalization (whitespace, lowercasing)
- Term extraction for BM25
- Embedding generation with Redis caching
- Uses `TaskType.RETRIEVAL_QUERY` for Gemini

**Output**:
```python
{
    "original_query": str,
    "normalized_query": str,
    "embedding": List[float],  # 768-dim vector
    "terms": List[str],
}
```

### 3. BM25 Service
**File**: `app/services/retrieval/bm25_service.py`

PostgreSQL-based BM25 full-text search:

**Features**:
- `tsvector` with weighted fields (section_title: A, content: B)
- GIN index for fast retrieval
- `ts_rank_cd` for BM25-like scoring
- User-based filtering (mandatory)
- Document-based filtering (optional)

**SQL Query**:
```sql
SELECT 
    id, document_id, content, chunk_index,
    ts_rank_cd(
        content_tsvector, 
        plainto_tsquery('english', :query),
        1  -- Normalize by document length
    ) AS bm25_score
FROM chunks
WHERE 
    user_id = :user_id
    AND content_tsvector @@ plainto_tsquery('english', :query)
ORDER BY bm25_score DESC
LIMIT :top_k
```

### 4. MMR Algorithm
**File**: `app/services/retrieval/mmr.py`

Maximal Marginal Relevance for result diversification:

**Formula**:
```
MMR = λ * Sim(D, Q) - (1-λ) * max[Sim(D, d) for d in Selected]
```

**Parameters**:
- `λ = 0.7` (default): Balance relevance and diversity
- `λ = 1.0`: Pure relevance (no diversity)
- `λ = 0.0`: Pure diversity (no relevance)

**Algorithm**:
1. Select highest-scoring document first
2. For each remaining position:
   - Calculate relevance to query
   - Calculate max similarity to already selected documents
   - Compute MMR score
   - Select document with highest MMR score

**Diversity Metrics**:
```python
diversity_score = 1 - avg_pairwise_similarity
# Score near 1: high diversity
# Score near 0: low diversity
```

### 5. Scoring Service
**File**: `app/services/retrieval/scoring.py`

Score normalization and combination:

**Normalization Methods**:
- **Min-Max**: `(x - min) / (max - min)` → [0, 1]
- **Z-Score + Sigmoid**: `sigmoid((x - μ) / σ)` → [0, 1]

**Score Combination**:
```python
final_score = (
    0.7 * normalized_vector_score +
    0.2 * normalized_bm25_score +
    0.1 * normalized_recency_score
)
```

**Recency Scoring**:
```python
# Exponential decay
recency_score = exp(-age_in_days / decay_days)
# decay_days = 365 (default)
# After 1 year: score ≈ 0.37
# After 2 years: score ≈ 0.14
```

### 6. Hybrid Retriever
**File**: `app/services/retrieval/hybrid_retriever.py`

Orchestrates the complete retrieval pipeline:

**Key Methods**:
```python
async def retrieve(
    query: str,
    user_id: str,
    db: AsyncSession,
    top_k: int = 5,
    document_id: Optional[UUID] = None,
    vector_top_k: int = 50,
    bm25_top_k: int = 20,
    apply_mmr: bool = True,
) -> List[RetrievalResult]
```

**Result Object**:
```python
@dataclass
class RetrievalResult:
    chunk_id: UUID
    document_id: UUID
    content: str
    score: float  # Combined score
    vector_score: float  # Normalized
    bm25_score: float  # Normalized
    recency_score: float  # Normalized
    chunk_index: int
    section_title: Optional[str]
    page_number: Optional[int]
    metadata: Optional[Dict[str, Any]]
```

## Database Schema

### Chunk Table
```sql
CREATE TABLE chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    token_count INTEGER NOT NULL,
    section_title VARCHAR(512),
    page_number INTEGER,
    hierarchy TEXT,  -- JSON string
    content_tsvector TSVECTOR,  -- Full-text search vector
    created_at TIMESTAMP NOT NULL,
    
    -- Indexes
    CONSTRAINT chunks_document_index UNIQUE (document_id, chunk_index)
);

CREATE INDEX ix_chunks_user_document ON chunks(user_id, document_id);
CREATE INDEX ix_chunks_content_tsvector ON chunks USING GIN(content_tsvector);
CREATE INDEX ix_chunks_content_hash ON chunks(content_hash);
```

### TSVector Generation
```sql
UPDATE chunks
SET content_tsvector = 
    setweight(to_tsvector('english', COALESCE(section_title, '')), 'A') ||
    setweight(to_tsvector('english', content), 'B')
WHERE document_id = :document_id;
```

## Retrieval Strategies by Query Type

| Query Type | Vector Weight | BM25 Weight | Recency Weight | Top K | MMR λ |
|------------|---------------|-------------|----------------|-------|-------|
| FACTUAL | 0.7 | 0.2 | 0.1 | 5 | 0.5 |
| COMPARATIVE | 0.6 | 0.3 | 0.1 | 8 | 0.7 |
| TEMPORAL | 0.5 | 0.2 | 0.3 | 5 | 0.6 |
| CONVERSATIONAL | 0.8 | 0.1 | 0.1 | 5 | 0.5 |
| MULTI_HOP | 0.6 | 0.3 | 0.1 | 10 | 0.8 |

## Performance Optimizations

### 1. Parallel Retrieval
```python
# Execute vector and BM25 searches concurrently
vector_task = self._vector_search(...)
bm25_task = BM25Service.search(...)

vector_results, bm25_results = await asyncio.gather(
    vector_task,
    bm25_task,
)
```

### 2. Query Embedding Caching
- Redis cache with SHA256 hash key
- Avoids redundant API calls for identical queries
- 7-day TTL

### 3. Database Optimizations
- GIN index on `content_tsvector` for fast full-text search
- Composite indexes for user/document filtering
- Query result limit at database level

### 4. Result Deduplication
- Merge by `chunk_id` to avoid duplicates
- Combine scores from both retrievers
- Single database lookup for metadata

## Usage Examples

### Basic Retrieval
```python
from app.services.retrieval import HybridRetriever

retriever = HybridRetriever()

results = await retriever.retrieve(
    query="What is machine learning?",
    user_id="user_123",
    db=db_session,
    top_k=5,
)

for result in results:
    print(f"Score: {result.score:.4f}")
    print(f"Content: {result.content[:200]}...")
    print(f"Vector: {result.vector_score:.4f}, BM25: {result.bm25_score:.4f}")
```

### Document-Scoped Retrieval
```python
results = await retriever.retrieve(
    query="Explain the methodology",
    user_id="user_123",
    db=db_session,
    top_k=5,
    document_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
)
```

### Disable MMR
```python
results = await retriever.retrieve(
    query="Latest updates",
    user_id="user_123",
    db=db_session,
    top_k=10,
    apply_mmr=False,  # Return top 10 by combined score
)
```

## Monitoring Metrics

### Logged Data
```json
{
  "query_preview": "What is...",
  "query_type": "factual",
  "user_id": "user_123",
  "vector_results": 50,
  "bm25_results": 20,
  "merged_results": 65,
  "final_results": 5,
  "top_score": 0.8542,
  "retrieval_time_ms": 234
}
```

### Key Metrics
- Query classification accuracy
- Cache hit rate for query embeddings
- Vector search latency
- BM25 search latency
- Result overlap (vector ∩ BM25)
- Diversity score of final results

## Error Handling

### Empty Results
- Returns empty list with warning log
- No exception raised

### Database Errors
- Catches and logs SQL errors
- Re-raises with context

### Vector Search Failures
- Falls back to BM25-only retrieval
- Logs error for monitoring

### Invalid Query
- Returns empty list for empty/whitespace queries
- Logs warning

## Testing

### Unit Tests
```bash
# Test query classification
pytest tests/services/retrieval/test_query_classifier.py

# Test BM25 search
pytest tests/services/retrieval/test_bm25_service.py

# Test MMR algorithm
pytest tests/services/retrieval/test_mmr.py

# Test scoring
pytest tests/services/retrieval/test_scoring.py
```

### Integration Tests
```bash
# End-to-end hybrid retrieval
pytest tests/integration/test_hybrid_retrieval.py
```

## Future Enhancements

### Planned Features
1. **Query Expansion**: Synonym expansion, acronym resolution
2. **Cross-Encoder Reranking**: BERT-based reranking after retrieval
3. **Learning to Rank**: Train model on click data
4. **Semantic Caching**: Cache results for semantically similar queries
5. **Federated Search**: Multi-index retrieval across tenants

### Optimization Opportunities
1. **HNSW Index**: Faster approximate nearest neighbor search
2. **Quantization**: Reduce vector dimensions (768 → 256)
3. **Hybrid Index**: Combined inverted + vector index
4. **Query Routing**: Route simple queries to BM25 only
5. **Adaptive Weights**: Learn optimal weights per query type

## Troubleshooting

### Low Recall
**Symptom**: Relevant documents not retrieved
**Solutions**:
- Increase `vector_top_k` and `bm25_top_k`
- Lower MMR λ for more diversity
- Check if documents are indexed

### Low Precision
**Symptom**: Irrelevant results in top positions
**Solutions**:
- Increase vector weight
- Apply stricter metadata filters
- Increase MMR λ for more relevance

### Slow Queries
**Symptom**: Retrieval takes > 1 second
**Solutions**:
- Check GIN index on `content_tsvector`
- Reduce `vector_top_k` and `bm25_top_k`
- Enable query result caching
- Check Pinecone pod type

### Query Embedding Failures
**Symptom**: Gemini API errors
**Solutions**:
- Check API key validity
- Verify rate limits
- Fallback to BM25-only retrieval

## Dependencies

```txt
numpy==1.26.3
google-generativeai==0.3.2
pinecone-client==3.0.0
sqlalchemy==2.0.25
asyncpg==0.29.0
redis==5.0.1
```

## References

- [BM25 Algorithm](https://en.wikipedia.org/wiki/Okapi_BM25)
- [MMR for Diversity](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf)
- [PostgreSQL Full-Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [Hybrid Search Best Practices](https://www.pinecone.io/learn/hybrid-search-intro/)
