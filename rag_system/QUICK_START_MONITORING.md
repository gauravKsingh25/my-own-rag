# Quick Start Guide - Monitoring System

This guide will help you quickly get started with the monitoring, metrics, and feedback system.

## Step 1: Apply Database Migration

Run the migration to create the new tables:

```bash
# Using Docker
docker exec -i rag_postgres psql -U postgres -d rag_db < migrations/add_monitoring_tables.sql

# Or using psql directly
psql -U your_user -d your_db -f migrations/add_monitoring_tables.sql
```

Verify tables were created:

```bash
docker exec -it rag_postgres psql -U postgres -d rag_db -c "\dt chat_*"
```

Expected output:
```
              List of relations
 Schema |       Name        | Type  |  Owner   
--------+-------------------+-------+----------
 public | chat_feedbacks    | table | postgres
 public | chat_interactions | table | postgres
```

## Step 2: Test Chat Endpoint (Now Returns interaction_id)

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the benefits of machine learning?",
    "user_id": "test_user",
    "top_k": 5
  }'
```

Response will now include `interaction_id`:
```json
{
  "interaction_id": "123e4567-e89b-12d3-a456-426614174000",
  "answer": "Machine learning offers...",
  "citations": [1, 2],
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

## Step 3: Submit Feedback

Use the `interaction_id` from the chat response:

```bash
curl -X POST http://localhost:8000/api/v1/chat/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "interaction_id": "123e4567-e89b-12d3-a456-426614174000",
    "rating": 5,
    "comment": "Great answer with accurate citations!"
  }'
```

Expected response:
```json
{
  "success": true,
  "message": "Feedback recorded successfully",
  "feedback_id": "223e4567-e89b-12d3-a456-426614174001"
}
```

## Step 4: Query Metrics Programmatically

### Get User Statistics

```python
from app.services.monitoring import MetricsCollector
from app.db.database import get_db

async def get_my_stats(user_id: str):
    collector = MetricsCollector()
    async for db in get_db():
        stats = await collector.get_user_statistics(
            db=db,
            user_id=user_id,
            hours=24,
        )
        print(f"User {user_id} statistics:")
        print(f"  Total requests: {stats['total_requests']}")
        print(f"  Total cost: ${stats['total_cost']:.4f}")
        print(f"  Avg latency: {stats['average_latency_ms']:.2f}ms")
        print(f"  Avg confidence: {stats['average_confidence']:.2f}")
        break

# Run it
import asyncio
asyncio.run(get_my_stats("test_user"))
```

### Get System-Wide Statistics

```python
from app.services.monitoring import MetricsCollector

async def get_system_stats():
    collector = MetricsCollector()
    async for db in get_db():
        stats = await collector.get_system_statistics(db=db, hours=24)
        print("System statistics (last 24h):")
        print(f"  Total requests: {stats['total_requests']}")
        print(f"  Unique users: {stats['unique_users']}")
        print(f"  Total cost: ${stats['total_cost']:.4f}")
        print(f"  Avg confidence: {stats['average_confidence']:.2f}")
        if 'average_rating' in stats:
            print(f"  Avg rating: {stats['average_rating']:.2f}")
            print(f"  Feedback rate: {stats['feedback_rate']:.1%}")
        break

asyncio.run(get_system_stats())
```

### Calculate Costs

```python
from app.services.monitoring import CostTracker

tracker = CostTracker()

# Single request cost
cost = tracker.calculate_cost(
    model_name="gemini-1.5-pro-latest",
    prompt_tokens=8234,
    completion_tokens=312,
)
print(f"Request cost: {tracker.format_cost(cost)}")

# Monthly estimate
estimates = tracker.estimate_monthly_cost(
    daily_requests=1000,
    avg_prompt_tokens=8000,
    avg_completion_tokens=300,
    model_name="gemini-1.5-pro-latest",
)
print(f"\nMonthly cost estimate for 1000 daily requests:")
print(f"  Per request: {tracker.format_cost(estimates['cost_per_request'])}")
print(f"  Daily: {tracker.format_cost(estimates['daily_cost'])}")
print(f"  Monthly: {tracker.format_cost(estimates['monthly_cost'])}")
print(f"  Annual: {tracker.format_cost(estimates['annual_cost'])}")
```

Example output:
```
Request cost: $0.001147
Monthly cost estimate for 1000 daily requests:
  Per request: $0.001147
  Daily: $1.15
  Monthly: $34.41
  Annual: $418.73
```

## Step 5: Query Database Directly

### View Recent Interactions

```sql
SELECT 
    id,
    user_id,
    LEFT(query, 50) || '...' as query_preview,
    confidence_score,
    latency_ms,
    cost_estimate,
    created_at
FROM chat_interactions
ORDER BY created_at DESC
LIMIT 10;
```

### Check Feedback Distribution

```sql
SELECT 
    rating,
    COUNT(*) as count,
    ROUND(AVG(ci.confidence_score), 2) as avg_confidence,
    ROUND(AVG(ci.latency_ms), 2) as avg_latency
FROM chat_feedbacks cf
JOIN chat_interactions ci ON cf.interaction_id = ci.id
GROUP BY rating
ORDER BY rating DESC;
```

### Daily Cost Breakdown

```sql
SELECT 
    DATE(created_at) as date,
    COUNT(*) as requests,
    SUM(cost_estimate) as total_cost,
    AVG(cost_estimate) as avg_cost,
    AVG(latency_ms) as avg_latency
FROM chat_interactions
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

### Find Low Confidence Interactions

```sql
SELECT 
    id,
    user_id,
    LEFT(query, 100) as query,
    confidence_score,
    citations_count,
    created_at
FROM chat_interactions
WHERE 
    confidence_score < 0.7 AND
    created_at >= NOW() - INTERVAL '1 day'
ORDER BY confidence_score ASC
LIMIT 20;
```

## Step 6: Monitor with Structured Logs

View logs with monitoring data:

```bash
# Docker logs
docker logs rag_api --tail 100 | grep "metrics recorded"

# Look for entries like:
# {
#   "timestamp": "2024-01-15T10:30:45.123Z",
#   "level": "INFO",
#   "message": "Interaction metrics recorded",
#   "interaction_id": "...",
#   "total_latency_ms": 3542.5,
#   "cost": 0.001147
# }
```

## Step 7: Create a Simple Dashboard Endpoint

Add this to your FastAPI app for quick dashboards:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.monitoring import MetricsCollector

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])

@router.get("/dashboard")
async def dashboard(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard metrics."""
    collector = MetricsCollector()
    
    system_stats = await collector.get_system_statistics(db=db, hours=hours)
    confidence_dist = await collector.get_confidence_distribution(db=db, hours=hours)
    latency_pct = await collector.get_latency_percentiles(db=db, hours=hours)
    
    return {
        "period_hours": hours,
        "system": system_stats,
        "confidence_distribution": confidence_dist,
        "latency_percentiles": latency_pct,
    }

# Add to main.py
from app.api import metrics
app.include_router(metrics.router)
```

Access dashboard:
```bash
curl http://localhost:8000/api/v1/metrics/dashboard?hours=24
```

## Common Tasks

### Export Interactions for Analysis

```sql
COPY (
    SELECT 
        id,
        user_id,
        query,
        answer,
        confidence_score,
        latency_ms,
        total_tokens,
        cost_estimate,
        created_at
    FROM chat_interactions
    WHERE created_at >= NOW() - INTERVAL '7 days'
) TO '/tmp/interactions_last_7_days.csv' CSV HEADER;
```

### Update Feedback

Users can resubmit feedback for the same interaction:

```bash
curl -X POST http://localhost:8000/api/v1/chat/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "interaction_id": "123e4567-e89b-12d3-a456-426614174000",
    "rating": 4,
    "comment": "Updated my rating after thinking about it more"
  }'
```

The system will update the existing feedback instead of creating a new one.

### Check Feedback Rate

```sql
SELECT 
    COUNT(DISTINCT ci.id) as total_interactions,
    COUNT(DISTINCT cf.id) as interactions_with_feedback,
    ROUND(
        COUNT(DISTINCT cf.id)::numeric / 
        COUNT(DISTINCT ci.id) * 100, 
        2
    ) as feedback_rate_percent
FROM chat_interactions ci
LEFT JOIN chat_feedbacks cf ON ci.id = cf.interaction_id
WHERE ci.created_at >= NOW() - INTERVAL '7 days';
```

## Troubleshooting

### Migration Failed

Rollback and retry:
```bash
docker exec -i rag_postgres psql -U postgres -d rag_db < migrations/rollback_monitoring_tables.sql
docker exec -i rag_postgres psql -U postgres -d rag_db < migrations/add_monitoring_tables.sql
```

### No interaction_id in Response

Check that ChatService is properly initialized:
- Verify CostTracker is imported
- Check database session is passed to process_chat
- Look for errors in logs during interaction storage

### Feedback Endpoint Returns 404

- Verify interaction_id is correct (UUID format)
- Check interaction exists in database
- Ensure database connection is working

### Cost Seems Wrong

- Verify model name matches pricing configuration
- Check token counts are accurate
- Review CostTracker pricing constants in cost_tracker.py
- Update pricing if Google changes rates

## Performance Tips

1. **Index Usage**: Ensure queries use indexes
   ```sql
   EXPLAIN ANALYZE 
   SELECT * FROM chat_interactions 
   WHERE user_id = 'test_user' 
   AND created_at >= NOW() - INTERVAL '24 hours';
   ```

2. **Batch Metrics**: Query metrics in batches rather than per-request

3. **Cache Results**: Cache dashboard metrics for 5-10 minutes

4. **Partition Tables**: For >10M interactions, consider partitioning by created_at

5. **Archive Old Data**: Move interactions >90 days to archive table

## Next Steps

1. Set up automated daily/weekly reports
2. Create Grafana/Metabase dashboards
3. Configure alerts for:
   - Low confidence (<0.5)
   - High latency (>10s)
   - Cost spikes
   - Low ratings (≤2)
4. Integrate with monitoring tools (Prometheus, DataDog, etc.)
5. Build A/B testing framework on top of metrics

## Getting Help

- Review documentation: `app/services/monitoring/README.md`
- Check implementation summary: `MONITORING_IMPLEMENTATION_SUMMARY.md`
- View code examples in monitoring service files
- Check structured logs for debugging

## Success!

You now have a fully functional monitoring system tracking:
- ✅ Every chat interaction with full metadata
- ✅ Real-time cost calculation
- ✅ User feedback with ratings and comments
- ✅ Performance metrics and analytics
- ✅ Quality monitoring via confidence scores

Happy monitoring! 🎉
