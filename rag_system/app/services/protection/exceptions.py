"""Protection layer exceptions."""


class ProtectionError(Exception):
    """Base exception for protection layer."""
    pass


class RateLimitExceededError(ProtectionError):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: int):
        """
        Initialize rate limit error.
        
        Args:
            message: Error message
            retry_after: Seconds until retry is allowed
        """
        super().__init__(message)
        self.retry_after = retry_after


class QuotaExceededError(ProtectionError):
    """Raised when daily quota is exceeded."""
    
    def __init__(self, message: str, reset_time: str):
        """
        Initialize quota exceeded error.
        
        Args:
            message: Error message
            reset_time: ISO format timestamp of quota reset
        """
        super().__init__(message)
        self.reset_time = reset_time


class CircuitBreakerOpenError(ProtectionError):
    """Raised when circuit breaker is open."""
    pass


class LoadSheddingError(ProtectionError):
    """Raised when system is shedding load (unlikely, we degrade instead)."""
    pass
