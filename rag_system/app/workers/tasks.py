"""Celery tasks for document processing."""
import asyncio
from pathlib import Path
from uuid import UUID
from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from app.workers.celery_app import celery_app
from app.db.database import AsyncSessionLocal
from app.db.models import ProcessingStatus
from app.services.ingestion import ingestion_manager
from app.services.parsing import ParserFactory
from app.services.chunking import SemanticChunker, HierarchicalChunker
from app.services.embeddings import EmbeddingService, TaskType
from app.services.vector_store import VectorService
from app.services.database import ChunkService
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AsyncTask(Task):
    """Base task class that supports async operations."""
    
    def __call__(self, *args, **kwargs):
        """Execute task, handling async functions."""
        result = self.run(*args, **kwargs)
        if asyncio.iscoroutine(result):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(result)
        return result


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="tasks.process_document",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=8,  # Max 8 seconds
    retry_jitter=True,
)
async def process_document(self, document_id: str) -> dict:
    """
    Process uploaded document with parsing.
    
    This task:
    1. Updates status to PROCESSING
    2. Loads file from storage
    3. Parses document using appropriate parser
    4. Normalizes extracted content
    5. Updates status to PARSED
    6. On failure: Updates status to FAILED and retries with exponential backoff
    
    Args:
        document_id: Document UUID as string
        
    Returns:
        dict: Processing result with document_id, status, and parsing stats
        
    Retry strategy:
        - Exponential backoff: 1s, 2s, 4s, 8s (with jitter)
        - Max 3 retries
        - Automatic retry on any exception
    """
    doc_id = UUID(document_id)
    
    logger.info(
        f"Starting document processing",
        extra={
            "document_id": document_id,
            "task_id": self.request.id,
            "retry_count": self.request.retries,
        }
    )
    
    db: AsyncSession = None
    
    try:
        # Get database session
        db = AsyncSessionLocal()
        
        # Update status to PROCESSING
        await ingestion_manager.update_document_status(
            document_id=doc_id,
            status=ProcessingStatus.PROCESSING,
            db=db,
        )
        
        logger.info(
            f"Document status updated to PROCESSING",
            extra={"document_id": document_id}
        )
        
        # Get document metadata from database
        document = await ingestion_manager.get_document(doc_id, db)
        
        if not document:
            raise Exception(f"Document {document_id} not found in database")
        
        # Construct file path
        storage_base = Path(settings.STORAGE_BASE_PATH)
        file_path = storage_base / document.storage_path
        
        if not file_path.exists():
            raise Exception(f"Document file not found at {file_path}")
        
        logger.info(
            f"Loading document from storage",
            extra={
                "document_id": document_id,
                "file_path": str(file_path),
                "document_type": document.document_type,
            }
        )
        
        # Get appropriate parser
        parser = ParserFactory.get_parser(document.document_type)
        
        if not parser:
            raise Exception(
                f"No parser available for document type: {document.document_type}"
            )
        
        # Parse document
        logger.info(
            f"Parsing document",
            extra={
                "document_id": document_id,
                "parser": parser.__class__.__name__,
            }
        )
        
        parsed_doc = await parser.parse(
            file_path=file_path,
            document_id=doc_id,
        )
        
        # Log parsing statistics
        sections_count = parsed_doc.get_total_sections()
        total_chars = parsed_doc.get_total_content_length()
        
        logger.info(
            f"Document parsing completed",
            extra={
                "document_id": document_id,
                "sections_count": sections_count,
                "total_chars": total_chars,
                "total_pages": parsed_doc.total_pages,
            }
        )
        
        # Update status to PARSED
        await ingestion_manager.update_document_status(
            document_id=doc_id,
            status=ProcessingStatus.PARSED,
            db=db,
        )
        
        logger.info(
            f"Document status updated to PARSED",
            extra={"document_id": document_id}
        )
        
        # ============================================================
        # CHUNKING PHASE
        # ============================================================
        
        logger.info(
            f"Starting document chunking",
            extra={"document_id": document_id}
        )
        
        # Initialize semantic chunker
        chunker = SemanticChunker(
            max_tokens=500,
            overlap=100,
            min_chunk_tokens=50,
        )
        
        # Chunk the document
        chunked_doc = await chunker.chunk_document(
            parsed_doc=parsed_doc,
            filename=document.filename,
            version=document.version,
        )
        
        # Validate hierarchy
        hierarchy_valid = HierarchicalChunker.validate_hierarchy(
            chunked_doc=chunked_doc,
            parsed_doc=parsed_doc,
        )
        
        if not hierarchy_valid:
            logger.warning(
                f"Chunk hierarchy validation failed",
                extra={"document_id": document_id}
            )
        
        # Get hierarchy statistics
        hierarchy_stats = HierarchicalChunker.get_hierarchy_stats(
            chunked_doc=chunked_doc,
            parsed_doc=parsed_doc,
        )
        
        logger.info(
            f"Document chunking completed",
            extra={
                "document_id": document_id,
                "total_chunks": chunked_doc.get_total_chunks(),
                "total_tokens": chunked_doc.get_total_tokens(),
                "avg_chunk_size": chunked_doc.get_average_chunk_size(),
                **hierarchy_stats,
            }
        )
        
        # Update status to CHUNKED
        await ingestion_manager.update_document_status(
            document_id=doc_id,
            status=ProcessingStatus.CHUNKED,
            db=db,
        )
        
        logger.info(
            f"Document status updated to CHUNKED",
            extra={"document_id": document_id}
        )
        
        # ============================================================
        # EMBEDDING PHASE
        # ============================================================
        
        logger.info(
            f"Starting embedding generation",
            extra={"document_id": document_id}
        )
        
        # Initialize embedding service
        embedding_service = EmbeddingService()
        
        # Get all chunks from chunked document
        all_chunks = chunked_doc.get_all_chunks()
        
        # Generate embeddings with caching and deduplication
        embedded_chunks = await embedding_service.embed_chunks(
            chunks=all_chunks,
            task_type=TaskType.RETRIEVAL_DOCUMENT,
        )
        
        logger.info(
            f"Embedding generation completed",
            extra={
                "document_id": document_id,
                "chunks": len(all_chunks),
                "embedded_chunks": len(embedded_chunks),
            }
        )
        
        # Update status to EMBEDDED
        await ingestion_manager.update_document_status(
            document_id=doc_id,
            status=ProcessingStatus.EMBEDDED,
            db=db,
        )
        
        logger.info(
            f"Document status updated to EMBEDDED",
            extra={"document_id": document_id}
        )
        
        # ============================================================
        # VECTOR STORAGE PHASE
        # ============================================================
        
        logger.info(
            f"Starting vector storage",
            extra={"document_id": document_id}
        )
        
        # Initialize vector service
        vector_service = VectorService()
        
        # Store embedded chunks in Pinecone
        vectors_stored = vector_service.store_document_chunks(
            embedded_chunks=embedded_chunks,
            document_id=document_id,
            user_id=document.user_id,
        )
        
        logger.info(
            f"Vector storage completed",
            extra={
                "document_id": document_id,
                "vectors_stored": vectors_stored,
            }
        )
        
        # ============================================================
        # DATABASE STORAGE PHASE
        # ============================================================
        
        logger.info(
            f"Starting database chunk storage",
            extra={"document_id": document_id}
        )
        
        # Store chunks in database with tsvector for full-text search
        chunks_stored = await ChunkService.store_chunks(
            embedded_chunks=embedded_chunks,
            document_id=doc_id,
            user_id=document.user_id,
            db=db,
        )
        
        logger.info(
            f"Database chunk storage completed",
            extra={
                "document_id": document_id,
                "chunks_stored": chunks_stored,
            }
        )
        
        # Update status to COMPLETED
        await ingestion_manager.update_document_status(
            document_id=doc_id,
            status=ProcessingStatus.COMPLETED,
            db=db,
        )
        
        logger.info(
            f"Document processing completed successfully",
            extra={
                "document_id": document_id,
                "task_id": self.request.id,
                "final_status": "COMPLETED",
            }
        )
        
        return {
            "document_id": document_id,
            "status": "COMPLETED",
            "task_id": self.request.id,
            "sections_count": sections_count,
            "total_chars": total_chars,
            "total_pages": parsed_doc.total_pages,
            "chunks_count": chunked_doc.get_total_chunks(),
            "total_tokens": chunked_doc.get_total_tokens(),
            "embedded_chunks": len(embedded_chunks),
            "vectors_stored": vectors_stored,
        }
        
    except Exception as e:
        logger.error(
            f"Document processing failed: {str(e)}",
            extra={
                "document_id": document_id,
                "task_id": self.request.id,
                "retry_count": self.request.retries,
            },
            exc_info=True,
        )
        
        # Update status to FAILED if this is the last retry
        if self.request.retries >= self.max_retries:
            try:
                if db:
                    await ingestion_manager.update_document_status(
                        document_id=doc_id,
                        status=ProcessingStatus.FAILED,
                        db=db,
                    )
                    logger.error(
                        f"Document processing failed permanently after {self.request.retries} retries",
                        extra={
                            "document_id": document_id,
                            "task_id": self.request.id,
                        }
                    )
            except Exception as update_error:
                logger.error(
                    f"Failed to update document status to FAILED: {str(update_error)}",
                    extra={"document_id": document_id},
                    exc_info=True,
                )
        
        # Re-raise for retry mechanism
        raise
        
    finally:
        # Close database session
        if db:
            await db.close()


@celery_app.task(name="tasks.healthcheck")
def healthcheck() -> dict:
    """
    Celery worker health check task.
    
    Returns:
        dict: Worker status information
    """
    logger.debug("Celery worker health check")
    return {
        "status": "healthy",
        "worker": "celery_worker",
    }
