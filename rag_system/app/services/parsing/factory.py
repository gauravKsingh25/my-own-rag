"""Parser factory for creating appropriate document parsers."""
from typing import Optional

from app.services.parsing.base import BaseParser
from app.services.parsing.pdf_parser import PDFParser
from app.services.parsing.docx_parser import DOCXParser
from app.services.parsing.pptx_parser import PPTXParser
from app.services.parsing.text_parser import TextParser
from app.core.logging import get_logger

logger = get_logger(__name__)


class ParserFactory:
    """Factory for creating document parsers based on file type."""
    
    # Singleton instances of parsers
    _parsers = {
        'pdf': PDFParser(),
        'docx': DOCXParser(),
        'pptx': PPTXParser(),
        'txt': TextParser(),
    }
    
    @classmethod
    def get_parser(cls, document_type: str) -> Optional[BaseParser]:
        """
        Get appropriate parser for document type.
        
        Args:
            document_type: Document type/extension (pdf, docx, pptx, txt)
            
        Returns:
            Optional[BaseParser]: Parser instance or None if unsupported
        """
        document_type = document_type.lower().strip()
        
        parser = cls._parsers.get(document_type)
        
        if parser:
            logger.debug(
                f"Parser selected for document type: {document_type}",
                extra={"document_type": document_type, "parser": parser.__class__.__name__}
            )
        else:
            logger.warning(
                f"No parser available for document type: {document_type}",
                extra={"document_type": document_type}
            )
        
        return parser
    
    @classmethod
    def supports_format(cls, document_type: str) -> bool:
        """
        Check if a document format is supported.
        
        Args:
            document_type: Document type/extension
            
        Returns:
            bool: True if format is supported
        """
        return document_type.lower().strip() in cls._parsers
    
    @classmethod
    def get_supported_formats(cls) -> list:
        """
        Get list of all supported document formats.
        
        Returns:
            list: List of supported formats
        """
        return list(cls._parsers.keys())
