"""SQLAlchemy database models."""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Integer,
    Enum,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base


class ProcessingStatus(str, PyEnum):
    """Document processing status enumeration."""
    
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PARSED = "PARSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Document(Base):
    """Document model for tracking uploaded documents."""
    
    __tablename__ = "documents"
    
    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        index=True,
    )
    
    # User information
    user_id = Column(String(255), nullable=False, index=True)
    
    # File information
    filename = Column(String(512), nullable=False)
    storage_path = Column(String(1024), nullable=False)
    document_type = Column(String(50), nullable=False)
    
    # Versioning and status
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    processing_status = Column(
        Enum(ProcessingStatus),
        default=ProcessingStatus.UPLOADED,
        nullable=False,
        index=True,
    )
    
    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    
    # Composite indexes for common queries
    __table_args__ = (
        Index(
            "ix_documents_user_created",
            "user_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index(
            "ix_documents_status_created",
            "processing_status",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id}, user_id={self.user_id}, "
            f"filename={self.filename}, status={self.processing_status})>"
        )
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "filename": self.filename,
            "storage_path": self.storage_path,
            "document_type": self.document_type,
            "version": self.version,
            "is_active": self.is_active,
            "processing_status": self.processing_status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
