# Monitoring, Metrics, and Feedback System

This module provides comprehensive monitoring and feedback capabilities for the RAG system, including cost tracking, performance metrics, and user feedback collection.

## Overview

The monitoring system consists of:

1. **Database Models**: `ChatInteraction` and `ChatFeedback` for storing interaction data
2. **Cost Tracking**: Calculate and monitor LLM API costs
3. **Metrics Collection**: Aggregate performance and quality metrics
4. **Feedback Service**: Collect and analyze user feedback
5. **API Endpoints**: 
   - `POST /api/v1/chat` - Returns `interaction_id` for feedback
   - `POST /api/v1/chat/feedback` - Submit user feedback

## Features

### 1. Automatic Interaction Tracking

Every chat request is automatically tracked with:
- Query and answer text
- Confidence score
- Citation count
- Latency breakdown (retrieval, generation)
- Token usage (prompt, completion, total)
- Model name
- Cost estimate

### 2. Cost Tracking

The `CostTracker` service calculates costs based on current Gemini pricing:

```python
from app.services.monitoring import CostTracker

cost_tracker = CostTracker()

# Calculate generation cost
cost = cost_tracker.calculate_cost(
    model_name="gemini-1.5-pro-latest",
    prompt_tokens=8234,
    completion_tokens=312,
)
# Returns: 0.001147125 (USD)

# Calculate embedding cost
embed_cost = cost_tracker.calculate_embedding_cost(
    model_name="models/embedding-001",
    token_count=500,
)

# Estimate monthly costs
estimates = cost_tracker.estimate_monthly_cost(
    daily_requests=1000,
    avg_prompt_tokens=8000,
    avg_completion_tokens=300,
    model_name="gemini-1.5-pro-latest",
)
# Returns: {
#     "cost_per_request": 0.001147125,
#     "daily_cost": 1.147125,
#     "monthly_cost": 34.41375,
#     "annual_cost": 418.730625,
# }
```

**Current Pricing** (as of implementation):
- **Gemini 1.5 Pro**: $0.125 per 1M input tokens, $0.375 per 1M output tokens
- **Gemini 1.5 Flash**: $0.075 per 1M input tokens, $0.30 per 1M output tokens
- **Embedding-001**: $0.01 per 1M tokens

### 3. Metrics Collection

The `MetricsCollector` provides comprehensive analytics:

```python
from app.services.monitoring import MetricsCollector

collector = MetricsCollector()

# Get user statistics
user_stats = await collector.get_user_statistics(
    db=db,
    user_id="user_123",
    hours=24,
)
# Returns:
# {
#     "user_id": "user_123",
#     "period_hours": 24,
#     "total_requests": 45,
#     "total_cost": 0.052,
#     "average_latency_ms": 3542.5,
#     "average_confidence": 0.87,
#     "total_tokens": 385420,
# }

# Get system-wide statistics
system_stats = await collector.get_system_statistics(db=db, hours=24)

# Get confidence score distribution
distribution = await collector.get_confidence_distribution(db=db, hours=24)
# Returns:
# {
#     "very_low (0.0-0.5)": 2,
#     "low (0.5-0.7)": 8,
#     "medium (0.7-0.85)": 15,
#     "high (0.85-1.0)": 20,
# }

# Get latency percentiles
percentiles = await collector.get_latency_percentiles(db=db, hours=24)
# Returns:
# {
#     "p50": 3200.5,
#     "p75": 4100.2,
#     "p90": 5800.1,
#     "p95": 7200.3,
#     "p99": 9500.8,
#     "min": 1200.0,
#     "max": 12000.5,
# }
```

### 4. Feedback Collection

Users can rate answers and provide comments:

```python
from app.services.monitoring import FeedbackService

feedback_service = FeedbackService()

# Submit feedback
feedback = await feedback_service.submit_feedback(
    db=db,
    interaction_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
    rating=5,
    comment="Great answer with accurate citations!",
)

# Get feedback statistics
avg_rating = await feedback_service.get_average_rating(db=db, hours=24)
rating_distribution = await feedback_service.get_rating_distribution(db=db, hours=24)
feedback_rate = await feedback_service.get_feedback_rate(db=db, hours=24)

# Get low-rated interactions for analysis
low_rated = await feedback_service.get_low_rated_interactions(
    db=db,
    threshold=2,  # Rating <= 2
    limit=20,
)
```

### 5. Performance Monitoring

Use `PerformanceMonitor` context manager to track operation latency:

```python
from app.services.monitoring import PerformanceMonitor

with PerformanceMonitor("database_query") as monitor:
    results = await db.execute(stmt)

# Automatically logs:
# "database_query completed" with duration_ms in structured log

duration = monitor.get_duration_ms()
```

## API Usage

### Chat Endpoint (Updated)

```bash
POST /api/v1/chat
```

**Request:**
```json
{
  "query": "What are the benefits of machine learning?",
  "user_id": "user_123",
  "document_id": null,
  "top_k": 5
}
```

**Response** (now includes `interaction_id`):
```json
{
  "interaction_id": "123e4567-e89b-12d3-a456-426614174000",
  "answer": "Machine learning offers several benefits...",
  "citations": [1, 2, 3],
  "confidence_score": 0.92,
  "sources": [...],
  "token_usage": {
    "prompt_tokens": 8234,
    "completion_tokens": 312,
    "total_tokens": 8546
  },
  "latency_ms": 3542.5,
  "warnings": []
}
```

### Feedback Endpoint (New)

```bash
POST /api/v1/chat/feedback
```

**Request:**
```json
{
  "interaction_id": "123e4567-e89b-12d3-a456-426614174000",
  "rating": 5,
  "comment": "Great answer with accurate citations!"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Feedback recorded successfully",
  "feedback_id": "223e4567-e89b-12d3-a456-426614174001"
}
```

**Rating Scale:**
- 1: Poor
- 2: Below Average
- 3: Average
- 4: Good
- 5: Excellent

## Database Schema

### ChatInteraction Table

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | VARCHAR(255) | User identifier |
| query | TEXT | User query |
| answer | TEXT | Generated answer |
| confidence_score | FLOAT | Confidence (0-1) |
| citations_count | INTEGER | Number of citations |
| latency_ms | FLOAT | Total latency |
| retrieval_latency_ms | FLOAT | Retrieval time |
| generation_latency_ms | FLOAT | Generation time |
| prompt_tokens | INTEGER | Input tokens |
| completion_tokens | INTEGER | Output tokens |
| total_tokens | INTEGER | Total tokens |
| model_name | VARCHAR(100) | LLM model used |
| cost_estimate | FLOAT | Cost in USD |
| created_at | TIMESTAMP | Creation time |

**Indexes:**
- `ix_chat_interactions_id` (id)
- `ix_chat_interactions_user_id` (user_id)
- `ix_chat_interactions_created_at` (created_at)
- `ix_chat_interactions_user_created` (user_id, created_at)
- `ix_chat_interactions_confidence` (confidence_score)

### ChatFeedback Table

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| interaction_id | UUID | FK to chat_interactions |
| rating | INTEGER | Rating 1-5 |
| comment | TEXT | Optional comment |
| created_at | TIMESTAMP | Creation time |

**Indexes:**
- `ix_chat_feedbacks_id` (id)
- `ix_chat_feedbacks_interaction_id` (interaction_id)
- `ix_chat_feedbacks_rating` (rating)

## Migration

Apply the database migration:

```bash
# Using psql
psql -U your_user -d your_db -f migrations/add_monitoring_tables.sql

# Using Docker
docker exec -i postgres_container psql -U your_user -d your_db < migrations/add_monitoring_tables.sql

# Rollback if needed
docker exec -i postgres_container psql -U your_user -d your_db < migrations/rollback_monitoring_tables.sql
```

## Monitoring Dashboard Queries

Get insights from your data:

```sql
-- Top users by request count (last 24h)
SELECT 
    user_id,
    COUNT(*) as request_count,
    AVG(confidence_score) as avg_confidence,
    SUM(cost_estimate) as total_cost
FROM chat_interactions
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY user_id
ORDER BY request_count DESC
LIMIT 10;

-- Average metrics by hour
SELECT 
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as requests,
    AVG(latency_ms) as avg_latency,
    AVG(confidence_score) as avg_confidence,
    SUM(cost_estimate) as total_cost
FROM chat_interactions
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY hour
ORDER BY hour DESC;

-- Feedback distribution
SELECT 
    rating,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM chat_feedbacks
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY rating
ORDER BY rating DESC;

-- Low confidence interactions (potential quality issues)
SELECT 
    id,
    user_id,
    query,
    confidence_score,
    citations_count,
    created_at
FROM chat_interactions
WHERE confidence_score < 0.6
ORDER BY created_at DESC
LIMIT 20;
```

## Integration Example

Complete integration in your application:

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.orchestration import ChatService
from app.services.monitoring import (
    CostTracker,
    MetricsCollector,
    FeedbackService,
)
from app.schemas.chat import ChatRequest, ChatResponse, FeedbackRequest

app = FastAPI()

@app.post("/chat")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    # Process chat (automatically stores interaction)
    chat_service = ChatService()
    response = await chat_service.process_chat(request=request, db=db)
    
    # interaction_id is now in response
    return response

@app.post("/feedback")
async def feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    feedback_service = FeedbackService()
    feedback = await feedback_service.submit_feedback(
        db=db,
        interaction_id=UUID(request.interaction_id),
        rating=request.rating,
        comment=request.comment,
    )
    return {"success": True, "feedback_id": str(feedback.id)}

@app.get("/metrics/user/{user_id}")
async def user_metrics(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    collector = MetricsCollector()
    stats = await collector.get_user_statistics(
        db=db,
        user_id=user_id,
        hours=24,
    )
    return stats
```

## Structured Logging

All monitoring operations include structured logging:

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "message": "Interaction metrics recorded",
  "interaction_id": "123e4567-e89b-12d3-a456-426614174000",
  "user_id": "user_123",
  "total_latency_ms": 3542.5,
  "total_tokens": 8546,
  "confidence_score": 0.92,
  "cost": 0.001147125
}
```

## Best Practices

1. **Monitor Cost Trends**: Set up alerts for unusual cost spikes
2. **Track Confidence Scores**: Low confidence (<0.6) may indicate poor quality
3. **Analyze Feedback**: Use low ratings to identify improvement areas
4. **Monitor Latency**: Track p95/p99 latencies for SLA compliance
5. **User Segmentation**: Compare metrics across user segments
6. **A/B Testing**: Use interaction data to evaluate system changes

## Future Enhancements

Potential additions to the monitoring system:

- Real-time dashboards (Grafana/Metabase)
- Alerting (PagerDuty, email)
- A/B testing framework
- Detailed error categorization
- User session tracking
- Query embedding analysis
- Cost optimization recommendations
