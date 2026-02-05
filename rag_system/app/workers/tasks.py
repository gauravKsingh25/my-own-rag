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
        
        # ============================================================
        # PLACEHOLDER: Future RAG processing
        # ============================================================
        # Next steps (not implemented yet):
        # 1. Chunk sections into smaller segments
        # 2. Generate embeddings for each chunk
        # 3. Store embeddings in vector database (Pinecone, etc.)
        # 4. Update metadata with chunking/embedding info
        # ============================================================
        
        # Update status to PARSED
        await ingestion_manager.update_document_status(
            document_id=doc_id,
            status=ProcessingStatus.PARSED,
            db=db,
        )
        
        logger.info(
            f"Document processing completed successfully",
            extra={
                "document_id": document_id,
                "task_id": self.request.id,
                "final_status": "PARSED",
            }
        )
        
        return {
            "document_id": document_id,
            "status": "PARSED",
            "task_id": self.request.id,
            "sections_count": sections_count,
            "total_chars": total_chars,
            "total_pages": parsed_doc.total_pages,
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
