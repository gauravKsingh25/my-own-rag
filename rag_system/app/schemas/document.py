"""Pydantic schemas for document operations."""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class DocumentUploadRequest(BaseModel):
    """Request schema for document upload."""
    
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User identifier",
    )
    
    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate user_id format."""
        if not v.strip():
            raise ValueError("user_id cannot be empty or whitespace")
        # Prevent path traversal in user_id
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("user_id contains invalid characters")
        return v.strip()


class DocumentUploadResponse(BaseModel):
    """Response schema for successful document upload."""
    
    document_id: UUID = Field(..., description="Unique document identifier")
    user_id: str = Field(..., description="User identifier")
    filename: str = Field(..., description="Original filename")
    document_type: str = Field(..., description="Document type/extension")
    storage_path: str = Field(..., description="Storage path")
    processing_status: str = Field(..., description="Current processing status")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "user123",
                "filename": "document.pdf",
                "document_type": "pdf",
                "storage_path": "user123/123e4567-e89b-12d3-a456-426614174000/document.pdf",
                "processing_status": "UPLOADED",
                "created_at": "2026-02-05T10:30:00",
            }
        }


class DocumentResponse(BaseModel):
    """Response schema for document metadata."""
    
    id: UUID = Field(..., description="Document identifier")
    user_id: str = Field(..., description="User identifier")
    filename: str = Field(..., description="Original filename")
    storage_path: str = Field(..., description="Storage path")
    document_type: str = Field(..., description="Document type/extension")
    version: int = Field(..., description="Document version")
    is_active: bool = Field(..., description="Whether document is active")
    processing_status: str = Field(..., description="Current processing status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "user123",
                "filename": "document.pdf",
                "storage_path": "user123/123e4567-e89b-12d3-a456-426614174000/document.pdf",
                "document_type": "pdf",
                "version": 1,
                "is_active": True,
                "processing_status": "COMPLETED",
                "created_at": "2026-02-05T10:30:00",
                "updated_at": "2026-02-05T10:35:00",
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    
    error: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
    request_id: str = Field(..., description="Request identifier")
    details: Optional[dict] = Field(default=None, description="Additional error details")
