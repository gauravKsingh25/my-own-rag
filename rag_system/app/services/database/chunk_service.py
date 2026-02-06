"""Database service for chunk operations."""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import insert

from app.db.models import Chunk
from app.services.embeddings import EmbeddedChunk
from app.core.logging import get_logger

logger = get_logger(__name__)


class ChunkService:
    """Service for chunk database operations."""
    
    @staticmethod
    async def store_chunks(
        embedded_chunks: List[EmbeddedChunk],
        document_id: UUID,
        user_id: str,
        db: AsyncSession,
    ) -> int:
        """
        Store chunks in database with tsvector generation.
        
        Args:
            embedded_chunks: Chunks with embeddings
            document_id: Document UUID
            user_id: User ID
            db: Database session
            
        Returns:
            int: Number of chunks stored
        """
        if not embedded_chunks:
            logger.warning("No chunks to store")
            return 0
        
        logger.info(
            f"Storing chunks in database",
            extra={
                "document_id": str(document_id),
                "user_id": user_id,
                "chunks": len(embedded_chunks),
            }
        )
        
        # Prepare chunk records
        chunk_records = []
        
        for embedded_chunk in embedded_chunks:
            chunk = embedded_chunk.chunk
            
            chunk_record = {
                "document_id": document_id,
                "user_id": user_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "content_hash": chunk.content_hash,
                "token_count": chunk.token_count,
                "section_title": chunk.section_title,
                "page_number": chunk.page_number,
                "hierarchy": chunk.hierarchy,
            }
            
            chunk_records.append(chunk_record)
        
        # Use bulk insert with ON CONFLICT DO NOTHING for idempotency
        stmt = insert(Chunk).values(chunk_records)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["document_id", "chunk_index"]
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        inserted_count = result.rowcount
        
        logger.info(
            f"Chunks stored in database",
            extra={
                "document_id": str(document_id),
                "inserted": inserted_count,
                "total": len(embedded_chunks),
            }
        )
        
        # Update tsvector for full-text search
        await ChunkService.update_tsvectors(document_id, db)
        
        return inserted_count
    
    @staticmethod
    async def update_tsvectors(
        document_id: UUID,
        db: AsyncSession,
    ):
        """
        Update tsvector column for chunks of a document.
        
        Args:
            document_id: Document UUID
            db: Database session
        """
        logger.info(
            f"Updating tsvectors for document",
            extra={"document_id": str(document_id)}
        )
        
        # Update tsvector using PostgreSQL to_tsvector function
        # This creates a weighted text search vector:
        # - Section title weight: A (highest)
        # - Content weight: B
        stmt = text("""
            UPDATE chunks
            SET content_tsvector = 
                setweight(to_tsvector('english', COALESCE(section_title, '')), 'A') ||
                setweight(to_tsvector('english', content), 'B')
            WHERE document_id = :document_id
        """)
        
        await db.execute(stmt, {"document_id": str(document_id)})
        await db.commit()
        
        logger.info(
            f"Tsvectors updated for document",
            extra={"document_id": str(document_id)}
        )
    
    @staticmethod
    async def delete_by_document_id(
        document_id: UUID,
        db: AsyncSession,
    ):
        """
        Delete all chunks for a document.
        
        Args:
            document_id: Document UUID
            db: Database session
        """
        logger.info(
            f"Deleting chunks for document",
            extra={"document_id": str(document_id)}
        )
        
        stmt = select(func.count()).select_from(Chunk).where(
            Chunk.document_id == document_id
        )
        result = await db.execute(stmt)
        count_before = result.scalar()
        
        # Delete chunks (CASCADE will handle vector deletion)
        stmt = text("DELETE FROM chunks WHERE document_id = :document_id")
        await db.execute(stmt, {"document_id": str(document_id)})
        await db.commit()
        
        logger.info(
            f"Chunks deleted for document",
            extra={
                "document_id": str(document_id),
                "deleted": count_before,
            }
        )
    
    @staticmethod
    async def get_by_ids(
        chunk_ids: List[UUID],
        db: AsyncSession,
    ) -> List[Chunk]:
        """
        Get chunks by IDs.
        
        Args:
            chunk_ids: List of chunk UUIDs
            db: Database session
            
        Returns:
            List[Chunk]: Chunks
        """
        if not chunk_ids:
            return []
        
        stmt = select(Chunk).where(Chunk.id.in_(chunk_ids))
        result = await db.execute(stmt)
        chunks = result.scalars().all()
        
        return list(chunks)
