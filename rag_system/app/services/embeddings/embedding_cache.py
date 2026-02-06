"""Redis-based embedding cache for deduplication."""
import json
from typing import Optional, List
from app.db.redis import RedisClient
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingCache:
    """Redis-based cache for storing and retrieving embeddings."""
    
    CACHE_PREFIX = "embedding"
    CACHE_TTL = 7 * 24 * 60 * 60  # 7 days in seconds
    
    def __init__(self, redis_client: RedisClient):
        """
        Initialize embedding cache.
        
        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client
        logger.debug("EmbeddingCache initialized")
    
    def _get_cache_key(self, content_hash: str) -> str:
        """
        Generate Redis key for embedding.
        
        Args:
            content_hash: SHA256 hash of content
            
        Returns:
            str: Redis key
        """
        return f"{self.CACHE_PREFIX}:{content_hash}"
    
    async def get(self, content_hash: str) -> Optional[List[float]]:
        """
        Retrieve embedding from cache.
        
        Args:
            content_hash: SHA256 hash of content
            
        Returns:
            Optional[List[float]]: Embedding vector or None if not found
        """
        cache_key = self._get_cache_key(content_hash)
        
        try:
            cached_value = await self.redis.get(cache_key)
            
            if cached_value:
                # Parse JSON embedding
                embedding = json.loads(cached_value)
                
                logger.debug(
                    f"Cache HIT",
                    extra={
                        "content_hash": content_hash[:16],
                        "embedding_dim": len(embedding),
                    }
                )
                
                return embedding
            
            logger.debug(
                f"Cache MISS",
                extra={"content_hash": content_hash[:16]}
            )
            
            return None
            
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to decode cached embedding: {str(e)}",
                extra={"content_hash": content_hash[:16]},
                exc_info=True,
            )
            return None
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve embedding from cache: {str(e)}",
                extra={"content_hash": content_hash[:16]},
                exc_info=True,
            )
            return None
    
    async def set(
        self,
        content_hash: str,
        embedding: List[float],
        ttl: int = None,
    ) -> bool:
        """
        Store embedding in cache.
        
        Args:
            content_hash: SHA256 hash of content
            embedding: Embedding vector
            ttl: Time to live in seconds (optional)
            
        Returns:
            bool: True if stored successfully
        """
        cache_key = self._get_cache_key(content_hash)
        ttl = ttl or self.CACHE_TTL
        
        try:
            # Serialize embedding as JSON
            embedding_json = json.dumps(embedding)
            
            # Store in Redis with TTL
            success = await self.redis.set(cache_key, embedding_json, ex=ttl)
            
            if success:
                logger.debug(
                    f"Embedding cached",
                    extra={
                        "content_hash": content_hash[:16],
                        "embedding_dim": len(embedding),
                        "ttl": ttl,
                    }
                )
            
            return success
            
        except Exception as e:
            logger.error(
                f"Failed to cache embedding: {str(e)}",
                extra={"content_hash": content_hash[:16]},
                exc_info=True,
            )
            return False
    
    async def get_batch(
        self,
        content_hashes: List[str]
    ) -> dict[str, Optional[List[float]]]:
        """
        Retrieve multiple embeddings from cache.
        
        Args:
            content_hashes: List of content hashes
            
        Returns:
            dict: Mapping of content_hash to embedding (or None)
        """
        results = {}
        
        for content_hash in content_hashes:
            embedding = await self.get(content_hash)
            results[content_hash] = embedding
        
        # Calculate cache hit rate
        hits = sum(1 for v in results.values() if v is not None)
        hit_rate = (hits / len(content_hashes) * 100) if content_hashes else 0
        
        logger.info(
            f"Batch cache lookup",
            extra={
                "total": len(content_hashes),
                "hits": hits,
                "misses": len(content_hashes) - hits,
                "hit_rate_percent": round(hit_rate, 2),
            }
        )
        
        return results
    
    async def set_batch(
        self,
        embeddings_map: dict[str, List[float]],
        ttl: int = None,
    ) -> int:
        """
        Store multiple embeddings in cache.
        
        Args:
            embeddings_map: Mapping of content_hash to embedding
            ttl: Time to live in seconds (optional)
            
        Returns:
            int: Number of embeddings successfully cached
        """
        success_count = 0
        
        for content_hash, embedding in embeddings_map.items():
            if await self.set(content_hash, embedding, ttl):
                success_count += 1
        
        logger.info(
            f"Batch cache store",
            extra={
                "total": len(embeddings_map),
                "success": success_count,
                "failed": len(embeddings_map) - success_count,
            }
        )
        
        return success_count
    
    async def delete(self, content_hash: str) -> bool:
        """
        Delete embedding from cache.
        
        Args:
            content_hash: SHA256 hash of content
            
        Returns:
            bool: True if deleted
        """
        cache_key = self._get_cache_key(content_hash)
        
        try:
            deleted = await self.redis.delete(cache_key)
            
            if deleted:
                logger.debug(
                    f"Embedding deleted from cache",
                    extra={"content_hash": content_hash[:16]}
                )
            
            return deleted > 0
            
        except Exception as e:
            logger.error(
                f"Failed to delete embedding from cache: {str(e)}",
                extra={"content_hash": content_hash[:16]},
                exc_info=True,
            )
            return False
