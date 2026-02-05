"""PDF document parser using PyMuPDF (fitz)."""
from pathlib import Path
from typing import Union, List
from uuid import UUID
import fitz  # PyMuPDF

from app.services.parsing.base import BaseParser
from app.services.parsing.models import ParsedDocument, ParsedSection
from app.services.parsing.normalizer import TextNormalizer
from app.core.logging import get_logger

logger = get_logger(__name__)


class PDFParser(BaseParser):
    """Parser for PDF documents using PyMuPDF."""
    
    def __init__(self):
        """Initialize PDF parser."""
        self.normalizer = TextNormalizer()
    
    def supports_format(self, file_extension: str) -> bool:
        """Check if this parser supports PDF format."""
        return file_extension.lower() in ['pdf']
    
    async def parse(
        self,
        file_path: Union[str, Path],
        document_id: UUID,
    ) -> ParsedDocument:
        """
        Parse PDF document page by page.
        
        Features:
        - Extract page-by-page text
        - Preserve paragraph breaks
        - Preserve bullet points
        - Handle empty pages
        - Include page numbers
        
        Args:
            file_path: Path to PDF file
            document_id: Document UUID
            
        Returns:
            ParsedDocument: Parsed PDF with sections (one per page)
            
        Raises:
            Exception: If PDF parsing fails
        """
        file_path = Path(file_path)
        
        logger.info(
            f"Parsing PDF document",
            extra={
                "document_id": str(document_id),
                "file_path": str(file_path),
            }
        )
        
        try:
            # Open PDF document
            doc = fitz.open(file_path)
            
            sections: List[ParsedSection] = []
            total_pages = len(doc)
            
            # Extract text from each page
            for page_num in range(total_pages):
                page = doc[page_num]
                
                # Extract text with layout preservation
                text = page.get_text("text")
                
                # Skip empty pages
                if not text.strip():
                    logger.debug(
                        f"Skipping empty page {page_num + 1}",
                        extra={"document_id": str(document_id)}
                    )
                    continue
                
                # Normalize text
                normalized_text = self.normalizer.normalize(text)
                
                # Create section for this page
                section = ParsedSection(
                    section_title=f"Page {page_num + 1}",
                    content=normalized_text,
                    page_number=page_num + 1,
                    metadata={
                        "page_width": page.rect.width,
                        "page_height": page.rect.height,
                        "has_images": len(page.get_images()) > 0,
                        "has_links": len(page.get_links()) > 0,
                    }
                )
                
                sections.append(section)
            
            # Close document
            doc.close()
            
            # Create parsed document
            parsed_doc = ParsedDocument(
                document_id=document_id,
                sections=sections,
                total_pages=total_pages,
                metadata={
                    "parser": "pdf",
                    "total_pages": total_pages,
                    "non_empty_pages": len(sections),
                }
            )
            
            # Log parsing statistics
            self._log_parsing_stats(
                document_id=document_id,
                sections_count=len(sections),
                total_chars=parsed_doc.get_total_content_length(),
                total_pages=total_pages,
            )
            
            return parsed_doc
            
        except Exception as e:
            logger.error(
                f"Failed to parse PDF: {str(e)}",
                extra={
                    "document_id": str(document_id),
                    "file_path": str(file_path),
                },
                exc_info=True,
            )
            raise Exception(f"PDF parsing failed: {str(e)}")
