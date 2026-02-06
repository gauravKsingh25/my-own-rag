"""Semantic chunker for intelligent document chunking."""
from typing import List, Optional
from uuid import UUID

from app.services.chunking.models import Chunk, ChunkedDocument
from app.services.chunking.tokenizer import Tokenizer
from app.services.chunking.hash_utils import generate_content_hash
from app.services.parsing.models import ParsedDocument, ParsedSection
from app.core.logging import get_logger

logger = get_logger(__name__)


class SemanticChunker:
    """
    Semantic chunker for creating intelligent document chunks.
    
    Features:
    - Merges small sections
    - Splits large sections
    - Preserves section metadata
    - Generates content hashes
    - Avoids empty chunks
    """
    
    def __init__(
        self,
        max_tokens: int = 500,
        overlap: int = 100,
        min_chunk_tokens: int = 50,
    ):
        """
        Initialize semantic chunker.
        
        Args:
            max_tokens: Maximum tokens per chunk
            overlap: Token overlap between chunks
            min_chunk_tokens: Minimum tokens to merge small sections
        """
        self.max_tokens = max_tokens
        self.overlap = overlap
        self.min_chunk_tokens = min_chunk_tokens
        self.tokenizer = Tokenizer()
        
        logger.debug(
            f"SemanticChunker initialized",
            extra={
                "max_tokens": max_tokens,
                "overlap": overlap,
                "min_chunk_tokens": min_chunk_tokens,
            }
        )
    
    async def chunk_document(
        self,
        parsed_doc: ParsedDocument,
        filename: Optional[str] = None,
        version: int = 1,
    ) -> ChunkedDocument:
        """
        Chunk a parsed document into semantic chunks.
        
        Strategy:
        1. Process each section
        2. Merge small consecutive sections
        3. Split large sections
        4. Preserve metadata (title, page number)
        5. Generate content hashes
        6. Create hierarchical structure
        
        Args:
            parsed_doc: Parsed document to chunk
            filename: Original filename (for metadata)
            version: Document version (for metadata)
            
        Returns:
            ChunkedDocument: Document with chunks
        """
        logger.info(
            f"Starting semantic chunking",
            extra={
                "document_id": str(parsed_doc.document_id),
                "sections_count": len(parsed_doc.sections),
            }
        )
        
        chunks: List[Chunk] = []
        chunk_index = 0
        
        # Process sections with merging strategy
        sections_to_process = self._merge_small_sections(parsed_doc.sections)
        
        # Process each section
        for section_idx, section in enumerate(sections_to_process):
            section_chunks = await self._chunk_section(
                section=section,
                document_id=parsed_doc.document_id,
                section_idx=section_idx,
                start_chunk_index=chunk_index,
                filename=filename,
                version=version,
            )
            
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)
        
        # Create chunked document
        chunked_doc = ChunkedDocument(
            document_id=parsed_doc.document_id,
            chunks=chunks,
            metadata={
                "chunking_strategy": "semantic",
                "max_tokens": self.max_tokens,
                "overlap": self.overlap,
                "total_chunks": len(chunks),
                "total_sections_processed": len(sections_to_process),
                "original_sections": len(parsed_doc.sections),
                "filename": filename,
                "version": version,
            }
        )
        
        # Log statistics
        self._log_chunking_stats(chunked_doc)
        
        return chunked_doc
    
    async def _chunk_section(
        self,
        section: ParsedSection,
        document_id: UUID,
        section_idx: int,
        start_chunk_index: int,
        filename: Optional[str] = None,
        version: int = 1,
    ) -> List[Chunk]:
        """
        Chunk a single section.
        
        Args:
            section: Section to chunk
            document_id: Document UUID
            section_idx: Index of section in document
            start_chunk_index: Starting chunk index
            filename: Original filename
            version: Document version
            
        Returns:
            List[Chunk]: List of chunks from this section
        """
        section_content = section.content.strip()
        
        # Skip empty sections
        if not section_content:
            logger.debug(f"Skipping empty section {section_idx}")
            return []
        
        # Count tokens in section
        section_tokens = self.tokenizer.count_tokens(section_content)
        
        # If section fits in one chunk, create single chunk
        if section_tokens <= self.max_tokens:
            chunk = self._create_chunk(
                content=section_content,
                document_id=document_id,
                chunk_index=start_chunk_index,
                section_title=section.section_title,
                page_number=section.page_number,
                parent_section_id=f"section_{section_idx}",
                filename=filename,
                version=version,
                metadata=section.metadata,
            )
            return [chunk]
        
        # Section is too large, split it
        logger.debug(
            f"Splitting large section {section_idx}",
            extra={
                "section_tokens": section_tokens,
                "max_tokens": self.max_tokens,
            }
        )
        
        # Split by token limit
        text_chunks = self.tokenizer.split_by_token_limit(
            text=section_content,
            max_tokens=self.max_tokens,
            overlap=self.overlap,
        )
        
        # Create Chunk objects
        chunks = []
        for sub_idx, text_chunk in enumerate(text_chunks):
            chunk = self._create_chunk(
                content=text_chunk,
                document_id=document_id,
                chunk_index=start_chunk_index + sub_idx,
                section_title=section.section_title,
                page_number=section.page_number,
                parent_section_id=f"section_{section_idx}",
                filename=filename,
                version=version,
                metadata={
                    **section.metadata,
                    "split_index": sub_idx,
                    "total_splits": len(text_chunks),
                },
            )
            chunks.append(chunk)
        
        return chunks
    
    def _merge_small_sections(
        self,
        sections: List[ParsedSection]
    ) -> List[ParsedSection]:
        """
        Merge consecutive small sections to create better chunks.
        
        Args:
            sections: List of parsed sections
            
        Returns:
            List[ParsedSection]: Sections with small ones merged
        """
        if not sections:
            return []
        
        merged_sections: List[ParsedSection] = []
        current_merge_content = []
        current_merge_metadata = {}
        merge_start_page = None
        
        for section in sections:
            section_tokens = self.tokenizer.count_tokens(section.content)
            
            # If section is large enough or we have accumulated content
            if section_tokens >= self.min_chunk_tokens:
                # Save any accumulated small sections
                if current_merge_content:
                    merged_section = ParsedSection(
                        section_title=None,  # Merged sections lose title
                        content='\n\n'.join(current_merge_content),
                        page_number=merge_start_page,
                        metadata={
                            **current_merge_metadata,
                            "merged": True,
                            "section_count": len(current_merge_content),
                        }
                    )
                    merged_sections.append(merged_section)
                    current_merge_content = []
                    current_merge_metadata = {}
                    merge_start_page = None
                
                # Add current section as-is
                merged_sections.append(section)
            else:
                # Accumulate small section
                current_merge_content.append(section.content)
                if merge_start_page is None:
                    merge_start_page = section.page_number
                
                # Merge metadata
                for key, value in section.metadata.items():
                    if key not in current_merge_metadata:
                        current_merge_metadata[key] = value
        
        # Add any remaining accumulated sections
        if current_merge_content:
            merged_section = ParsedSection(
                section_title=None,
                content='\n\n'.join(current_merge_content),
                page_number=merge_start_page,
                metadata={
                    **current_merge_metadata,
                    "merged": True,
                    "section_count": len(current_merge_content),
                }
            )
            merged_sections.append(merged_section)
        
        logger.debug(
            f"Section merging complete",
            extra={
                "original_sections": len(sections),
                "merged_sections": len(merged_sections),
            }
        )
        
        return merged_sections
    
    def _create_chunk(
        self,
        content: str,
        document_id: UUID,
        chunk_index: int,
        section_title: Optional[str],
        page_number: Optional[int],
        parent_section_id: str,
        filename: Optional[str],
        version: int,
        metadata: dict,
    ) -> Chunk:
        """
        Create a Chunk object with all metadata.
        
        Args:
            content: Chunk content
            document_id: Document UUID
            chunk_index: Chunk index
            section_title: Section title
            page_number: Page number
            parent_section_id: Parent section ID
            filename: Original filename
            version: Document version
            metadata: Additional metadata
            
        Returns:
            Chunk: Created chunk object
        """
        # Count tokens
        token_count = self.tokenizer.count_tokens(content)
        
        # Generate content hash
        content_hash = generate_content_hash(content)
        
        # Prepare metadata
        chunk_metadata = {
            "document_id": str(document_id),
            "filename": filename,
            "version": version,
            **metadata,
        }
        
        return Chunk(
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            token_count=token_count,
            section_title=section_title,
            page_number=page_number,
            content_hash=content_hash,
            metadata=chunk_metadata,
            parent_section_id=parent_section_id,
        )
    
    def _log_chunking_stats(self, chunked_doc: ChunkedDocument) -> None:
        """
        Log chunking statistics.
        
        Args:
            chunked_doc: Chunked document
        """
        total_chunks = chunked_doc.get_total_chunks()
        total_tokens = chunked_doc.get_total_tokens()
        avg_chunk_size = chunked_doc.get_average_chunk_size()
        
        # Calculate token distribution
        token_counts = [chunk.token_count for chunk in chunked_doc.chunks]
        min_tokens = min(token_counts) if token_counts else 0
        max_tokens = max(token_counts) if token_counts else 0
        
        logger.info(
            f"Chunking completed",
            extra={
                "document_id": str(chunked_doc.document_id),
                "total_chunks": total_chunks,
                "total_tokens": total_tokens,
                "avg_chunk_size": round(avg_chunk_size, 2),
                "min_tokens": min_tokens,
                "max_tokens": max_tokens,
                "target_max_tokens": self.max_tokens,
            }
        )
