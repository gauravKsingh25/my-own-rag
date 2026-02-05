"""Document ingestion manager service."""
import uuid
from typing import BinaryIO, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile

from app.db.models import Document, ProcessingStatus
from app.services.storage import LocalStorageService
from app.core.exceptions import StorageException, DatabaseException
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class IngestionManager:
    """Manages document ingestion workflow."""
    
    # Allowed file extensions and MIME types
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt"}
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
    }
    
    # Maximum file size (25MB)
    MAX_FILE_SIZE = 25 * 1024 * 1024
    
    def __init__(self, storage_service: Optional[LocalStorageService] = None):
        """
        Initialize ingestion manager.
        
        Args:
            storage_service: Storage service instance (optional, creates default if None)
        """
        self.storage_service = storage_service or LocalStorageService()
    
    def _validate_file_type(self, filename: str, content_type: Optional[str]) -> str:
        """
        Validate file type and extract document type.
        
        Args:
            filename: Original filename
            content_type: MIME type from upload
            
        Returns:
            str: Document type (extension without dot)
            
        Raises:
            ValueError: If file type is not allowed
        """
        # Get file extension
        file_ext = None
        if "." in filename:
            file_ext = "." + filename.rsplit(".", 1)[-1].lower()
        
        # Validate extension
        if file_ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"File type not allowed. Allowed types: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )
        
        # Optionally validate MIME type if provided
        if content_type and content_type not in self.ALLOWED_MIME_TYPES:
            logger.warning(
                f"MIME type mismatch: {content_type} for file {filename}",
                extra={"content_type": content_type, "filename": filename}
            )
        
        # Return document type without dot
        return file_ext[1:]
    
    def _validate_file_size(self, file_size: int) -> None:
        """
        Validate file size.
        
        Args:
            file_size: Size in bytes
            
        Raises:
            ValueError: If file is too large
        """
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds maximum allowed "
                f"size ({self.MAX_FILE_SIZE} bytes / 25MB)"
            )
    
    async def create_document(
        self,
        file: UploadFile,
        user_id: str,
        db: AsyncSession,
    ) -> Document:
        """
        Create document record and save file.
        
        Args:
            file: Uploaded file
            user_id: User identifier
            db: Database session
            
        Returns:
            Document: Created document instance
            
        Raises:
            ValueError: If validation fails
            StorageException: If file save fails
            DatabaseException: If database operation fails
        """
        try:
            # Read file content
            file_content = await file.read()
            file_size = len(file_content)
            
            # Validate file size
            self._validate_file_size(file_size)
            
            # Validate file type
            document_type = self._validate_file_type(file.filename, file.content_type)
            
            # Generate document ID
            document_id = uuid.uuid4()
            
            logger.info(
                f"Creating document: {file.filename}",
                extra={
                    "user_id": user_id,
                    "document_id": str(document_id),
                    "file_size": file_size,
                    "document_type": document_type,
                }
            )
            
            # Save file to storage
            # Create a file-like object from bytes
            from io import BytesIO
            file_obj = BytesIO(file_content)
            
            storage_path = await self.storage_service.save_file(
                file_content=file_obj,
                user_id=user_id,
                doc_id=str(document_id),
                filename=file.filename,
            )
            
            # Create database record
            document = Document(
                id=document_id,
                user_id=user_id,
                filename=file.filename,
                storage_path=storage_path,
                document_type=document_type,
                processing_status=ProcessingStatus.UPLOADED,
            )
            
            db.add(document)
            await db.commit()
            await db.refresh(document)
            
            logger.info(
                f"Document created successfully",
                extra={
                    "document_id": str(document_id),
                    "user_id": user_id,
                    "storage_path": storage_path,
                }
            )
            
            return document
            
        except ValueError:
            # Re-raise validation errors
            raise
        except StorageException:
            # Re-raise storage errors
            raise
        except Exception as e:
            logger.error(
                f"Failed to create document: {str(e)}",
                extra={
                    "user_id": user_id,
                    "filename": file.filename if file else None,
                },
                exc_info=True,
            )
            await db.rollback()
            raise DatabaseException(
                f"Failed to create document: {str(e)}",
                details={"user_id": user_id, "filename": file.filename if file else None}
            )
    
    async def get_document(
        self,
        document_id: UUID,
        db: AsyncSession,
    ) -> Optional[Document]:
        """
        Retrieve document by ID.
        
        Args:
            document_id: Document UUID
            db: Database session
            
        Returns:
            Optional[Document]: Document instance or None if not found
        """
        try:
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if document:
                logger.debug(
                    f"Document retrieved",
                    extra={
                        "document_id": str(document_id),
                        "status": document.processing_status.value,
                    }
                )
            else:
                logger.debug(f"Document not found: {document_id}")
            
            return document
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve document: {str(e)}",
                extra={"document_id": str(document_id)},
                exc_info=True,
            )
            raise DatabaseException(
                f"Failed to retrieve document: {str(e)}",
                details={"document_id": str(document_id)}
            )
    
    async def update_document_status(
        self,
        document_id: UUID,
        status: ProcessingStatus,
        db: AsyncSession,
    ) -> Document:
        """
        Update document processing status.
        
        Args:
            document_id: Document UUID
            status: New processing status
            db: Database session
            
        Returns:
            Document: Updated document instance
            
        Raises:
            DatabaseException: If update fails
        """
        try:
            document = await self.get_document(document_id, db)
            
            if not document:
                raise DatabaseException(
                    f"Document not found",
                    details={"document_id": str(document_id)}
                )
            
            document.processing_status = status
            await db.commit()
            await db.refresh(document)
            
            logger.info(
                f"Document status updated",
                extra={
                    "document_id": str(document_id),
                    "status": status.value,
                }
            )
            
            return document
            
        except DatabaseException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update document status: {str(e)}",
                extra={
                    "document_id": str(document_id),
                    "status": status.value,
                },
                exc_info=True,
            )
            await db.rollback()
            raise DatabaseException(
                f"Failed to update document status: {str(e)}",
                details={
                    "document_id": str(document_id),
                    "status": status.value,
                }
            )


# Global instance
ingestion_manager = IngestionManager()
