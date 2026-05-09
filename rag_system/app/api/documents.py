"""Document management API endpoints."""
from uuid import UUID
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentDeleteResponse,
)
from app.services.ingestion import ingestion_manager
from app.workers.tasks import process_document
from app.core.logging import get_logger
from app.core.exceptions import StorageException, DatabaseException
from app.core.auth import get_authenticated_user_id

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    description="Upload a document for processing. Accepts PDF, DOCX, PPTX, and TXT files up to 25MB.",
)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload"),
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Upload and queue a document for processing.
    
    Workflow:
    1. Validate file type (PDF, DOCX, PPTX, TXT)
    2. Validate file size (max 25MB)
    3. Generate unique document ID
    4. Save file to storage
    5. Create database record with status=UPLOADED
    6. Trigger async Celery task for processing
    7. Return document metadata
    
    Args:
        file: Uploaded file
        user_id: User identifier
        db: Database session (injected)
        
    Returns:
        DocumentUploadResponse: Document metadata with processing status
        
    Raises:
        HTTPException 400: Invalid file type or size
        HTTPException 422: Validation error
        HTTPException 500: Storage or database error
    """
    logger.info(
        f"Document upload request",
        extra={
            "user_id": user_id,
            "file_name": file.filename,
            "content_type": file.content_type,
        }
    )
    
    try:
        # Create document using ingestion manager
        document = await ingestion_manager.create_document(
            file=file,
            user_id=user_id,
            db=db,
        )
        
        # Trigger async processing task
        task = process_document.delay(str(document.id))
        
        logger.info(
            f"Document upload successful, processing task queued",
            extra={
                "document_id": str(document.id),
                "user_id": user_id,
                "task_id": task.id,
                "file_name": file.filename,
            }
        )
        
        # Return response
        return DocumentUploadResponse(
            document_id=document.id,
            user_id=document.user_id,
            filename=document.filename,
            document_type=document.document_type,
            storage_path=document.storage_path,
            processing_status=document.processing_status.value,
            created_at=document.created_at,
        )
        
    except ValueError as e:
        # Validation errors (file type, size)
        logger.warning(
            f"Document upload validation failed: {str(e)}",
            extra={
                "user_id": user_id,
                "file_name": file.filename,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
        
    except StorageException as e:
        # Storage errors
        logger.error(
            f"Document upload storage error: {e.message}",
            extra={
                "user_id": user_id,
                "file_name": file.filename,
                "details": e.details,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save document: {e.message}",
        )
        
    except DatabaseException as e:
        # Database errors
        logger.error(
            f"Document upload database error: {e.message}",
            extra={
                "user_id": user_id,
                "file_name": file.filename,
                "details": e.details,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create document record: {e.message}",
        )
        
    except Exception as e:
        # Unexpected errors
        logger.error(
            f"Unexpected error during document upload: {str(e)}",
            extra={
                "user_id": user_id,
                "file_name": file.filename,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during document upload",
        )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document metadata",
    description="Retrieve document metadata and processing status by document ID.",
)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Retrieve document metadata by ID.
    
    Returns complete document information including:
    - Document metadata (filename, type, version)
    - Storage path
    - Processing status
    - Timestamps
    
    Args:
        document_id: Document UUID
        db: Database session (injected)
        
    Returns:
        DocumentResponse: Complete document metadata
        
    Raises:
        HTTPException 404: Document not found
        HTTPException 500: Database error
    """
    logger.info(
        f"Document retrieval request",
        extra={"document_id": str(document_id)}
    )
    
    try:
        # Retrieve document
        document = await ingestion_manager.get_document(
            document_id=document_id,
            db=db,
        )
        
        if not document:
            logger.warning(
                f"Document not found",
                extra={"document_id": str(document_id)}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )
        
        logger.info(
            f"Document retrieved successfully",
            extra={
                "document_id": str(document_id),
                "status": document.processing_status.value,
            }
        )
        
        # Return response
        return DocumentResponse(
            id=document.id,
            user_id=document.user_id,
            filename=document.filename,
            storage_path=document.storage_path,
            document_type=document.document_type,
            version=document.version,
            is_active=document.is_active,
            processing_status=document.processing_status.value,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except DatabaseException as e:
        # Database errors
        logger.error(
            f"Database error retrieving document: {e.message}",
            extra={
                "document_id": str(document_id),
                "details": e.details,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve document: {e.message}",
        )
        
    except Exception as e:
        # Unexpected errors
        logger.error(
            f"Unexpected error retrieving document: {str(e)}",
            extra={"document_id": str(document_id)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving document",
        )


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a document",
    description=(
        "Delete a document and all related data from metadata, chunk storage, "
        "vector store, and file storage."
    ),
)
async def delete_document(
    document_id: UUID,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
) -> DocumentDeleteResponse:
    """Delete a document and its associated data from all storage layers."""
    logger.info(
        "Document deletion request",
        extra={
            "document_id": str(document_id),
            "user_id": user_id,
        },
    )

    try:
        document = await ingestion_manager.get_document(
            document_id=document_id,
            db=db,
        )

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )

        if document.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to delete this document",
            )

        await ingestion_manager.delete_document_data(
            document_id=document_id,
            user_id=user_id,
            db=db,
        )

        return DocumentDeleteResponse(
            document_id=document_id,
            user_id=user_id,
            deleted=True,
            message="Document deleted from metadata, chunks, vectors, and file storage",
        )

    except HTTPException:
        raise

    except (StorageException, DatabaseException) as e:
        logger.error(
            f"Document deletion failed: {e.message}",
            extra={
                "document_id": str(document_id),
                "user_id": user_id,
                "details": e.details,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {e.message}",
        )

    except Exception as e:
        logger.error(
            f"Unexpected error deleting document: {str(e)}",
            extra={
                "document_id": str(document_id),
                "user_id": user_id,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting document",
        )
