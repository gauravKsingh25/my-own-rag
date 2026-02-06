# Protection and Stability Layer

This module provides production-grade protection mechanisms to ensure system stability and prevent abuse.

## Overview

The protection layer implements four key mechanisms:

1. **Rate Limiting**: Token bucket algorithm limiting requests per user
2. **Quota Management**: Daily limits on token usage and costs per user
3. **Circuit Breaker**: Automatic failure protection for Gemini API
4. **Load Shedding**: Graceful degradation under high system load

## Components

### 1. Rate Limiter (`rate_limiter.py`)

Redis-based token bucket algorithm for per-user rate limiting.

**Features:**
- 10 requests per minute per user (configurable)
- Atomic operations using Lua script
- Returns 429 with Retry-After header
- Fail-open design (allows requests if Redis fails)

**Configuration:**
```python
RATE_LIMIT_ENABLED = True
RATE_LIMIT_PER_MINUTE = 10
RATE_LIMIT_WINDOW = 60  # seconds
```

**Usage:**
```python
from app.services.protection import RateLimiter

limiter = RateLimiter(rate=10, window=60)

# Check rate limit
result = await limiter.check_rate_limit(user_id="user_123")

if not result.allowed:
    # Rate limit exceeded
    retry_after = result.retry_after
    raise RateLimitExceededError(f"Retry after {retry_after}s", retry_after)
```

**Response:**
```json
{
  "allowed": false,
  "remaining": 0,
  "reset_time": 1707235200.0,
  "retry_after": 42
}
```

### 2. Quota Manager (`quota_manager.py`)

Tracks daily token usage and costs per user from ChatInteraction records.

**Features:**
- 1M tokens per user per day (configurable)
- $10 cost limit per user per day (configurable)
- Resets at midnight UTC
- Database-backed tracking

**Configuration:**
```python
QUOTA_ENABLED = True
DAILY_TOKEN_LIMIT = 1_000_000
DAILY_COST_LIMIT = 10.0
```

**Usage:**
```python
from app.services.protection import QuotaManager

quota_mgr = QuotaManager(
    daily_token_limit=1_000_000,
    daily_cost_limit=10.0,
)

# Check quota
status = await quota_mgr.check_quota(db, user_id="user_123")

if status.quota_exceeded:
    # Quota exceeded
    raise QuotaExceededError(
        f"Quota exceeded. Resets at {status.reset_time}",
        reset_time=status.reset_time.isoformat(),
    )
```

**Response:**
```json
{
  "tokens_used": 850000,
  "tokens_limit": 1000000,
  "tokens_remaining": 150000,
  "cost_used": 7.25,
  "cost_limit": 10.0,
  "cost_remaining": 2.75,
  "quota_exceeded": false,
  "reset_time": "2026-02-07T00:00:00"
}
```

### 3. Circuit Breaker (`circuit_breaker.py`)

Protects against cascading failures by automatically opening circuit after repeated failures.

**States:**
- **CLOSED**: Normal operation, all requests pass through
- **OPEN**: Circuit tripped, requests fail immediately
- **HALF_OPEN**: Testing recovery, limited requests allowed

**Features:**
- Opens after 5 failures in 60 seconds (configurable)
- Automatically attempts recovery after 60 second timeout
- Returns to CLOSED after 2 consecutive successes
- Per-service circuit breakers (e.g., "gemini_generation")

**Configuration:**
```python
CIRCUIT_BREAKER_ENABLED = True
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_SUCCESS_THRESHOLD = 2
CIRCUIT_BREAKER_TIMEOUT = 60.0
CIRCUIT_BREAKER_WINDOW = 60.0
```

**Usage:**
```python
from app.services.protection import CircuitBreakerManager, CircuitBreakerConfig

manager = CircuitBreakerManager()

# Get circuit breaker for Gemini
breaker = manager.get_breaker(
    name="gemini_generation",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout=60.0,
    ),
)

# Call protected function
try:
    result = await breaker.call(
        gemini_generator.generate,
        system_prompt=prompt,
        user_prompt=query,
    )
except CircuitBreakerOpenError:
    # Service unavailable
    raise HTTPException(503, "Service temporarily unavailable")
```

**State Information:**
```json
{
  "name": "gemini_generation",
  "state": "closed",
  "failure_count": 2,
  "failure_threshold": 5,
  "success_count": 0,
  "opened_at": null,
  "time_until_half_open": null
}
```

### 4. Load Shedder (`load_shedder.py`)

Gracefully degrades service quality under high system load to maintain availability.

**Load Levels:**
- **NORMAL**: Full quality (CPU/Memory < 70%)
- **ELEVATED**: Slight degradation (CPU/Memory 70-85%)
- **HIGH**: Moderate degradation (CPU/Memory 85-95%)
- **CRITICAL**: Maximum degradation (CPU/Memory > 95%)

**Degradation Strategy:**

| Level | top_k | MMR | max_output_tokens | Temperature |
|-------|-------|-----|-------------------|-------------|
| NORMAL | 5 | ✓ | 2048 | 0.7 |
| ELEVATED | 4 | ✓ | 1536 | 0.7 |
| HIGH | 3 | ✗ | 1024 | 0.5 |
| CRITICAL | 2 | ✗ | 512 | 0.3 |

**Configuration:**
```python
LOAD_SHEDDING_ENABLED = True
CPU_THRESHOLD_ELEVATED = 70.0
CPU_THRESHOLD_HIGH = 85.0
CPU_THRESHOLD_CRITICAL = 95.0
MEMORY_THRESHOLD_ELEVATED = 75.0
MEMORY_THRESHOLD_HIGH = 90.0
MEMORY_THRESHOLD_CRITICAL = 95.0
```

**Usage:**
```python
from app.services.protection import LoadShedder

shedder = LoadShedder(
    cpu_threshold_high=85.0,
    memory_threshold_high=90.0,
)

# Check load and get degradation config
metrics = shedder.check_load(
    original_top_k=5,
    original_max_tokens=2048,
)

if metrics.degraded:
    # Apply degraded parameters
    top_k = metrics.degradation_config.top_k
    max_tokens = metrics.degradation_config.max_output_tokens
    apply_mmr = metrics.degradation_config.enable_mmr
```

**Response:**
```json
{
  "cpu_percent": 88.5,
  "memory_percent": 82.3,
  "load_level": "high",
  "degraded": true,
  "degradation_config": {
    "top_k": 3,
    "enable_mmr": false,
    "max_output_tokens": 1024,
    "temperature": 0.5,
    "retrieval_timeout": 10.0,
    "generation_timeout": 20.0
  }
}
```

## Integration

The protection layer is automatically integrated into the chat pipeline:

### Request Flow

```
User Request
    ↓
[1] Rate Limit Check → 429 if exceeded
    ↓
[2] Quota Check → 429 if exceeded  
    ↓
[3] Load Check → Adjust parameters if degraded
    ↓
[4] Retrieval (with adjusted top_k, apply_mmr)
    ↓
[5] Prompt Building
    ↓
[6] Generation (with circuit breaker, adjusted max_tokens) → 503 if open
    ↓
[7] Validation
    ↓
[8] Response
```

### Error Responses

**429 Too Many Requests (Rate Limit):**
```json
{
  "error": "Rate limit exceeded. Try again in 42 seconds.",
  "error_type": "RateLimitExceeded",
  "retry_after": 42,
  "details": {
    "user_id": "user_123",
    "message": "You have exceeded the rate limit..."
  }
}
```

**429 Too Many Requests (Quota):**
```json
{
  "error": "Daily quota exceeded. Resets at 2026-02-07T00:00:00.",
  "error_type": "QuotaExceeded",
  "reset_time": "2026-02-07T00:00:00",
  "details": {
    "user_id": "user_123",
    "message": "You have exceeded your daily quota..."
  }
}
```

**503 Service Unavailable (Circuit Breaker):**
```json
{
  "error": "The AI service is temporarily unavailable...",
  "error_type": "ServiceUnavailable",
  "details": {
    "message": "Our AI service is experiencing issues..."
  }
}
```

## Monitoring

Check protection layer status:

```bash
# Rate limit info for user
GET /api/v1/protection/rate-limit/{user_id}

# Quota status for user
GET /api/v1/protection/quota/{user_id}

# Circuit breaker states
GET /api/v1/protection/circuit-breakers

# Load shedder status
GET /api/v1/protection/load
```

## Configuration Reference

All settings in `app/core/config.py`:

```python
# Rate Limiting
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_PER_MINUTE: int = 10
RATE_LIMIT_WINDOW: int = 60

# Daily Quota
QUOTA_ENABLED: bool = True
DAILY_TOKEN_LIMIT: int = 1_000_000
DAILY_COST_LIMIT: float = 10.0

# Circuit Breaker
CIRCUIT_BREAKER_ENABLED: bool = True
CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
CIRCUIT_BREAKER_SUCCESS_THRESHOLD: int = 2
CIRCUIT_BREAKER_TIMEOUT: float = 60.0
CIRCUIT_BREAKER_WINDOW: float = 60.0

# Load Shedding
LOAD_SHEDDING_ENABLED: bool = True
CPU_THRESHOLD_ELEVATED: float = 70.0
CPU_THRESHOLD_HIGH: float = 85.0
CPU_THRESHOLD_CRITICAL: float = 95.0
MEMORY_THRESHOLD_ELEVATED: float = 75.0
MEMORY_THRESHOLD_HIGH: float = 90.0
MEMORY_THRESHOLD_CRITICAL: float = 95.0
```

Override via environment variables:
```bash
export RATE_LIMIT_PER_MINUTE=20
export DAILY_TOKEN_LIMIT=2000000
export CIRCUIT_BREAKER_FAILURE_THRESHOLD=10
```

## Testing

### Test Rate Limiter

```bash
# Make 11 requests rapidly
for i in {1..11}; do
  curl -X POST http://localhost:8000/api/v1/chat \
    -H "Content-Type: application/json" \
    -d '{"query": "test", "user_id": "test_user"}'
  echo "Request $i"
done

# 11th request should return 429
```

### Test Quota

```sql
-- Set high token usage for user
UPDATE chat_interactions
SET total_tokens = 1100000
WHERE user_id = 'test_user' 
AND created_at >= CURRENT_DATE;

-- Next chat request should return 429
```

### Test Circuit Breaker

```python
# Simulate Gemini failures
# (Could mock generator to raise exceptions)

import asyncio
from app.services.protection import CircuitBreaker, CircuitBreakerConfig

async def failing_function():
    raise Exception("Gemini API error")

breaker = CircuitBreaker(
    "test",
    CircuitBreakerConfig(failure_threshold=3, timeout=10.0),
)

# Call 3 times to open circuit
for i in range(3):
    try:
        await breaker.call(failing_function)
    except:
        print(f"Attempt {i+1} failed")

# Next call should immediately fail with CircuitBreakerOpenError
try:
    await breaker.call(failing_function)
except CircuitBreakerOpenError:
    print("Circuit is open!")
```

### Test Load Shedding

```python
# Simulate CPU load
import multiprocessing

def cpu_load():
    while True:
        pass

# Spawn processes to max CPU
processes = []
for _ in range(multiprocessing.cpu_count()):
    p = multiprocessing.Process(target=cpu_load)
    p.start()
    processes.append(p)

# Make chat request - should see degraded parameters in logs

# Cleanup
for p in processes:
    p.terminate()
```

## Best Practices

1. **Rate Limiting**:
   - Set limits based on expected user behavior
   - Consider different tiers for different users
   - Monitor false positives

2. **Quotas**:
   - Set realistic daily limits
   - Provide clear quota information to users
   - Consider hourly quotas for bursty traffic

3. **Circuit Breaker**:
   - Use separate breakers for different services
   - Set appropriate failure thresholds
   - Monitor breaker state changes
   - Alert on frequent trips

4. **Load Shedding**:
   - Test degraded performance
   - Communicate degradation to users
   - Monitor degradation frequency
   - Consider queueing instead of pure shedding

## Troubleshooting

### Rate Limit Issues

**Problem**: Legitimate users hitting rate limit

**Solutions**:
- Increase RATE_LIMIT_PER_MINUTE
- Implement user tiers
- Add exemptions for specific users
- Check for retry loops

### Quota Issues

**Problem**: Power users exceeding quota early

**Solutions**:
- Increase DAILY_TOKEN_LIMIT
- Implement quota tiers
- Add quota purchase options
- Optimize queries to use fewer tokens

### Circuit Breaker Stuck Open

**Problem**: Circuit not recovering

**Solutions**:
- Verify Gemini API is actually working
- Reduce SUCCESS_THRESHOLD
- Increase TIMEOUT for longer recovery window
- Manually reset circuit: `breaker.reset()`

### Excessive Load Shedding

**Problem**: System constantly in degraded mode

**Solutions**:
- Scale infrastructure (more CPU/memory)
- Optimize retrieval/generation
- Increase load thresholds
- Implement request queueing

## Future Enhancements

Potential additions:

1. **Distributed Rate Limiting**: Redis cluster support
2. **Adaptive Quotas**: Dynamic limits based on usage patterns
3. **Bulkhead Pattern**: Isolate resources per user
4. **Request Prioritization**: Queue management with priorities
5. **Graceful Shutdown**: Drain connections before restart
6. **Health Checks**: Automated health endpoints
7. **Metrics Export**: Prometheus/Grafana integration
