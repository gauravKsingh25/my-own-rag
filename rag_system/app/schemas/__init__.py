"""Schemas module initialization."""
from app.schemas.health import HealthResponse, ReadinessResponse
from app.schemas.document import (
    DocumentUploadRequest,
    DocumentUploadResponse,
    DocumentResponse,
    ErrorResponse,
)

__all__ = [
    "HealthResponse",
    "ReadinessResponse",
    "DocumentUploadRequest",
    "DocumentUploadResponse",
    "DocumentResponse",
    "ErrorResponse",
]
