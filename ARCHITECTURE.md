# System Architecture Documentation

> **RAG System** — Production-grade Retrieval-Augmented Generation platform  
> Stack: Next.js · FastAPI · PostgreSQL · Redis · Pinecone · Gemini AI · Celery

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Backend Architecture](#2-backend-architecture)
3. [Frontend Architecture](#3-frontend-architecture)
4. [RAG Ingestion Pipeline](#4-rag-ingestion-pipeline)
5. [Parsing and Chunking Flow](#5-parsing-and-chunking-flow)
6. [Embedding and Vector Storage](#6-embedding-and-vector-storage)
7. [Hybrid Retrieval Pipeline](#7-hybrid-retrieval-pipeline)
8. [Prompt Building and Generation](#8-prompt-building-and-generation)
9. [Chat Orchestration](#9-chat-orchestration)
10. [Monitoring and Feedback System](#10-monitoring-and-feedback-system)

---

## 1. System Overview

The RAG System is a full-stack, production-ready Retrieval-Augmented Generation platform. Users upload documents through a Next.js frontend; documents are asynchronously processed by a Celery worker pipeline (parse → chunk → embed → index). At query time, a FastAPI backend orchestrates hybrid retrieval (dense vector search + BM25 sparse search), prompt construction, and Gemini LLM generation, all guarded by a multi-layer protection system.

```mermaid
graph TB
    subgraph Client["Client Layer (Next.js)"]
        UI[Dashboard / Chat / Documents]
        CTX[AppContext<br/>userId · documents · selectedDoc]
        HOOKS[Hooks: useChat · useDocuments · useHealth]
    end

    subgraph Gateway["API Gateway (FastAPI :8000)"]
        CHAT_API[POST /api/v1/chat]
        DOC_API[POST /documents/upload<br/>GET /documents]
        HEALTH_API[GET /health]
        MW[Middleware: CORS · RequestID · Logging]
    end

    subgraph Processing["Async Processing (Celery Worker)"]
        PARSE[Parser Factory<br/>PDF · DOCX · PPTX · TXT]
        CHUNK[Semantic + Hierarchical Chunker]
        EMBED[Gemini Embedding Service]
        STORE[Vector + DB Store]
    end

    subgraph RAGPipeline["RAG Query Pipeline"]
        PROTECT[Protection Layer<br/>RateLimit · Quota · CircuitBreaker · LoadShedder]
        RETRIEVE[Hybrid Retriever<br/>Pinecone + BM25]
        PROMPT[Prompt Builder<br/>Context Optimizer · Token Budget]
        GENERATE[Gemini Generator<br/>gemini-2.0-flash]
        VALIDATE[Answer Validator<br/>Citations · Confidence · Hallucination]
    end

    subgraph DataStores["Data Stores"]
        PG[(PostgreSQL<br/>Documents · Chunks · Interactions · Feedback)]
        REDIS[(Redis<br/>Cache · Rate Limits · Celery Broker)]
        PINE[(Pinecone<br/>Dense Vector Index)]
        FS[(Local Storage<br/>Raw Files)]
    end

    UI --> CTX --> HOOKS --> Gateway
    Gateway --> MW
    CHAT_API --> PROTECT --> RETRIEVE --> PROMPT --> GENERATE --> VALIDATE
    DOC_API --> Processing
    Processing --> DataStores
    RETRIEVE --> PINE
    RETRIEVE --> PG
    GENERATE --> REDIS
    Gateway --> PG
    REDIS --> Processing
```

---

## 2. Backend Architecture

The backend is a **FastAPI** application with async SQLAlchemy for PostgreSQL, an async Redis client, and Celery for background task execution. All configuration is managed via `pydantic-settings` and environment variables.

### Infrastructure Stack

| Component | Technology | Purpose |
|---|---|---|
| Web Framework | FastAPI 0.110+ | Async REST API |
| Database | PostgreSQL 15 | Relational data, BM25 full-text search |
| Cache / Broker | Redis 7 | Embedding cache, rate limits, Celery broker/backend |
| Vector DB | Pinecone | Dense vector similarity search |
| Task Queue | Celery | Async document processing |
| LLM | Gemini 2.0 Flash | Answer generation |
| Embeddings | Gemini `embedding-001` | 3072-dim dense vectors |
| Container | Docker Compose | Multi-service orchestration |

```mermaid
graph TB
    subgraph Docker["Docker Compose Network (rag_network)"]
        subgraph FastAPI["FastAPI Container (:8000)"]
            APP[FastAPI App<br/>lifespan: init DB + Redis]
            ROUTES[Routes<br/>/chat · /documents · /health]
            SERVICES[Service Layer<br/>orchestration · retrieval · generation<br/>protection · monitoring]
            APP --> ROUTES --> SERVICES
        end

        subgraph CeleryW["Celery Worker Container"]
            CWORKER[Celery Worker<br/>process_document task]
            CBEAT[Celery Beat<br/>scheduled tasks]
        end

        subgraph PGCont["PostgreSQL Container (:5432)"]
            PGDB[(rag_database)]
        end

        subgraph RedisCont["Redis Container (:6379)"]
            R0[DB 0: App Cache]
            R1[DB 1: Celery Broker]
            R2[DB 2: Celery Results]
        end
    end

    subgraph External["External Services"]
        GEMINI_API[Google Gemini API<br/>embedding-001 · 2.0-flash]
        PINE_API[Pinecone API<br/>rag-embeddings index]
    end

    FastAPI --> PGCont
    FastAPI --> RedisCont
    CeleryW --> PGCont
    CeleryW --> RedisCont
    CeleryW --> GEMINI_API
    CeleryW --> PINE_API
    FastAPI --> GEMINI_API
    FastAPI --> PINE_API
```

### API Routes

```mermaid
graph LR
    subgraph ChatRoutes["Chat Routes (/api/v1/chat)"]
        C1[POST / — RAG chat query]
        C2[POST /feedback — Submit rating]
        C3[GET /interactions — History]
    end

    subgraph DocRoutes["Document Routes (/documents)"]
        D1[POST /upload — Upload file]
        D2[GET / — List documents]
        D3[GET /{id} — Get document]
        D4[DELETE /{id} — Delete document]
    end

    subgraph HealthRoutes["Health Routes (/health)"]
        H1[GET / — System health]
        H2[GET /services — Service statuses]
    end

    subgraph Middleware["Middleware Stack"]
        MW1[CORSMiddleware<br/>allow_origins from config]
        MW2[RequestIDMiddleware<br/>X-Request-ID header]
        MW3[Exception Handlers<br/>BaseAPIException · HTTP · Validation]
    end
```

### Database Schema

```mermaid
erDiagram
    DOCUMENTS {
        uuid id PK
        string user_id
        string filename
        string storage_path
        string document_type
        int version
        bool is_active
        enum processing_status
        datetime created_at
        datetime updated_at
    }

    DOCUMENT_CHUNKS {
        uuid id PK
        uuid document_id FK
        string user_id
        text content
        string content_hash
        int chunk_index
        int token_count
        string parent_section_id
        string section_title
        int page_number
        tsvector search_vector
        json metadata
        datetime created_at
    }

    CHAT_INTERACTIONS {
        uuid id PK
        string user_id
        uuid document_id FK
        text query
        text answer
        json citations
        float confidence_score
        int prompt_tokens
        int completion_tokens
        float latency_ms
        float cost_usd
        string model
        datetime created_at
    }

    CHAT_FEEDBACK {
        uuid id PK
        uuid interaction_id FK
        int rating
        text comment
        datetime created_at
    }

    DOCUMENTS ||--o{ DOCUMENT_CHUNKS : "has"
    DOCUMENTS ||--o{ CHAT_INTERACTIONS : "queried in"
    CHAT_INTERACTIONS ||--o| CHAT_FEEDBACK : "receives"
```

---

## 3. Frontend Architecture

The frontend is a **Next.js 14** App Router application using CSS Modules for styling and React Context for global state. There is no Redux — all state is held in `AppContext` and local component state via custom hooks.

```mermaid
graph TB
    subgraph AppShell["App Shell (layout.js)"]
        PROVIDERS[Providers<br/>AppProvider · ThemeProvider]
        SIDEBAR[Sidebar<br/>Navigation links]
        TOPBAR[Topbar<br/>Theme toggle · User ID]
        CONTENT[Page Content Slot]
    end

    subgraph Pages["Pages (App Router)"]
        DASH[/ — Dashboard<br/>Stats · Quick links]
        CHATPAGE[/chat — Chat<br/>Message thread · Source panel]
        DOCPAGE[/documents — Documents<br/>Upload · Status cards]
        HEALTHPAGE[/health — Health<br/>Service grid · Metrics]
    end

    subgraph StateLayer["State Layer"]
        APPCTX[AppContext<br/>userId · documents · selectedDocumentId<br/>addDocument · updateDocument]
        UC[useChat<br/>messages · isLoading · sendMessage · submitFeedback]
        UD[useDocuments<br/>upload · poll · delete]
        UH[useHealth<br/>health data · isHealthy]
        UT[useTheme<br/>theme · toggleTheme]
    end

    subgraph APILib["API Library"]
        CLI[client.js<br/>apiFetch wrapper]
        CHATAPI[chat.js<br/>sendChat · submitFeedback]
        DOCAPI[documents.js<br/>uploadDocument · getDocument · deleteDocument]
        HAPI[health.js<br/>getHealth]
    end

    subgraph ChatComponents["Chat Components"]
        CW[ChatWindow<br/>message list · auto-scroll]
        CI[ChatInput<br/>query input · doc selector · submit]
        MB[MessageBubble<br/>user/assistant · citations · confidence]
        DS[DocumentSelector<br/>dropdown · filter completed]
        FM[FeedbackModal<br/>1-5 star rating · comment]
        SP[SourcePanel<br/>retrieved chunks · scores]
    end

    subgraph DocComponents["Document Components"]
        DC[DocumentCard<br/>status badge · actions]
        DZ[DropZone<br/>drag & drop · file picker]
        PS[ProcessingStatus<br/>progress indicator · polling]
    end

    PROVIDERS --> APPCTX
    Pages --> StateLayer
    StateLayer --> APILib
    APILib --> CLI
    CHATPAGE --> ChatComponents
    DOCPAGE --> DocComponents
```

### Data Flow: Chat

```mermaid
sequenceDiagram
    participant User
    participant ChatInput
    participant useChat
    participant chat.js API
    participant Backend

    User->>ChatInput: Type query, select document, submit
    ChatInput->>useChat: sendMessage({ query, userId, documentId, topK })
    useChat->>useChat: Optimistically append user message
    useChat->>chat.js API: sendChat(payload)
    chat.js API->>Backend: POST /api/v1/chat
    Backend-->>chat.js API: ChatResponse { answer, citations, sources, confidence_score, ... }
    chat.js API-->>useChat: ChatResponse
    useChat->>useChat: Append assistant message with all metadata
    useChat-->>ChatInput: isLoading = false
    ChatInput-->>User: Display MessageBubble + SourcePanel
    User->>FeedbackModal: Click thumbs up/down
    FeedbackModal->>useChat: submitFeedback({ interactionId, rating, comment })
    useChat->>chat.js API: submitFeedback(payload)
    chat.js API->>Backend: POST /api/v1/chat/feedback
```

---

## 4. RAG Ingestion Pipeline

Documents uploaded through the API are stored, registered in PostgreSQL, and then processed asynchronously by a Celery worker that executes a six-stage pipeline. Status transitions are tracked throughout.

```mermaid
flowchart TD
    A([User uploads file via POST /documents/upload]) --> B

    subgraph Validation["IngestionManager — Validation"]
        B[Validate file extension<br/>.pdf · .docx · .pptx · .txt]
        B --> C[Validate file size ≤ 25 MB]
        C --> D[Generate document UUID]
    end

    D --> E

    subgraph Storage["Storage"]
        E[Save binary to local storage<br/>storage/{user_id}/{doc_id}/{filename}]
        E --> F[Create Document record in PostgreSQL<br/>status = UPLOADED]
    end

    F --> G[Return DocumentUploadResponse to client]
    F --> H

    subgraph CeleryTask["Celery Task: process_document<br/>max_retries=3 · exponential backoff: 1s→2s→4s→8s"]
        H[Set status = PROCESSING]
        H --> I[Load file from storage path]
        I --> J

        subgraph Parsing["Parsing"]
            J[ParserFactory.get_parser document_type]
            J --> K[Parse document → ParsedDocument<br/>sections · metadata]
            K --> L[Normalizer: clean whitespace, fix encoding]
        end

        L --> M[Set status = PARSED]
        M --> N

        subgraph Chunking["Chunking"]
            N[SemanticChunker.chunk_document<br/>max_tokens=500 · overlap=100]
            N --> O[HierarchicalChunker: map section hierarchy<br/>Level 0: Doc → Level 1: Section → Level 2: Chunk]
            O --> P[Generate content_hash per chunk]
        end

        P --> Q[Set status = CHUNKED]
        Q --> R

        subgraph Embedding["Embedding"]
            R[EmbeddingService.embed_chunks]
            R --> S{Cache hit<br/>in Redis?}
            S -- Yes --> T[Reuse cached embedding]
            S -- No --> U[Gemini embedding-001 API<br/>3072-dim vector]
            U --> V[Cache in Redis]
            T --> W[Attach embedding to chunk]
            V --> W
        end

        W --> X[Set status = EMBEDDED]
        X --> Y

        subgraph Indexing["Indexing"]
            Y[VectorService.store_document_chunks<br/>Upsert to Pinecone namespace=user_id]
            Y --> Z[ChunkService.bulk_create_chunks<br/>Insert into PostgreSQL with TSVECTOR index]
        end

        Z --> AA[Set status = COMPLETED]
    end

    AA --> AB([Document ready for retrieval])

    classDef status fill:#2d6a4f,color:#fff
    class H,M,Q,X,AA status
```

---

## 5. Parsing and Chunking Flow

### Parser Factory

Four format-specific parsers are dispatched by `ParserFactory` based on file extension. Each parser produces a `ParsedDocument` with a list of `ParsedSection` objects.

```mermaid
graph TD
    PF[ParserFactory.get_parser extension]

    PF --> PDF[PDFParser<br/>pypdf / pdfplumber<br/>extracts pages → sections<br/>preserves page numbers]
    PF --> DOCX[DocxParser<br/>python-docx<br/>maps headings → sections<br/>preserves section titles]
    PF --> PPTX[PPTXParser<br/>python-pptx<br/>maps slides → sections<br/>title + body text]
    PF --> TXT[TextParser<br/>UTF-8 / fallback encoding<br/>paragraph splitting]

    PDF --> NORM
    DOCX --> NORM
    PPTX --> NORM
    TXT --> NORM

    NORM[Normalizer<br/>strip extra whitespace<br/>fix encoding artefacts<br/>remove null bytes]

    NORM --> PD[ParsedDocument<br/>document_id · sections[] · metadata]
```

### Chunking Strategy

```mermaid
flowchart LR
    PD[ParsedDocument<br/>sections] --> SC

    subgraph SemanticChunker["SemanticChunker (max_tokens=500, overlap=100)"]
        SC[Iterate sections]
        SC --> SMALL{section tokens\n< min_chunk_tokens\n= 50?}
        SMALL -- Yes --> MERGE[Merge with next section]
        SMALL -- No --> LARGE{section tokens\n> max_tokens?}
        LARGE -- Yes --> SPLIT[Split with overlap window<br/>overlap = 100 tokens]
        LARGE -- No --> KEEP[Keep as single chunk]
        MERGE --> CHUNK
        SPLIT --> CHUNK
        KEEP --> CHUNK
        CHUNK[Assign chunk_index<br/>copy section metadata<br/>compute content_hash]
    end

    CHUNK --> HC

    subgraph HierarchicalChunker["HierarchicalChunker"]
        HC[Map section_id → ParsedSection<br/>parent layer]
        HC --> GM[Group chunks by parent_section_id<br/>child layer]
    end

    GM --> CD[ChunkedDocument<br/>chunks[] with parent_section_id links]
```

---

## 6. Embedding and Vector Storage

### Embedding Pipeline

```mermaid
flowchart TD
    CHUNKS[List of Chunk objects] --> ES

    subgraph EmbeddingService["EmbeddingService"]
        ES[Deduplicate by content_hash]
        ES --> BATCH[Split into batches]
        BATCH --> CCHK{Redis cache\nhit per hash?}
        CCHK -- Hit --> HIT[Retrieve cached vector]
        CCHK -- Miss --> GCALL[GeminiEmbeddingClient.embed_batch<br/>task_type = RETRIEVAL_DOCUMENT]
        GCALL --> RETRY[Retry: 1s → 2s → 4s on rate limit / timeout]
        RETRY --> CACHE[Store vector in Redis<br/>key: embedding:{content_hash}]
        HIT --> ATTACH
        CACHE --> ATTACH
        ATTACH[Attach embedding to EmbeddedChunk]
    end

    ATTACH --> VS

    subgraph VectorService["VectorService → PineconeClient"]
        VS[Build VectorRecord per chunk<br/>id · values · metadata]
        VS --> META["Metadata: document_id · chunk_index\nsection_title · page_number\nuser_id · filename"]
        META --> UP[Pinecone upsert batch<br/>namespace = user_id]
    end

    UP --> PGSTORE

    subgraph ChunkService["ChunkService → PostgreSQL"]
        PGSTORE[bulk_create_chunks<br/>INSERT INTO document_chunks<br/>with TSVECTOR search_vector]
    end

    PGSTORE --> IDX[(Pinecone Index<br/>3072-dim · cosine similarity<br/>+ PostgreSQL tsvector index)]
```

### Pinecone Architecture

```mermaid
graph LR
    subgraph PineconeIndex["Pinecone Index: rag-embeddings"]
        subgraph NS1["Namespace: user_id_A"]
            V1[chunk_id_1<br/>3072-dim vector]
            V2[chunk_id_2<br/>3072-dim vector]
        end
        subgraph NS2["Namespace: user_id_B"]
            V3[chunk_id_3<br/>3072-dim vector]
        end
    end

    QE[Query Embedding<br/>task_type = RETRIEVAL_QUERY] -->|cosine sim top-50| NS1
    NS1 -->|VectorSearchResult| MERGE[Merge with BM25 results]
```

---

## 7. Hybrid Retrieval Pipeline

The retrieval engine combines **dense vector search** (Pinecone, semantic similarity) with **sparse BM25 search** (PostgreSQL `tsvector`, keyword matching) to maximize both recall and precision. Results are merged, scored, and diversified using **MMR**.

```mermaid
flowchart TD
    Q[User Query] --> QC

    subgraph Classification["Query Classification"]
        QC[QueryClassifier<br/>pattern matching on query text]
        QC --> QT_TYPE{Query Type}
        QT_TYPE --> FACTUAL[FACTUAL<br/>λ=0.5 · standard weights]
        QT_TYPE --> COMPARE[COMPARATIVE<br/>λ=0.7 · diversity boost]
        QT_TYPE --> TEMPORAL[TEMPORAL<br/>recency_weight=0.3]
        QT_TYPE --> CONVO[CONVERSATIONAL<br/>vector_weight=0.8]
        QT_TYPE --> MULTIHOP[MULTI_HOP<br/>λ=0.8 · top_k=10]
    end

    QC --> QTR

    subgraph Transformation["Query Transformation"]
        QTR[QueryTransformer.transform]
        QTR --> NORM2[Normalize: lowercase · strip punct]
        NORM2 --> TERMS[Extract search terms<br/>remove stopwords]
        TERMS --> QEMB{Redis cache<br/>for query?}
        QEMB -- Hit --> QVEC[Cached query vector]
        QEMB -- Miss --> GEMBED[Gemini embed<br/>task_type = RETRIEVAL_QUERY]
        GEMBED --> QVEC
    end

    QVEC --> PARALLEL

    subgraph ParallelRetrieval["Parallel Retrieval (asyncio)"]
        PARALLEL{Dispatch in parallel}
        PARALLEL --> VEC[Pinecone Vector Search<br/>top_k=50 by cosine sim<br/>filter by namespace=user_id]
        PARALLEL --> BM25[PostgreSQL BM25 Search<br/>ts_rank_cd against tsvector<br/>top_k=20]
    end

    VEC --> MERGE2
    BM25 --> MERGE2

    subgraph Scoring["Score Normalization & Combination"]
        MERGE2[Merge · Deduplicate by chunk_id]
        MERGE2 --> NORM_V[Min-max normalize vector scores]
        MERGE2 --> NORM_B[Min-max normalize BM25 scores]
        MERGE2 --> RECENCY[Compute recency score<br/>from created_at timestamp]
        NORM_V --> COMBINE
        NORM_B --> COMBINE
        RECENCY --> COMBINE
        COMBINE["Weighted combination\n0.7 × vector + 0.2 × BM25 + 0.1 × recency"]
    end

    COMBINE --> MMR_DIV

    subgraph MMR["MMR Diversification"]
        MMR_DIV[MMR.rerank<br/>λ = query-type-dependent]
        MMR_DIV --> SELECT[Iteratively select:\nmax λ×Sim_query − 1−λ×max_Sim_selected]
    end

    SELECT --> TOPK[Return top_k RetrievalResult objects<br/>default k = 5]

    TOPK --> PROMPT_PHASE([→ Prompt Building])
```

---

## 8. Prompt Building and Generation

### Prompt Construction

```mermaid
flowchart TD
    RESULTS[List of RetrievalResult] --> CTX_OPT

    subgraph ContextOptimizer["ContextOptimizer"]
        CTX_OPT[Rank chunks by score]
        CTX_OPT --> BUDGET[TokenBudgetManager<br/>MODEL_MAX_TOKENS = 1,048,576<br/>MAX_OUTPUT_TOKENS = 8,192]
        BUDGET --> TRIM[Fit context within budget<br/>reserve space for system + query + output]
        TRIM --> SELECTED[Selected chunks with token allocation]
    end

    SELECTED --> SF

    subgraph SourceFormatter["SourceFormatter"]
        SF[Format each chunk as:\n[Source N]\nTitle: section_title\nPage: page_number\nContent: ...]
        SF --> MAP[Build source_mapping Dict<br/>N → {document_id, chunk_id, section_title, ...}]
    end

    MAP --> PB

    subgraph PromptBuilder["PromptBuilder"]
        PB[Assemble PromptComponents]
        PB --> SYS["System prompt:\n• Answer ONLY from sources\n• [Source X] citation format\n• Explicit no-info statement\n• Anti-hallucination rules"]
        PB --> USER["User prompt:\n{formatted_sources}\n\nQuestion: {query}"]
        PB --> TOKENS[Count total tokens]
    end

    USER --> GG
    SYS --> GG

    subgraph GeminiGenerator["GeminiGenerator"]
        GG[Configure GenerativeModel<br/>model=gemini-2.0-flash<br/>temperature=0.1<br/>max_output_tokens=8192]
        GG --> RETRY2[generate_content with\nexponential backoff\n1s → 2s → 4s]
        RETRY2 --> RESP[Extract text + usage_metadata]
    end

    RESP --> AV

    subgraph AnswerValidator["AnswerValidator"]
        AV[Parse citations: \[Source \d+\] pattern]
        AV --> VALID[Validate each citation\nagainst source_mapping keys]
        VALID --> HALL{Hallucination\nchecks}
        HALL --> H1[No citations present?]
        HALL --> H2[Invalid citation numbers?]
        HALL --> H3[Generic non-answer statements?]
        H1 --> CONF
        H2 --> CONF
        H3 --> CONF
        CONF["Confidence Score\n0.4 × citation_quality\n+ 0.3 × validity_score\n+ 0.2 × citation_density\n+ 0.1 × certainty_score"]
    end

    CONF --> AR[AnswerResponse\nanswer · citations · confidence_score\ntoken_usage · latency_ms · warnings\nhas_hallucinations · invalid_citations]
```

---

## 9. Chat Orchestration

`ChatService` is the central orchestrator that wires together the protection layer, retrieval, generation, and persistence layers in a single atomic request flow.

```mermaid
sequenceDiagram
    participant C as Client
    participant API as POST /api/v1/chat
    participant CS as ChatService
    participant PL as Protection Layer
    participant HR as HybridRetriever
    participant PB as PromptBuilder
    participant GG as GeminiGenerator
    participant CB as CircuitBreaker
    participant AV as AnswerValidator
    participant CT as CostTracker
    participant DB as PostgreSQL

    C->>API: ChatRequest { query, user_id, document_id?, top_k }
    API->>CS: process_chat(request, db)

    rect rgb(255, 240, 220)
        Note over CS,PL: Protection Layer
        CS->>PL: LoadShedder.check_load()<br/>CPU/Memory thresholds
        CS->>PL: RateLimiter.check_rate(user_id)<br/>10 req/min window in Redis
        CS->>PL: QuotaManager.check_quota(user_id)<br/>daily token + cost limits
        PL-->>CS: ✓ Pass / 429 / 503 errors
    end

    rect rgb(220, 240, 255)
        Note over CS,HR: Retrieval Phase
        CS->>HR: retrieve(query, user_id, db, top_k, document_id?)
        HR-->>CS: List[RetrievalResult] (scored + MMR diversified)
    end

    rect rgb(220, 255, 220)
        Note over CS,GG: Generation Phase
        CS->>PB: build_prompt(results, query)
        PB-->>CS: PromptComponents (system + user + sources)
        CS->>CB: CircuitBreaker.call(generate)
        CB->>GG: generate(prompt_components)
        GG-->>CB: AnswerResponse (raw)
        CB-->>CS: AnswerResponse / CircuitBreakerOpenError
        CS->>AV: validate(answer_response)
        AV-->>CS: ValidatedAnswerResponse + confidence_score
    end

    rect rgb(255, 220, 220)
        Note over CS,DB: Persistence Phase
        CS->>CT: calculate_cost(model, prompt_tokens, completion_tokens)
        CS->>DB: INSERT ChatInteraction (query, answer, citations, tokens, cost)
        CS->>PL: QuotaManager.record_usage(user_id, tokens, cost)
    end

    CS-->>API: ChatResponse { answer, citations, sources, confidence_score,<br/>interaction_id, token_usage, latency_ms, warnings }
    API-->>C: 200 OK / 429 / 503
```

### Protection Layer State Machine

```mermaid
stateDiagram-v2
    [*] --> RateLimitCheck
    RateLimitCheck --> QuotaCheck : ✓ within rate
    RateLimitCheck --> [*] : 429 RateLimitExceededError

    QuotaCheck --> LoadShedderCheck : ✓ within quota
    QuotaCheck --> [*] : 429 QuotaExceededError

    LoadShedderCheck --> CircuitBreakerCheck : ✓ CPU/Memory OK
    LoadShedderCheck --> [*] : 503 Load too high

    CircuitBreakerCheck --> Generation : CLOSED
    CircuitBreakerCheck --> [*] : 503 CircuitBreakerOpenError

    state CircuitBreakerCheck {
        CLOSED --> OPEN : ≥ 5 failures in 60s window
        OPEN --> HALF_OPEN : timeout 60s elapsed
        HALF_OPEN --> CLOSED : ≥ 2 successes
        HALF_OPEN --> OPEN : any failure
    }

    Generation --> [*] : ChatResponse
```

---

## 10. Monitoring and Feedback System

### Feedback Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend FeedbackModal
    participant API as POST /api/v1/chat/feedback
    participant FS as FeedbackService
    participant DB as PostgreSQL

    U->>FE: Click feedback button (1-5 stars + optional comment)
    FE->>API: FeedbackRequest { interaction_id, rating, comment }
    API->>FS: submit_feedback(db, interaction_id, rating, comment)
    FS->>DB: SELECT ChatInteraction WHERE id = interaction_id
    DB-->>FS: ChatInteraction (or None → 404)
    FS->>DB: SELECT ChatFeedback WHERE interaction_id = interaction_id
    alt Feedback already exists
        FS->>DB: UPDATE rating + comment + timestamp
    else New feedback
        FS->>DB: INSERT ChatFeedback
    end
    DB-->>FS: ChatFeedback record
    FS-->>API: FeedbackResponse
    API-->>FE: 200 OK
    FE->>FE: Set hasFeedback=true on message<br/>(disables re-submission)
```

### Cost Tracking

```mermaid
flowchart LR
    GENERATION[LLM Generation\ncompleted] --> CT

    subgraph CostTracker
        CT[calculate_cost\nmodel · prompt_tokens · completion_tokens]
        CT --> PRICE{Model pricing table}
        PRICE --> G2F["gemini-2.0-flash\ninput: $0.075/1M\noutput: $0.30/1M"]
        PRICE --> G15P["gemini-1.5-pro\ninput: $0.125/1M\noutput: $0.375/1M"]
        PRICE --> EMB["embedding-001\ninput: $0.01/1M"]
        G2F --> CALC
        G15P --> CALC
        EMB --> CALC
        CALC["cost = tokens/1M × price_per_million"]
    end

    CALC --> QM

    subgraph QuotaManager
        QM[record_usage\nuser_id · tokens · cost]
        QM --> RED[Redis INCR\ndaily_tokens:{user_id}:{date}]
        QM --> RCOST[Redis INCRBYFLOAT\ndaily_cost:{user_id}:{date}]
        RED --> CHECK{Check against\nlimits}
        RCOST --> CHECK
        CHECK --> DAILY_TK["DAILY_TOKEN_LIMIT\n= 1,000,000 tokens"]
        CHECK --> DAILY_COST["DAILY_COST_LIMIT\n= $10.00 USD"]
    end

    CALC --> PERSIST[Persist cost_usd\nin ChatInteraction record]
```

### Metrics and Monitoring

```mermaid
graph TD
    subgraph MetricsCollector["MetricsCollector"]
        M1[Track interaction latency]
        M2[Track token usage per model]
        M3[Track retrieval quality scores]
        M4[Track error rates by endpoint]
        M5[Track document processing times]
    end

    subgraph HealthEndpoint["Health Endpoint /health"]
        H1[Check PostgreSQL connectivity]
        H2[Check Redis connectivity]
        H3[Check Celery worker status]
        H4[Check Pinecone connectivity]
        H5[Report system CPU + Memory]
        H1 & H2 & H3 & H4 & H5 --> HR[HealthResponse\nstatus · services · version · uptime]
    end

    subgraph Logging["Structured Logging"]
        LOG[JSON logs with\nrequest_id · user_id · latency\ntoken_usage · cost · scores]
        LOG --> STDOUT[stdout / container logs]
    end

    MetricsCollector --> Logging
    HealthEndpoint --> Logging
```

---

## Component Dependency Map

```mermaid
graph BT
    %% Data layer
    PG[(PostgreSQL)]
    REDIS[(Redis)]
    PINE[(Pinecone)]
    FS[(File Storage)]

    %% Infrastructure
    GC[GeminiEmbeddingClient] --> REDIS
    PC[PineconeClient] --> PINE
    CS_DB[ChunkService] --> PG
    IM[IngestionManager] --> FS
    IM --> PG

    %% Embedding
    EC[EmbeddingCache] --> REDIS
    ES[EmbeddingService] --> GC
    ES --> EC

    %% Vector
    VS[VectorService] --> PC
    VS --> ES

    %% Retrieval
    BM25[BM25Service] --> PG
    QT[QueryTransformer] --> ES
    QT --> EC
    QC[QueryClassifier]
    SCORING[ScoringService]
    MMR_C[MMR]
    HR_C[HybridRetriever] --> PC
    HR_C --> BM25
    HR_C --> QT
    HR_C --> QC
    HR_C --> SCORING
    HR_C --> MMR_C
    HR_C --> CS_DB

    %% Generation
    GEN[GeminiGenerator]
    TB[TokenBudgetManager]
    CO[ContextOptimizer] --> TB
    SF_C[SourceFormatter]
    PB_C[PromptBuilder] --> CO
    PB_C --> SF_C
    PB_C --> TB
    AV_C[AnswerValidator]
    CT_C[CostTracker]

    %% Protection
    RL[RateLimiter] --> REDIS
    QM[QuotaManager] --> REDIS
    CB_C[CircuitBreaker]
    LS[LoadShedder]

    %% Orchestration
    CHAT_SVC[ChatService] --> HR_C
    CHAT_SVC --> PB_C
    CHAT_SVC --> GEN
    CHAT_SVC --> CB_C
    CHAT_SVC --> AV_C
    CHAT_SVC --> CT_C
    CHAT_SVC --> RL
    CHAT_SVC --> QM
    CHAT_SVC --> LS
    CHAT_SVC --> PG

    %% Monitoring
    FB_SVC[FeedbackService] --> PG

    %% Workers
    TASK[Celery Task] --> IM
    TASK --> ES
    TASK --> VS
    TASK --> CS_DB

    %% API
    CHAT_API[/api/v1/chat] --> CHAT_SVC
    CHAT_API --> FB_SVC
    DOC_API[/documents] --> IM
    DOC_API --> TASK
```

---

*Generated: March 2026 — reflects codebase at `rag_system/` + `frontend/`*
