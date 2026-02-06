"""Protection and stability layer services."""

from app.services.protection.rate_limiter import RateLimiter, RateLimitResult
from app.services.protection.quota_manager import QuotaManager, QuotaStatus
from app.services.protection.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerManager,
    CircuitBreakerConfig,
    CircuitState,
)
from app.services.protection.load_shedder import (
    LoadShedder,
    LoadMetrics,
    LoadLevel,
    DegradationConfig,
)
from app.services.protection.exceptions import (
    ProtectionError,
    RateLimitExceededError,
    QuotaExceededError,
    CircuitBreakerOpenError,
    LoadSheddingError,
)

__all__ = [
    # Rate limiting
    "RateLimiter",
    "RateLimitResult",
    
    # Quota management
    "QuotaManager",
    "QuotaStatus",
    
    # Circuit breaker
    "CircuitBreaker",
    "CircuitBreakerManager",
    "CircuitBreakerConfig",
    "CircuitState",
    
    # Load shedding
    "LoadShedder",
    "LoadMetrics",
    "LoadLevel",
    "DegradationConfig",
    
    # Exceptions
    "ProtectionError",
    "RateLimitExceededError",
    "QuotaExceededError",
    "CircuitBreakerOpenError",
    "LoadSheddingError",
]
