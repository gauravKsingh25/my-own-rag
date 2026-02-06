"""Chunk data models for document chunking."""
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """Represents a chunk of document content."""
    
    document_id: UUID = Field(
        ...,
        description="UUID of the parent document"
    )
    chunk_index: int = Field(
        ...,
        ge=0,
        description="Sequential index of this chunk within the document"
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Text content of the chunk"
    )
    token_count: int = Field(
        ...,
        gt=0,
        description="Number of tokens in this chunk"
    )
    section_title: Optional[str] = Field(
        default=None,
        description="Title of the source section (if available)"
    )
    page_number: Optional[int] = Field(
        default=None,
        description="Page number where this chunk appears"
    )
    content_hash: str = Field(
        ...,
        description="SHA256 hash of the content for deduplication"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the chunk"
    )
    parent_section_id: Optional[str] = Field(
        default=None,
        description="Identifier of the parent section (for hierarchical structure)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "chunk_index": 0,
                "content": "This is the content of the first chunk...",
                "token_count": 150,
                "section_title": "Introduction",
                "page_number": 1,
                "content_hash": "a1b2c3d4...",
                "metadata": {"source": "pdf", "version": 1},
                "parent_section_id": "section_0"
            }
        }


class ChunkedDocument(BaseModel):
    """Represents a document with all its chunks."""
    
    document_id: UUID = Field(
        ...,
        description="UUID of the document"
    )
    chunks: list[Chunk] = Field(
        ...,
        description="List of chunks in order"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Document-level chunking metadata"
    )
    
    def get_total_chunks(self) -> int:
        """Get total number of chunks."""
        return len(self.chunks)
    
    def get_total_tokens(self) -> int:
        """Get total token count across all chunks."""
        return sum(chunk.token_count for chunk in self.chunks)
    
    def get_average_chunk_size(self) -> float:
        """Get average chunk size in tokens."""
        total_chunks = self.get_total_chunks()
        if total_chunks == 0:
            return 0.0
        return self.get_total_tokens() / total_chunks
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "chunks": [],
                "metadata": {
                    "chunking_strategy": "semantic",
                    "max_tokens": 500,
                    "overlap": 100
                }
            }
        }
