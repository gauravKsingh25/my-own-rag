# Quick Start Guide - Protection Layer

This guide helps you quickly deploy and test the protection and stability layer.

---

## Step 1: Install Dependencies

```bash
pip install psutil==5.9.8
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

Verify psutil:
```bash
python -c "import psutil; print(f'CPU: {psutil.cpu_percent()}%, Memory: {psutil.virtual_memory().percent}%')"
```

---

## Step 2: Configure Protection Settings

Edit `.env` or environment variables:

```bash
# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_WINDOW=60

# Daily Quota
QUOTA_ENABLED=true
DAILY_TOKEN_LIMIT=1000000
DAILY_COST_LIMIT=10.0

# Circuit Breaker
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_SUCCESS_THRESHOLD=2
CIRCUIT_BREAKER_TIMEOUT=60.0

# Load Shedding
LOAD_SHEDDING_ENABLED=true
CPU_THRESHOLD_HIGH=85.0
MEMORY_THRESHOLD_HIGH=90.0

# Redis (required for rate limiting)
REDIS_URL=redis://localhost:6379/0
```

---

## Step 3: Start Services

```bash
# Start Redis (required for rate limiting)
docker run -d -p 6379:6379 redis:7-alpine

# Or use existing Redis
redis-cli ping  # Should return PONG

# Start FastAPI application
uvicorn app.main:app --reload --port 8000
```

Verify startup logs:
```
INFO: ChatService initialized with protection layer
      (rate_limit_enabled=True, quota_enabled=True,
       circuit_breaker_enabled=True, load_shedding_enabled=True)
```

---

## Step 4: Test Rate Limiting

Make 11 requests rapidly (limit is 10/min):

```bash
for i in {1..11}; do
  echo "Request $i:"
  curl -X POST http://localhost:8000/api/v1/chat \
    -H "Content-Type: application/json" \
    -d '{
      "query": "What is machine learning?",
      "user_id": "test_user",
      "top_k": 5
    }' | jq .
  echo ""
done
```

**Expected**:
- Requests 1-10: **200 OK**
- Request 11: **429 Too Many Requests**

**Response for 11th request**:
```json
{
  "error": "Rate limit exceeded. Try again in 42 seconds.",
  "error_type": "RateLimitExceeded",
  "retry_after": 42
}
```

**Header**:
```
Retry-After: 42
```

---

## Step 5: Test Quota Management

### Option A: Simulate High Usage

```sql
-- Connect to PostgreSQL
psql -U your_user -d rag_db

-- Set high token usage for test_user
INSERT INTO chat_interactions (
  user_id, 
  query, 
  answer, 
  total_tokens, 
  cost_estimate, 
  confidence_score, 
  latency_ms, 
  model_name, 
  created_at
) VALUES (
  'test_user',
  'test query',
  'test answer',
  1100000,  -- Over 1M limit
  12.0,     -- Over $10 limit
  0.9,
  1000,
  'gemini-1.5-pro-latest',
  CURRENT_TIMESTAMP
);
```

### Test Request

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is AI?",
    "user_id": "test_user"
  }' | jq .
```

**Expected**: **429 Too Many Requests**
```json
{
  "error": "Daily quota exceeded. Resets at 2026-02-07T00:00:00.",
  "error_type": "QuotaExceeded",
  "reset_time": "2026-02-07T00:00:00"
}
```

---

## Step 6: Test Load Shedding

### Generate CPU Load

**Linux/Mac**:
```bash
# Install stress tool
sudo apt-get install stress  # Ubuntu/Debian
brew install stress          # macOS

# Generate 90% CPU load for 60 seconds
stress --cpu 8 --timeout 60s &
```

**Python Alternative**:
```bash
python3 << EOF
import multiprocessing
import time

def cpu_load():
    while True:
        pass

# Spawn CPU-intensive processes
processes = []
for _ in range(multiprocessing.cpu_count()):
    p = multiprocessing.Process(target=cpu_load)
    p.start()
    processes.append(p)

# Let it run for 30 seconds
time.sleep(30)

# Cleanup
for p in processes:
    p.terminate()
EOF
```

### Make Request During Load

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain quantum computing",
    "user_id": "test_user",
    "top_k": 5
  }' | jq .
```

**Expected**: **200 OK** (but degraded)

**Check logs for degradation**:
```bash
docker logs rag_api --tail 50 | grep "degraded mode"
```

**Log output**:
```
WARN: System under load - degraded mode active
      (load_level=high, cpu=88.5%, memory=82.3%,
       original_top_k=5, adjusted_top_k=3,
       original_max_tokens=2048, adjusted_max_tokens=1024,
       apply_mmr=false)
```

**Response may include**:
```json
{
  "answer": "Quantum computing is...",
  "warnings": ["System under high load - reduced response quality"]
}
```

---

## Step 7: Test Circuit Breaker

### Mock Gemini Failures

Temporarily modify `app/services/generation/gemini_generator.py` to fail:

```python
async def generate(self, system_prompt, user_prompt, max_output_tokens=2048):
    # For testing: always fail
    raise Exception("Simulated Gemini failure")
```

### Make 6 Requests

```bash
for i in {1..6}; do
  echo "Request $i:"
  curl -X POST http://localhost:8000/api/v1/chat \
    -H "Content-Type: application/json" \
    -d '{"query": "test", "user_id": "test_user"}' \
    2>&1 | grep -o '"error_type":"[^"]*"'
  echo ""
done
```

**Expected**:
- Requests 1-5: 500 Internal Error (failures recorded)
- Request 6+: **503 Service Unavailable** (circuit open)

**Response for 6th request**:
```json
{
  "error": "The AI service is temporarily unavailable...",
  "error_type": "ServiceUnavailable"
}
```

**Logs**:
```
ERROR: CircuitBreaker 'gemini_generation' OPENED
       (failure_count=5, threshold=5)
WARN: Circuit breaker open - rejecting request
```

### Restore Normal Operation

Remove the mock failure code and wait 60 seconds (timeout period). Circuit will transition to HALF_OPEN and eventually CLOSED.

---

## Step 8: Monitor Protection Status

### Check Rate Limit Info

```bash
# Via Redis CLI
redis-cli HGETALL "rate_limit:test_user"
```

**Output**:
```
1) "tokens"
2) "5.2"
3) "last_refill"
4) "1707235187.234"
```

### Check Quota Status

```sql
-- Daily usage for user
SELECT 
  SUM(total_tokens) as tokens_used,
  SUM(cost_estimate) as cost_used,
  COUNT(*) as requests
FROM chat_interactions
WHERE user_id = 'test_user'
  AND created_at >= CURRENT_DATE;
```

### Check Circuit Breaker State

Add monitoring endpoint (optional):

```python
# app/api/protection.py
from fastapi import APIRouter
from app.services.protection import CircuitBreakerManager

router = APIRouter(prefix="/api/v1/protection", tags=["protection"])

@router.get("/circuit-breakers")
async def get_circuit_breaker_states():
    manager = CircuitBreakerManager()
    return manager.get_all_states()
```

**Request**:
```bash
curl http://localhost:8000/api/v1/protection/circuit-breakers | jq .
```

**Response**:
```json
{
  "gemini_generation": {
    "state": "closed",
    "failure_count": 0,
    "opened_at": null
  }
}
```

### Check System Load

```bash
# Via Python
python3 -c "import psutil; print(f'CPU: {psutil.cpu_percent(1)}%, Memory: {psutil.virtual_memory().percent}%')"
```

---

## Step 9: Verify Logs

Check structured logs for protection events:

```bash
# Docker logs
docker logs rag_api --tail 100 | grep -E "Rate limit|Quota|Circuit|degraded"

# File logs (if configured)
tail -f /var/log/rag_api.log | jq 'select(.message | contains("protection"))'
```

**Sample logs**:
```json
{
  "timestamp": "2026-02-06T10:30:45.123Z",
  "level": "WARN",
  "message": "Rate limit exceeded for user test_user",
  "user_id": "test_user",
  "retry_after": 42
}

{
  "timestamp": "2026-02-06T10:31:00.456Z",
  "level": "WARN",
  "message": "Daily quota exceeded for user test_user",
  "tokens_used": 1050000,
  "cost_used": 12.5
}

{
  "timestamp": "2026-02-06T10:32:15.789Z",
  "level": "ERROR",
  "message": "CircuitBreaker 'gemini_generation' OPENED",
  "failure_count": 5
}
```

---

## Step 10: Production Deployment

### Environment Variables

Set in production environment:

```bash
# Conservative limits for production
export RATE_LIMIT_PER_MINUTE=20
export DAILY_TOKEN_LIMIT=5000000
export DAILY_COST_LIMIT=50.0

# More lenient circuit breaker
export CIRCUIT_BREAKER_FAILURE_THRESHOLD=10
export CIRCUIT_BREAKER_TIMEOUT=120.0

# Aggressive load shedding
export CPU_THRESHOLD_HIGH=80.0
export MEMORY_THRESHOLD_HIGH=85.0
```

### Health Checks

Add to your orchestrator (Kubernetes, ECS, etc.):

```yaml
# Kubernetes example
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Monitoring Alerts

Set up alerts for:

1. **High Rate Limit Violations**:
   - Alert if >100 violations/minute
   - Indicates potential attack or misconfigured client

2. **Quota Exceeded Spike**:
   - Alert if >10 users hit quota in 1 hour
   - May indicate pricing tier issue

3. **Circuit Breaker Open**:
   - Alert immediately when circuit opens
   - Page on-call if open >5 minutes

4. **Extended Degradation**:
   - Alert if degraded >10 minutes
   - Scale infrastructure or investigate

---

## Common Issues and Solutions

### Issue: Rate Limit Not Working

**Symptoms**: All requests pass through

**Solutions**:
```bash
# Check Redis connection
redis-cli ping

# Check if rate limiting is enabled
echo $RATE_LIMIT_ENABLED

# Check logs for Redis errors
docker logs rag_api | grep -i redis
```

### Issue: Quota Always Exceeded

**Symptoms**: All users getting 429 quota errors

**Solutions**:
```sql
-- Check if quota limits are too low
SELECT user_id, SUM(total_tokens), SUM(cost_estimate)
FROM chat_interactions
WHERE created_at >= CURRENT_DATE
GROUP BY user_id;

-- Increase limits
export DAILY_TOKEN_LIMIT=10000000
export DAILY_COST_LIMIT=100.0
```

### Issue: Circuit Breaker Stuck Open

**Symptoms**: All requests getting 503

**Solutions**:
```bash
# Check if Gemini API is actually down
curl https://generativelanguage.googleapis.com/v1/models

# Manually reset circuit (via admin API or code)
# Or wait for timeout period

# Increase timeout if failures are transient
export CIRCUIT_BREAKER_TIMEOUT=300.0
```

### Issue: System Always Degraded

**Symptoms**: Load shedding always active

**Solutions**:
```bash
# Check actual system load
top
htop

# Increase thresholds if normal load is high
export CPU_THRESHOLD_HIGH=90.0
export MEMORY_THRESHOLD_HIGH=95.0

# Or scale infrastructure (more CPU/RAM)
```

---

## Success!

You now have a fully functional protection layer:

- ✅ Rate limiting enforced
- ✅ Daily quotas tracked
- ✅ Circuit breaker protecting Gemini API
- ✅ Load shedding maintaining availability

**Next Steps**:
1. Monitor protection metrics
2. Tune limits based on usage patterns
3. Set up alerting
4. Document runbooks for common scenarios

Happy protecting! 🛡️
