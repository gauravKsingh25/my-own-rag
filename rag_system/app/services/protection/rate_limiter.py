"""
Rate limiting service using Redis token bucket algorithm.

This module provides rate limiting to prevent abuse and ensure fair resource usage.
"""

import logging
import time
from typing import Optional, Tuple
from dataclasses import dataclass
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    
    allowed: bool
    remaining: int
    reset_time: float
    retry_after: Optional[int] = None


class RateLimiter:
    """
    Redis-based token bucket rate limiter.
    
    Implements per-user rate limiting using the token bucket algorithm.
    Tokens are refilled at a constant rate, and each request consumes one token.
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        rate: int = 10,  # requests per window
        window: int = 60,  # window in seconds
    ):
        """
        Initialize rate limiter.
        
        Args:
            redis_client: Redis client instance (optional)
            rate: Number of requests allowed per window
            window: Time window in seconds
        """
        self.redis_client = redis_client
        self.rate = rate
        self.window = window
        
        logger.info(
            "RateLimiter initialized",
            extra={
                "rate": rate,
                "window": window,
            },
        )
    
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        return self.redis_client
    
    def _get_key(self, user_id: str) -> str:
        """
        Generate Redis key for user rate limit.
        
        Args:
            user_id: User identifier
            
        Returns:
            Redis key
        """
        return f"rate_limit:{user_id}"
    
    async def check_rate_limit(self, user_id: str) -> RateLimitResult:
        """
        Check if request is within rate limit.
        
        Uses token bucket algorithm:
        1. Check current token count
        2. Calculate tokens to add based on time elapsed
        3. If tokens available, consume one and allow request
        4. If no tokens, deny request and return retry time
        
        Args:
            user_id: User identifier
            
        Returns:
            RateLimitResult with allowed status and metadata
        """
        try:
            redis_client = await self._get_redis()
            key = self._get_key(user_id)
            current_time = time.time()
            
            # Use Lua script for atomic token bucket operation
            lua_script = """
            local key = KEYS[1]
            local rate = tonumber(ARGV[1])
            local window = tonumber(ARGV[2])
            local current_time = tonumber(ARGV[3])
            
            -- Get current bucket state
            local bucket = redis.call('HGETALL', key)
            local tokens = rate
            local last_refill = current_time
            
            if #bucket > 0 then
                -- Parse existing bucket
                for i = 1, #bucket, 2 do
                    if bucket[i] == 'tokens' then
                        tokens = tonumber(bucket[i + 1])
                    elseif bucket[i] == 'last_refill' then
                        last_refill = tonumber(bucket[i + 1])
                    end
                end
                
                -- Calculate tokens to add based on time elapsed
                local time_elapsed = current_time - last_refill
                local tokens_to_add = (time_elapsed / window) * rate
                tokens = math.min(rate, tokens + tokens_to_add)
            end
            
            -- Try to consume one token
            if tokens >= 1 then
                tokens = tokens - 1
                redis.call('HSET', key, 'tokens', tokens, 'last_refill', current_time)
                redis.call('EXPIRE', key, window * 2)
                return {1, math.floor(tokens), 0}  -- allowed, remaining, retry_after
            else
                -- Calculate retry after time
                local tokens_needed = 1 - tokens
                local retry_after = math.ceil((tokens_needed / rate) * window)
                return {0, 0, retry_after}  -- not allowed, 0 remaining, retry_after
            end
            """
            
            result = await redis_client.eval(
                lua_script,
                1,
                key,
                str(self.rate),
                str(self.window),
                str(current_time),
            )
            
            allowed = bool(result[0])
            remaining = int(result[1])
            retry_after = int(result[2]) if result[2] > 0 else None
            
            # Calculate reset time
            reset_time = current_time + self.window
            
            rate_limit_result = RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=retry_after,
            )
            
            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for user {user_id}",
                    extra={
                        "user_id": user_id,
                        "retry_after": retry_after,
                        "rate": self.rate,
                        "window": self.window,
                    },
                )
            else:
                logger.debug(
                    f"Rate limit check passed",
                    extra={
                        "user_id": user_id,
                        "remaining": remaining,
                    },
                )
            
            return rate_limit_result
            
        except Exception as e:
            logger.error(
                f"Rate limit check failed: {str(e)}",
                extra={
                    "user_id": user_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            
            # Fail open - allow request if rate limiter is broken
            return RateLimitResult(
                allowed=True,
                remaining=self.rate,
                reset_time=time.time() + self.window,
                retry_after=None,
            )
    
    async def reset_limit(self, user_id: str) -> bool:
        """
        Reset rate limit for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if reset successful
        """
        try:
            redis_client = await self._get_redis()
            key = self._get_key(user_id)
            await redis_client.delete(key)
            
            logger.info(
                f"Rate limit reset for user {user_id}",
                extra={"user_id": user_id},
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to reset rate limit: {str(e)}",
                extra={"user_id": user_id},
                exc_info=True,
            )
            return False
    
    async def get_limit_info(self, user_id: str) -> dict:
        """
        Get current rate limit information for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with rate limit info
        """
        try:
            redis_client = await self._get_redis()
            key = self._get_key(user_id)
            
            bucket = await redis_client.hgetall(key)
            
            if bucket:
                tokens = float(bucket.get('tokens', self.rate))
                last_refill = float(bucket.get('last_refill', time.time()))
                
                # Calculate current tokens
                current_time = time.time()
                time_elapsed = current_time - last_refill
                tokens_to_add = (time_elapsed / self.window) * self.rate
                current_tokens = min(self.rate, tokens + tokens_to_add)
                
                return {
                    "user_id": user_id,
                    "rate": self.rate,
                    "window": self.window,
                    "current_tokens": int(current_tokens),
                    "max_tokens": self.rate,
                    "last_refill": last_refill,
                }
            else:
                return {
                    "user_id": user_id,
                    "rate": self.rate,
                    "window": self.window,
                    "current_tokens": self.rate,
                    "max_tokens": self.rate,
                    "last_refill": None,
                }
                
        except Exception as e:
            logger.error(
                f"Failed to get rate limit info: {str(e)}",
                extra={"user_id": user_id},
                exc_info=True,
            )
            return {}
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("RateLimiter Redis connection closed")
