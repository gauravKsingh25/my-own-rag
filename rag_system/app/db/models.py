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
    Float,
    Text,
    Enum,
    Index,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import relationship
from app.db.database import Base


class ProcessingStatus(str, PyEnum):
    """Document processing status enumeration."""
    
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PARSED = "PARSED"
    CHUNKED = "CHUNKED"
    EMBEDDED = "EMBEDDED"
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


class Chunk(Base):
    """Chunk model for storing document chunks with full-text search."""
    
    __tablename__ = "chunks"
    
    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        index=True,
    )
    
    # Foreign key to document
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # User information (denormalized for query performance)
    user_id = Column(String(255), nullable=False, index=True)
    
    # Chunk information
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    
    # Token count
    token_count = Column(Integer, nullable=False)
    
    # Document structure metadata
    section_title = Column(String(512), nullable=True)
    page_number = Column(Integer, nullable=True)
    hierarchy = Column(Text, nullable=True)  # JSON string
    
    # Full-text search vector
    content_tsvector = Column(
        TSVECTOR,
        nullable=True,
    )
    
    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    
    # Relationship
    document = relationship("Document", backref="chunks")
    
    # Indexes
    __table_args__ = (
        # Composite index for user queries
        Index(
            "ix_chunks_user_document",
            "user_id",
            "document_id",
        ),
        # GIN index for full-text search
        Index(
            "ix_chunks_content_tsvector",
            "content_tsvector",
            postgresql_using="gin",
        ),
        # Index for content hash deduplication
        Index(
            "ix_chunks_content_hash",
            "content_hash",
        ),
        # Composite index for document ordering
        Index(
            "ix_chunks_document_index",
            "document_id",
            "chunk_index",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Chunk(id={self.id}, document_id={self.document_id}, "
            f"chunk_index={self.chunk_index}, tokens={self.token_count})>"
        )
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "user_id": self.user_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "content_hash": self.content_hash,
            "token_count": self.token_count,
            "section_title": self.section_title,
            "page_number": self.page_number,
            "hierarchy": self.hierarchy,
            "created_at": self.created_at.isoformat(),
        }


class ChatInteraction(Base):
    """Chat interaction model for monitoring and analytics."""
    
    __tablename__ = "chat_interactions"
    
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
    
    # Query and response
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    
    # Quality metrics
    confidence_score = Column(Float, nullable=False)
    citations_count = Column(Integer, default=0)
    
    # Performance metrics
    latency_ms = Column(Float, nullable=False)
    retrieval_latency_ms = Column(Float, nullable=True)
    generation_latency_ms = Column(Float, nullable=True)
    
    # Token usage
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    
    # Model information
    model_name = Column(String(100), nullable=False)
    
    # Cost tracking
    cost_estimate = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    
    # Relationship
    feedbacks = relationship("ChatFeedback", backref="interaction", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index(
            "ix_chat_interactions_user_created",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_chat_interactions_confidence",
            "confidence_score",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ChatInteraction(id={self.id}, user_id={self.user_id}, "
            f"confidence={self.confidence_score})>"
        )
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "query": self.query,
            "answer": self.answer,
            "confidence_score": self.confidence_score,
            "citations_count": self.citations_count,
            "latency_ms": self.latency_ms,
            "retrieval_latency_ms": self.retrieval_latency_ms,
            "generation_latency_ms": self.generation_latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model_name": self.model_name,
            "cost_estimate": self.cost_estimate,
            "created_at": self.created_at.isoformat(),
        }


class ChatFeedback(Base):
    """Chat feedback model for user ratings and comments."""
    
    __tablename__ = "chat_feedbacks"
    
    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        index=True,
    )
    
    # Foreign key to interaction
    interaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_interactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Feedback data
    rating = Column(
        Integer,
        nullable=False,
    )
    comment = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    
    # Indexes
    __table_args__ = (
        Index(
            "ix_chat_feedbacks_rating",
            "rating",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ChatFeedback(id={self.id}, interaction_id={self.interaction_id}, "
            f"rating={self.rating})>"
        )
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "interaction_id": str(self.interaction_id),
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat(),
        }
