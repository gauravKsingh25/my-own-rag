"""Embedding service for generating and caching embeddings."""
from typing import List, Dict, Tuple
from dataclasses import dataclass

from app.services.chunking.models import Chunk
from app.services.embeddings.gemini_client import GeminiEmbeddingClient, TaskType
from app.services.embeddings.embedding_cache import EmbeddingCache
from app.db.redis import redis_client
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EmbeddedChunk:
    """Chunk with its embedding vector."""
    
    chunk: Chunk
    embedding: List[float]


class EmbeddingService:
    """
    Service for generating embeddings with caching and deduplication.
    
    Features:
    - Deduplication by content hash
    - Redis caching for reuse
    - Batch processing
    - Progress tracking
    """
    
    def __init__(
        self,
        gemini_client: GeminiEmbeddingClient = None,
        embedding_cache: EmbeddingCache = None,
    ):
        """
        Initialize embedding service.
        
        Args:
            gemini_client: Gemini client instance (optional)
            embedding_cache: Embedding cache instance (optional)
        """
        self.gemini_client = gemini_client or GeminiEmbeddingClient()
        self.embedding_cache = embedding_cache or EmbeddingCache(redis_client)
        
        logger.info("EmbeddingService initialized")
    
    async def embed_chunks(
        self,
        chunks: List[Chunk],
        task_type: str = TaskType.RETRIEVAL_DOCUMENT,
    ) -> List[EmbeddedChunk]:
        """
        Generate embeddings for chunks with caching and deduplication.
        
        Workflow:
        1. Deduplicate chunks by content_hash
        2. Check cache for existing embeddings
        3. Generate embeddings for cache misses
        4. Cache new embeddings
        5. Attach embeddings to chunks
        6. Return enriched chunks
        
        Args:
            chunks: List of chunks to embed
            task_type: Gemini task type for embeddings
            
        Returns:
            List[EmbeddedChunk]: Chunks with embeddings attached
        """
        if not chunks:
            logger.warning("No chunks provided for embedding")
            return []
        
        logger.info(
            f"Starting embedding generation",
            extra={
                "total_chunks": len(chunks),
                "task_type": task_type,
            }
        )
        
        # Step 1: Deduplicate by content hash
        unique_chunks_map, hash_to_chunks = self._deduplicate_chunks(chunks)
        
        logger.info(
            f"Deduplication complete",
            extra={
                "original_chunks": len(chunks),
                "unique_chunks": len(unique_chunks_map),
                "dedup_ratio": round((1 - len(unique_chunks_map) / len(chunks)) * 100, 2) if chunks else 0,
            }
        )
        
        # Step 2: Check cache
        cached_embeddings = await self.embedding_cache.get_batch(
            list(unique_chunks_map.keys())
        )
        
        # Separate cached and missing
        cached_hashes = {h for h, emb in cached_embeddings.items() if emb is not None}
        missing_hashes = [h for h in unique_chunks_map.keys() if h not in cached_hashes]
        
        logger.info(
            f"Cache lookup complete",
            extra={
                "cached": len(cached_hashes),
                "missing": len(missing_hashes),
                "cache_hit_rate": round(len(cached_hashes) / len(unique_chunks_map) * 100, 2) if unique_chunks_map else 0,
            }
        )
        
        # Step 3: Generate embeddings for missing chunks
        new_embeddings = {}
        
        if missing_hashes:
            # Prepare texts for embedding
            texts_to_embed = [
                unique_chunks_map[h].content
                for h in missing_hashes
            ]
            
            # Generate embeddings
            try:
                embeddings = self.gemini_client.embed_texts(
                    texts=texts_to_embed,
                    task_type=task_type,
                )
                
                # Map embeddings to hashes
                for hash_val, embedding in zip(missing_hashes, embeddings):
                    new_embeddings[hash_val] = embedding
                
                logger.info(
                    f"New embeddings generated",
                    extra={
                        "count": len(new_embeddings),
                        "embedding_dim": len(embeddings[0]) if embeddings else 0,
                    }
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to generate embeddings: {str(e)}",
                    extra={"missing_count": len(missing_hashes)},
                    exc_info=True,
                )
                raise
        
        # Step 4: Cache new embeddings
        if new_embeddings:
            cached_count = await self.embedding_cache.set_batch(new_embeddings)
            logger.info(
                f"New embeddings cached",
                extra={
                    "cached": cached_count,
                    "total": len(new_embeddings),
                }
            )
        
        # Step 5: Combine cached and new embeddings
        all_embeddings = {**cached_embeddings, **new_embeddings}
        
        # Remove None values
        all_embeddings = {h: emb for h, emb in all_embeddings.items() if emb is not None}
        
        # Step 6: Attach embeddings to all original chunks
        embedded_chunks = []
        
        for chunk in chunks:
            content_hash = chunk.content_hash
            
            if content_hash in all_embeddings:
                embedded_chunk = EmbeddedChunk(
                    chunk=chunk,
                    embedding=all_embeddings[content_hash],
                )
                embedded_chunks.append(embedded_chunk)
            else:
                logger.warning(
                    f"No embedding found for chunk",
                    extra={
                        "chunk_index": chunk.chunk_index,
                        "content_hash": content_hash[:16],
                    }
                )
        
        logger.info(
            f"Embedding generation complete",
            extra={
                "total_chunks": len(chunks),
                "embedded_chunks": len(embedded_chunks),
                "unique_embeddings": len(all_embeddings),
                "from_cache": len(cached_hashes),
                "newly_generated": len(new_embeddings),
            }
        )
        
        return embedded_chunks
    
    def _deduplicate_chunks(
        self,
        chunks: List[Chunk]
    ) -> Tuple[Dict[str, Chunk], Dict[str, List[Chunk]]]:
        """
        Deduplicate chunks by content hash.
        
        Args:
            chunks: List of chunks
            
        Returns:
            Tuple containing:
                - Dict mapping content_hash to first occurrence of chunk
                - Dict mapping content_hash to all chunks with that hash
        """
        unique_chunks_map = {}
        hash_to_chunks = {}
        
        for chunk in chunks:
            content_hash = chunk.content_hash
            
            # Track all chunks with this hash
            if content_hash not in hash_to_chunks:
                hash_to_chunks[content_hash] = []
            hash_to_chunks[content_hash].append(chunk)
            
            # Keep first occurrence for embedding generation
            if content_hash not in unique_chunks_map:
                unique_chunks_map[content_hash] = chunk
        
        return unique_chunks_map, hash_to_chunks
