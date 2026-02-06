"""Query transformation for improved retrieval."""
from typing import List, Optional
import asyncio

from app.services.embeddings import EmbeddingService, EmbeddingCache, TaskType
from app.db.redis import redis_client
from app.core.logging import get_logger

logger = get_logger(__name__)


class QueryTransformer:
    """
    Transform user queries for optimal retrieval.
    
    Features:
    - Query embedding with caching
    - Query normalization
    - Stop word handling
    - Query expansion (future)
    """
    
    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        embedding_cache: Optional[EmbeddingCache] = None,
    ):
        """
        Initialize query transformer.
        
        Args:
            embedding_service: Embedding service instance
            embedding_cache: Embedding cache instance
        """
        self.embedding_service = embedding_service or EmbeddingService()
        self.embedding_cache = embedding_cache or EmbeddingCache(redis_client)
        
        logger.info("QueryTransformer initialized")
    
    async def transform(self, query: str) -> dict:
        """
        Transform query into normalized form with embedding.
        
        Args:
            query: User query string
            
        Returns:
            dict: {
                "original_query": str,
                "normalized_query": str,
                "embedding": List[float],
                "terms": List[str],
            }
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        logger.info(
            f"Transforming query",
            extra={"query_preview": query[:100]}
        )
        
        # Normalize query
        normalized_query = self._normalize_query(query)
        
        # Extract search terms
        terms = self._extract_terms(normalized_query)
        
        # Generate embedding
        embedding = await self._embed_query(normalized_query)
        
        logger.info(
            f"Query transformation complete",
            extra={
                "original_length": len(query),
                "normalized_length": len(normalized_query),
                "terms_count": len(terms),
                "embedding_dim": len(embedding),
            }
        )
        
        return {
            "original_query": query,
            "normalized_query": normalized_query,
            "embedding": embedding,
            "terms": terms,
        }
    
    def _normalize_query(self, query: str) -> str:
        """
        Normalize query text.
        
        Args:
            query: Raw query string
            
        Returns:
            str: Normalized query
        """
        # Remove extra whitespace
        normalized = " ".join(query.split())
        
        # Lowercase for consistency (embeddings are case-insensitive)
        normalized = normalized.lower()
        
        return normalized
    
    def _extract_terms(self, query: str) -> List[str]:
        """
        Extract search terms from query.
        
        Args:
            query: Normalized query string
            
        Returns:
            List[str]: Search terms
        """
        # Simple whitespace tokenization
        # PostgreSQL's to_tsquery will handle stop words
        terms = query.split()
        
        # Remove very short terms (likely not meaningful)
        terms = [t for t in terms if len(t) >= 2]
        
        return terms
    
    async def _embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for query with caching.
        
        Args:
            query: Query string
            
        Returns:
            List[float]: Query embedding vector
        """
        # Compute content hash for cache key
        import hashlib
        content_hash = hashlib.sha256(query.encode()).hexdigest()
        
        # Check cache first
        cached_embedding = await self.embedding_cache.get(content_hash)
        
        if cached_embedding:
            logger.debug(
                f"Query embedding cache hit",
                extra={"query_hash": content_hash[:16]}
            )
            return cached_embedding
        
        # Generate embedding using RETRIEVAL_QUERY task type
        logger.debug(
            f"Generating query embedding",
            extra={"query_hash": content_hash[:16]}
        )
        
        embeddings = self.embedding_service.gemini_client.embed_texts(
            texts=[query],
            task_type=TaskType.RETRIEVAL_QUERY,
        )
        
        embedding = embeddings[0]
        
        # Cache the embedding
        await self.embedding_cache.set(content_hash, embedding)
        
        logger.debug(
            f"Query embedding cached",
            extra={"query_hash": content_hash[:16]}
        )
        
        return embedding
