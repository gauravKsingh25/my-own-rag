"""Base document parser interface."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union
from uuid import UUID

from app.services.parsing.models import ParsedDocument
from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseParser(ABC):
    """Abstract base class for document parsers."""
    
    @abstractmethod
    async def parse(
        self,
        file_path: Union[str, Path],
        document_id: UUID,
    ) -> ParsedDocument:
        """
        Parse a document file.
        
        Args:
            file_path: Path to the document file
            document_id: UUID of the document
            
        Returns:
            ParsedDocument: Parsed document with sections
            
        Raises:
            Exception: If parsing fails
        """
        pass
    
    @abstractmethod
    def supports_format(self, file_extension: str) -> bool:
        """
        Check if this parser supports the given file format.
        
        Args:
            file_extension: File extension (e.g., 'pdf', 'docx')
            
        Returns:
            bool: True if format is supported
        """
        pass
    
    def _log_parsing_stats(
        self,
        document_id: UUID,
        sections_count: int,
        total_chars: int,
        total_pages: int = None,
    ) -> None:
        """
        Log parsing statistics.
        
        Args:
            document_id: Document UUID
            sections_count: Number of sections parsed
            total_chars: Total character count
            total_pages: Total number of pages (optional)
        """
        logger.info(
            f"Document parsed successfully",
            extra={
                "document_id": str(document_id),
                "sections_count": sections_count,
                "total_chars": total_chars,
                "total_pages": total_pages,
            }
        )
