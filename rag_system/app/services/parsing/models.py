"""Data models for parsed document content."""
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class ParsedSection(BaseModel):
    """Represents a parsed section of a document."""
    
    section_title: Optional[str] = Field(
        default=None,
        description="Title of the section (e.g., heading, slide title)"
    )
    content: str = Field(
        ...,
        description="Text content of the section"
    )
    page_number: Optional[int] = Field(
        default=None,
        description="Page or slide number where this section appears"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the section"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "section_title": "Introduction",
                "content": "This document covers the basics of...",
                "page_number": 1,
                "metadata": {"type": "heading1", "has_tables": False}
            }
        }


class ParsedDocument(BaseModel):
    """Represents a fully parsed document with all sections."""
    
    document_id: UUID = Field(
        ...,
        description="Unique identifier of the document"
    )
    sections: List[ParsedSection] = Field(
        ...,
        description="List of parsed sections in order"
    )
    total_pages: Optional[int] = Field(
        default=None,
        description="Total number of pages in the document"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Document-level metadata"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "sections": [
                    {
                        "section_title": "Introduction",
                        "content": "Document content here...",
                        "page_number": 1,
                        "metadata": {}
                    }
                ],
                "total_pages": 5,
                "metadata": {"parser": "pdf", "sections_count": 3}
            }
        }
    
    def get_total_sections(self) -> int:
        """Get total number of sections."""
        return len(self.sections)
    
    def get_total_content_length(self) -> int:
        """Get total character count across all sections."""
        return sum(len(section.content) for section in self.sections)
