"""Plain text document parser."""
from pathlib import Path
from typing import Union, List
from uuid import UUID
import aiofiles

from app.services.parsing.base import BaseParser
from app.services.parsing.models import ParsedDocument, ParsedSection
from app.services.parsing.normalizer import TextNormalizer
from app.core.logging import get_logger

logger = get_logger(__name__)


class TextParser(BaseParser):
    """Parser for plain text documents."""
    
    def __init__(self):
        """Initialize text parser."""
        self.normalizer = TextNormalizer()
    
    def supports_format(self, file_extension: str) -> bool:
        """Check if this parser supports TXT format."""
        return file_extension.lower() in ['txt']
    
    async def parse(
        self,
        file_path: Union[str, Path],
        document_id: UUID,
    ) -> ParsedDocument:
        """
        Parse plain text document.
        
        Features:
        - Simple paragraph splitting (by double newlines)
        - Preserves paragraph structure
        
        Args:
            file_path: Path to TXT file
            document_id: Document UUID
            
        Returns:
            ParsedDocument: Parsed text with sections (by paragraphs)
            
        Raises:
            Exception: If text parsing fails
        """
        file_path = Path(file_path)
        
        logger.info(
            f"Parsing TXT document",
            extra={
                "document_id": str(document_id),
                "file_path": str(file_path),
            }
        )
        
        try:
            # Read file content asynchronously
            async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = await f.read()
            
            # Normalize the entire content first
            normalized_content = self.normalizer.normalize(content)
            
            # Split by paragraph breaks (double newlines)
            paragraphs = normalized_content.split('\n\n')
            
            # Filter out empty paragraphs
            paragraphs = [p.strip() for p in paragraphs if p.strip()]
            
            sections: List[ParsedSection] = []
            
            # Create sections from paragraphs
            for idx, paragraph in enumerate(paragraphs, start=1):
                section = ParsedSection(
                    section_title=None,  # Plain text has no titles
                    content=paragraph,
                    page_number=None,  # No page concept in plain text
                    metadata={
                        "paragraph_index": idx,
                    }
                )
                sections.append(section)
            
            # If no paragraphs found (single block of text), create one section
            if not sections and normalized_content:
                section = ParsedSection(
                    section_title=None,
                    content=normalized_content,
                    metadata={
                        "paragraph_index": 1,
                    }
                )
                sections.append(section)
            
            # Create parsed document
            parsed_doc = ParsedDocument(
                document_id=document_id,
                sections=sections,
                metadata={
                    "parser": "txt",
                    "paragraph_count": len(sections),
                }
            )
            
            # Log parsing statistics
            self._log_parsing_stats(
                document_id=document_id,
                sections_count=len(sections),
                total_chars=parsed_doc.get_total_content_length(),
            )
            
            return parsed_doc
            
        except Exception as e:
            logger.error(
                f"Failed to parse TXT: {str(e)}",
                extra={
                    "document_id": str(document_id),
                    "file_path": str(file_path),
                },
                exc_info=True,
            )
            raise Exception(f"TXT parsing failed: {str(e)}")
