"""
Circuit breaker pattern implementation for external service protection.

This module prevents cascading failures by opening circuit after repeated failures.
"""

import logging
import time
from typing import Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit tripped, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    
    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 2  # Successes to close circuit from half-open
    timeout: float = 60.0  # Seconds before attempting recovery
    window: float = 60.0  # Time window for counting failures


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.
    
    States:
    - CLOSED: All requests pass through normally
    - OPEN: All requests fail immediately without calling service
    - HALF_OPEN: Limited requests allowed to test recovery
    
    Transitions:
    - CLOSED -> OPEN: After failure_threshold failures in window
    - OPEN -> HALF_OPEN: After timeout period
    - HALF_OPEN -> CLOSED: After success_threshold successes
    - HALF_OPEN -> OPEN: On any failure
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name (for logging)
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.opened_at: Optional[float] = None
        
        # Track failures in time window
        self.failure_times: list[float] = []
        
        logger.info(
            f"CircuitBreaker '{name}' initialized",
            extra={
                "name": name,
                "failure_threshold": self.config.failure_threshold,
                "timeout": self.config.timeout,
                "window": self.config.window,
            },
        )
    
    def _clean_old_failures(self) -> None:
        """Remove failures outside the time window."""
        current_time = time.time()
        cutoff_time = current_time - self.config.window
        
        self.failure_times = [
            t for t in self.failure_times
            if t > cutoff_time
        ]
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should transition from OPEN to HALF_OPEN."""
        if self.state != CircuitState.OPEN:
            return False
        
        if self.opened_at is None:
            return False
        
        elapsed = time.time() - self.opened_at
        return elapsed >= self.config.timeout
    
    def _record_success(self) -> None:
        """Record successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.config.success_threshold:
                # Close circuit
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.failure_times = []
                self.opened_at = None
                
                logger.info(
                    f"CircuitBreaker '{self.name}' CLOSED",
                    extra={
                        "name": self.name,
                        "previous_state": "HALF_OPEN",
                        "success_count": self.success_count,
                    },
                )
    
    def _record_failure(self) -> None:
        """Record failed request."""
        current_time = time.time()
        self.last_failure_time = current_time
        self.failure_times.append(current_time)
        
        # Clean old failures
        self._clean_old_failures()
        
        if self.state == CircuitState.HALF_OPEN:
            # Any failure in HALF_OPEN reopens circuit
            self.state = CircuitState.OPEN
            self.opened_at = current_time
            self.success_count = 0
            
            logger.warning(
                f"CircuitBreaker '{self.name}' reopened",
                extra={
                    "name": self.name,
                    "previous_state": "HALF_OPEN",
                },
            )
        
        elif self.state == CircuitState.CLOSED:
            # Check if threshold exceeded
            if len(self.failure_times) >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = current_time
                
                logger.error(
                    f"CircuitBreaker '{self.name}' OPENED",
                    extra={
                        "name": self.name,
                        "failure_count": len(self.failure_times),
                        "threshold": self.config.failure_threshold,
                        "window": self.config.window,
                    },
                )
    
    async def call(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception from function
        """
        # Check if should attempt reset
        if self._should_attempt_reset():
            self.state = CircuitState.HALF_OPEN
            self.success_count = 0
            
            logger.info(
                f"CircuitBreaker '{self.name}' entering HALF_OPEN",
                extra={"name": self.name},
            )
        
        # Check current state
        if self.state == CircuitState.OPEN:
            logger.warning(
                f"CircuitBreaker '{self.name}' is OPEN, rejecting request",
                extra={
                    "name": self.name,
                    "opened_at": self.opened_at,
                    "elapsed": time.time() - self.opened_at if self.opened_at else None,
                },
            )
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open"
            )
        
        # Attempt call
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self._record_success()
            return result
            
        except Exception as e:
            self._record_failure()
            
            logger.error(
                f"CircuitBreaker '{self.name}' recorded failure",
                extra={
                    "name": self.name,
                    "state": self.state.value,
                    "failure_count": len(self.failure_times),
                    "error": str(e),
                },
            )
            
            raise
    
    def get_state(self) -> dict:
        """
        Get current circuit breaker state.
        
        Returns:
            Dictionary with state information
        """
        self._clean_old_failures()
        
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": len(self.failure_times),
            "failure_threshold": self.config.failure_threshold,
            "success_count": self.success_count,
            "success_threshold": self.config.success_threshold,
            "opened_at": self.opened_at,
            "last_failure_time": self.last_failure_time,
            "time_until_half_open": (
                max(0, self.config.timeout - (time.time() - self.opened_at))
                if self.opened_at and self.state == CircuitState.OPEN
                else None
            ),
        }
    
    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.failure_times = []
        self.opened_at = None
        self.last_failure_time = None
        
        logger.info(
            f"CircuitBreaker '{self.name}' manually reset",
            extra={"name": self.name},
        )


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreakerManager:
    """Manage multiple circuit breakers."""
    
    def __init__(self):
        """Initialize circuit breaker manager."""
        self.breakers: dict[str, CircuitBreaker] = {}
        logger.info("CircuitBreakerManager initialized")
    
    def get_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """
        Get or create circuit breaker.
        
        Args:
            name: Circuit breaker name
            config: Optional configuration
            
        Returns:
            CircuitBreaker instance
        """
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name, config)
            logger.info(
                f"Created new circuit breaker: {name}",
                extra={"name": name},
            )
        
        return self.breakers[name]
    
    def get_all_states(self) -> dict[str, dict]:
        """
        Get state of all circuit breakers.
        
        Returns:
            Dictionary mapping breaker names to states
        """
        return {
            name: breaker.get_state()
            for name, breaker in self.breakers.items()
        }
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self.breakers.values():
            breaker.reset()
        
        logger.info("All circuit breakers reset")
