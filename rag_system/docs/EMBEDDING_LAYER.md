# Embedding and Vector Storage Layer

## Overview
Complete implementation of embedding generation and vector storage for the RAG system with production-grade features.

## Architecture

### 1. Embedding Pipeline
```
Document → Chunks → Deduplication → Cache Check → Generate → Store → Pinecone
```

### 2. Components

#### Gemini Embedding Client
- **File**: `app/services/embeddings/gemini_client.py`
- **Features**:
  - Batch processing (100 texts/batch)
  - Exponential backoff retry (3 attempts)
  - Timeout handling (30s default)
  - Task type support (RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY)
  - Latency tracking
  - Comprehensive logging

#### Redis Embedding Cache
- **File**: `app/services/embeddings/embedding_cache.py`
- **Features**:
  - Hash-based deduplication
  - 7-day TTL
  - Batch get/set operations
  - Cache hit rate tracking
  - JSON serialization

#### Embedding Service
- **File**: `app/services/embeddings/embedding_service.py`
- **Features**:
  - Content hash deduplication
  - Cache-first approach
  - Batch embedding generation
  - Progress tracking
  - Error handling with retries

#### Pinecone Vector Database
- **File**: `app/services/vector_store/pinecone_client.py`
- **Features**:
  - Serverless index auto-creation
  - Batch upsert (100 vectors/batch)
  - User-based namespacing
  - Metadata filtering
  - Document deletion
  - Cosine similarity metric

#### Vector Service
- **File**: `app/services/vector_store/vector_service.py`
- **Features**:
  - Chunk to vector conversion
  - Metadata enrichment
  - Batch storage
  - Namespace management

## Processing Flow

### Document Processing Pipeline
```python
UPLOADED → PROCESSING → PARSED → CHUNKED → EMBEDDED → COMPLETED
                                              ↓
                                         (on error)
                                            FAILED
```

### Embedding Generation Flow
1. **Deduplication**: Group chunks by content hash
2. **Cache Lookup**: Check Redis for existing embeddings
3. **Generate**: Call Gemini API for cache misses
4. **Cache Store**: Save new embeddings to Redis
5. **Attach**: Return all chunks with embeddings

### Vector Storage Flow
1. **Convert**: Transform chunks to vector records
2. **Enrich**: Add metadata (document_id, user_id, hierarchy)
3. **Namespace**: Use user_id for multi-tenancy
4. **Upsert**: Batch insert to Pinecone

## Configuration

### Required Environment Variables
```bash
# Gemini AI
GEMINI_API_KEY=your-api-key
GEMINI_MODEL=models/embedding-001
GEMINI_TIMEOUT=30
GEMINI_MAX_RETRIES=3

# Pinecone
PINECONE_API_KEY=your-api-key
PINECONE_ENVIRONMENT=us-west1-gcp
PINECONE_INDEX_NAME=rag-embeddings
PINECONE_DIMENSION=768
PINECONE_CLOUD=gcp
```

## Data Models

### EmbeddedChunk
```python
@dataclass
class EmbeddedChunk:
    chunk: Chunk              # Original chunk
    embedding: List[float]    # 768-dimensional vector
```

### VectorRecord
```python
@dataclass
class VectorRecord:
    id: str                   # document_id#chunk_index
    values: List[float]       # Embedding vector
    metadata: Dict[str, Any]  # Chunk metadata
```

### Vector Metadata
```python
{
    "document_id": "uuid",
    "chunk_index": 0,
    "content": "text",
    "content_hash": "hash",
    "token_count": 500,
    "section_title": "title",
    "page_number": 1,
    "hierarchy": [...]
}
```

## Performance Optimizations

### 1. Deduplication
- Content hash-based deduplication reduces API calls
- Example: 1000 chunks → 850 unique → 15% savings

### 2. Caching
- Redis cache with 7-day TTL
- Reprocessing same document = 0 API calls
- Typical cache hit rate: 40-60% for similar docs

### 3. Batching
- Gemini: 100 texts per batch
- Pinecone: 100 vectors per batch
- Reduces network overhead by ~90%

### 4. Async Operations
- Non-blocking I/O for Redis and database
- Concurrent batch processing
- Parallel cache lookups

## Error Handling

### Retry Strategy
```python
# Gemini API
- Max retries: 3
- Backoff: exponential (2^n seconds)
- Timeout: 30 seconds per request

# Pinecone
- Auto-retry on connection errors
- Batch failure isolation
- Graceful degradation
```

### Failure Modes
1. **Gemini API Failure**: Retries with backoff, fails task on exhaustion
2. **Redis Failure**: Bypasses cache, generates fresh embeddings
3. **Pinecone Failure**: Retries batch, fails task on persistent error
4. **Database Failure**: Rolls back status update, retries entire task

## Monitoring

### Logged Metrics
- Embedding generation time
- Cache hit/miss rates
- Deduplication ratios
- Vector upsert counts
- API latencies
- Error rates

### Example Log Output
```json
{
  "message": "Embedding generation complete",
  "document_id": "123e4567-e89b-12d3-a456-426614174000",
  "total_chunks": 1000,
  "unique_chunks": 850,
  "cached": 400,
  "newly_generated": 450,
  "dedup_ratio": 15.0,
  "cache_hit_rate": 47.06,
  "vectors_stored": 1000
}
```

## Usage Example

### Celery Task Integration
```python
from app.services.embeddings import EmbeddingService, TaskType
from app.services.vector_store import VectorService

# Generate embeddings
embedding_service = EmbeddingService()
embedded_chunks = await embedding_service.embed_chunks(
    chunks=all_chunks,
    task_type=TaskType.RETRIEVAL_DOCUMENT,
)

# Store in Pinecone
vector_service = VectorService()
vectors_stored = vector_service.store_document_chunks(
    embedded_chunks=embedded_chunks,
    document_id=document_id,
    user_id=user_id,
)
```

## Testing

### Unit Tests
```bash
# Test embedding generation
pytest tests/services/test_embeddings.py

# Test vector storage
pytest tests/services/test_vector_store.py

# Test caching
pytest tests/services/test_embedding_cache.py
```

### Integration Tests
```bash
# End-to-end document processing
pytest tests/integration/test_document_pipeline.py
```

## Security

### API Key Management
- Store keys in environment variables
- Never commit to version control
- Rotate keys periodically

### Multi-tenancy
- User-based namespacing in Pinecone
- Metadata filtering for access control
- Document ID tracking for deletion

## Scalability

### Horizontal Scaling
- Celery workers: Scale to N workers
- Redis: Cluster mode for high throughput
- Pinecone: Serverless auto-scales

### Cost Optimization
- Cache hit rate directly reduces API costs
- Deduplication reduces vector storage
- Batch processing reduces network overhead

### Capacity Planning
- Gemini: 1500 requests/minute (free tier)
- Pinecone: Unlimited vectors (serverless)
- Redis: 10GB cache = ~13M embeddings

## Future Enhancements

### Planned Features
1. **Hybrid Search**: Combine dense + sparse retrieval
2. **Reranking**: Cross-encoder for result refinement
3. **Async Vector Updates**: Background index optimization
4. **Embedding Model Versioning**: A/B test different models
5. **Query Analytics**: Track popular queries and cache results

### Optimization Opportunities
1. **Embedding Quantization**: Reduce vector size (768 → 256 dims)
2. **Approximate NN**: HNSW for faster search
3. **Metadata Compression**: Reduce storage costs
4. **Smart Caching**: LRU eviction for hot embeddings

## Troubleshooting

### Common Issues

#### 1. Gemini API Rate Limits
**Symptom**: `ResourceExhausted` errors
**Solution**: Implement token bucket rate limiter

#### 2. Pinecone Index Not Ready
**Symptom**: `IndexNotFoundException`
**Solution**: Increase wait time after index creation (5s → 30s)

#### 3. Redis Connection Timeout
**Symptom**: Cache misses, slow processing
**Solution**: Check Redis connection pool settings

#### 4. Out of Memory
**Symptom**: Worker crashes during large document
**Solution**: Reduce batch size or add pagination

## Dependencies

```txt
google-generativeai==0.3.2
pinecone-client==3.0.0
redis==5.0.1
tiktoken==0.5.2
```

## References

- [Gemini Embedding API](https://ai.google.dev/tutorials/embeddings)
- [Pinecone Serverless](https://docs.pinecone.io/docs/serverless)
- [Redis Caching Best Practices](https://redis.io/docs/manual/patterns/)
