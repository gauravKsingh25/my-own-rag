"""Source formatting for citation and attribution."""
from typing import List, Optional, Dict, Any
from app.core.logging import get_logger

logger = get_logger(__name__)


class SourceFormatter:
    """
    Format retrieved chunks as cited sources for LLM context.
    
    Format:
        [Source X]
        Document: filename
        Section: section_title
        Page: page_number
        Content:
        ...
    """
    
    @staticmethod
    def format_source(
        source_number: int,
        content: str,
        document_filename: Optional[str] = None,
        section_title: Optional[str] = None,
        page_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Format a single source with citation information.
        
        Args:
            source_number: Source index (1-based)
            content: Chunk content
            document_filename: Name of source document
            section_title: Section or heading
            page_number: Page number in document
            metadata: Additional metadata
            
        Returns:
            str: Formatted source text
        """
        lines = [f"[Source {source_number}]"]
        
        # Add document info if available
        if document_filename:
            lines.append(f"Document: {document_filename}")
        
        # Add section info if available
        if section_title:
            lines.append(f"Section: {section_title}")
        
        # Add page number if available
        if page_number is not None:
            lines.append(f"Page: {page_number}")
        
        # Add content
        lines.append("Content:")
        lines.append(content.strip())
        
        # Join with newlines
        formatted = "\n".join(lines)
        
        return formatted
    
    @staticmethod
    def format_sources(
        contents: List[str],
        document_filenames: Optional[List[str]] = None,
        section_titles: Optional[List[Optional[str]]] = None,
        page_numbers: Optional[List[Optional[int]]] = None,
        metadata_list: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Format multiple sources as a context string.
        
        Args:
            contents: List of chunk contents
            document_filenames: List of document filenames
            section_titles: List of section titles
            page_numbers: List of page numbers
            metadata_list: List of metadata dicts
            
        Returns:
            str: Formatted context with all sources
        """
        if not contents:
            logger.warning("No contents provided for formatting")
            return ""
        
        # Ensure all lists have the same length
        n = len(contents)
        
        if document_filenames is None:
            document_filenames = [None] * n
        if section_titles is None:
            section_titles = [None] * n
        if page_numbers is None:
            page_numbers = [None] * n
        if metadata_list is None:
            metadata_list = [None] * n
        
        # Format each source
        formatted_sources = []
        
        for i in range(n):
            formatted_source = SourceFormatter.format_source(
                source_number=i + 1,  # 1-based indexing
                content=contents[i],
                document_filename=document_filenames[i],
                section_title=section_titles[i],
                page_number=page_numbers[i],
                metadata=metadata_list[i],
            )
            formatted_sources.append(formatted_source)
        
        # Join all sources with separators
        context = "\n\n---\n\n".join(formatted_sources)
        
        logger.info(
            f"Sources formatted",
            extra={
                "source_count": len(contents),
                "total_chars": len(context),
            }
        )
        
        return context
    
    @staticmethod
    def extract_document_info(
        retrieval_results: List[Any],
    ) -> Dict[str, List]:
        """
        Extract formatting information from retrieval results.
        
        Args:
            retrieval_results: List of RetrievalResult objects
            
        Returns:
            dict: {
                "contents": List[str],
                "document_filenames": List[str],
                "section_titles": List[Optional[str]],
                "page_numbers": List[Optional[int]],
                "metadata_list": List[Dict],
            }
        """
        contents = []
        document_filenames = []
        section_titles = []
        page_numbers = []
        metadata_list = []
        
        for result in retrieval_results:
            # Extract content
            contents.append(result.content)
            
            # Extract metadata
            # Try to get document filename from metadata
            filename = None
            if hasattr(result, 'metadata') and result.metadata:
                filename = result.metadata.get('filename')
            
            # Fallback to document_id if no filename
            if not filename and hasattr(result, 'document_id'):
                filename = f"Document {str(result.document_id)[:8]}"
            
            document_filenames.append(filename or "Unknown Document")
            
            # Extract section and page
            section = getattr(result, 'section_title', None)
            page = getattr(result, 'page_number', None)
            
            section_titles.append(section)
            page_numbers.append(page)
            
            # Store full metadata
            if hasattr(result, 'metadata'):
                metadata_list.append(result.metadata or {})
            else:
                metadata_list.append({})
        
        return {
            "contents": contents,
            "document_filenames": document_filenames,
            "section_titles": section_titles,
            "page_numbers": page_numbers,
            "metadata_list": metadata_list,
        }
    
    @staticmethod
    def create_source_mapping(
        retrieval_results: List[Any],
    ) -> Dict[str, Any]:
        """
        Create a mapping of source numbers to document information.
        
        Useful for tracking citations in generated answers.
        
        Args:
            retrieval_results: List of RetrievalResult objects
            
        Returns:
            dict: Mapping of source numbers to metadata
        """
        source_map = {}
        
        for i, result in enumerate(retrieval_results):
            source_number = i + 1
            
            source_map[source_number] = {
                "chunk_id": str(getattr(result, 'chunk_id', '')),
                "document_id": str(getattr(result, 'document_id', '')),
                "section_title": getattr(result, 'section_title', None),
                "page_number": getattr(result, 'page_number', None),
                "score": getattr(result, 'score', 0.0),
                "chunk_index": getattr(result, 'chunk_index', 0),
            }
        
        return source_map
