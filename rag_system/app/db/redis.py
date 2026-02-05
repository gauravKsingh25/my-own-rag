"""Redis async connection configuration."""
from typing import Optional
import redis.asyncio as aioredis
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    """Async Redis client wrapper."""
    
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
    
    async def connect(self) -> None:
        """Establish Redis connection."""
        try:
            self._redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
            )
            # Test connection
            await self._redis.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}", exc_info=True)
            raise
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")
    
    @property
    def client(self) -> aioredis.Redis:
        """Get Redis client instance."""
        if not self._redis:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return self._redis
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis."""
        return await self.client.get(key)
    
    async def set(
        self, 
        key: str, 
        value: str, 
        ex: Optional[int] = None
    ) -> bool:
        """Set value in Redis with optional expiration."""
        return await self.client.set(key, value, ex=ex)
    
    async def delete(self, key: str) -> int:
        """Delete key from Redis."""
        return await self.client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        return await self.client.exists(key) > 0
    
    async def ping(self) -> bool:
        """Ping Redis to check health."""
        try:
            return await self.client.ping()
        except Exception:
            return False


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency to get Redis client."""
    return redis_client
