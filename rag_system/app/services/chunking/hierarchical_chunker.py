"""Hierarchical chunker for creating parent-child chunk relationships."""
from typing import List, Dict, Optional
from uuid import UUID

from app.services.chunking.models import Chunk, ChunkedDocument
from app.services.parsing.models import ParsedDocument, ParsedSection
from app.core.logging import get_logger

logger = get_logger(__name__)


class HierarchicalChunker:
    """
    Hierarchical chunker for creating structured chunk relationships.
    
    Hierarchy:
    - Level 0: Document
    - Level 1: Section (parent)
    - Level 2: Chunk (child)
    
    This establishes parent-child relationships where:
    - Parent = Original section from parsing
    - Child = Individual chunks created from splitting sections
    """
    
    @staticmethod
    def create_section_hierarchy(
        parsed_doc: ParsedDocument,
    ) -> Dict[str, ParsedSection]:
        """
        Create a mapping of section IDs to sections.
        
        This creates the "parent" layer in the hierarchy.
        
        Args:
            parsed_doc: Parsed document with sections
            
        Returns:
            Dict[str, ParsedSection]: Mapping of section_id to section
        """
        section_map = {}
        
        for idx, section in enumerate(parsed_doc.sections):
            section_id = f"section_{idx}"
            section_map[section_id] = section
        
        logger.debug(
            f"Created section hierarchy",
            extra={
                "document_id": str(parsed_doc.document_id),
                "sections_count": len(section_map),
            }
        )
        
        return section_map
    
    @staticmethod
    def get_chunks_by_section(
        chunked_doc: ChunkedDocument,
    ) -> Dict[str, List[Chunk]]:
        """
        Group chunks by their parent section.
        
        This organizes chunks according to their hierarchical structure.
        
        Args:
            chunked_doc: Chunked document
            
        Returns:
            Dict[str, List[Chunk]]: Mapping of parent_section_id to chunks
        """
        section_chunks: Dict[str, List[Chunk]] = {}
        
        for chunk in chunked_doc.chunks:
            parent_id = chunk.parent_section_id
            
            if parent_id:
                if parent_id not in section_chunks:
                    section_chunks[parent_id] = []
                section_chunks[parent_id].append(chunk)
        
        logger.debug(
            f"Grouped chunks by section",
            extra={
                "document_id": str(chunked_doc.document_id),
                "sections_with_chunks": len(section_chunks),
            }
        )
        
        return section_chunks
    
    @staticmethod
    def validate_hierarchy(
        chunked_doc: ChunkedDocument,
        parsed_doc: ParsedDocument,
    ) -> bool:
        """
        Validate that chunk hierarchy is consistent.
        
        Checks:
        - All chunks have parent_section_id
        - All parent_section_ids reference valid sections
        - Chunk indices are sequential
        
        Args:
            chunked_doc: Chunked document
            parsed_doc: Original parsed document
            
        Returns:
            bool: True if hierarchy is valid
        """
        # Create section map
        section_map = HierarchicalChunker.create_section_hierarchy(parsed_doc)
        valid_section_ids = set(section_map.keys())
        
        # Check all chunks
        for chunk in chunked_doc.chunks:
            # Check parent_section_id exists
            if chunk.parent_section_id is None:
                logger.warning(
                    f"Chunk {chunk.chunk_index} has no parent_section_id",
                    extra={"document_id": str(chunked_doc.document_id)}
                )
                return False
            
            # Check parent_section_id is valid
            if chunk.parent_section_id not in valid_section_ids:
                logger.warning(
                    f"Chunk {chunk.chunk_index} has invalid parent_section_id: {chunk.parent_section_id}",
                    extra={"document_id": str(chunked_doc.document_id)}
                )
                return False
        
        # Check chunk indices are sequential
        expected_indices = list(range(len(chunked_doc.chunks)))
        actual_indices = [chunk.chunk_index for chunk in chunked_doc.chunks]
        
        if actual_indices != expected_indices:
            logger.warning(
                f"Chunk indices are not sequential",
                extra={
                    "document_id": str(chunked_doc.document_id),
                    "expected": expected_indices,
                    "actual": actual_indices,
                }
            )
            return False
        
        logger.debug(
            f"Hierarchy validation passed",
            extra={"document_id": str(chunked_doc.document_id)}
        )
        
        return True
    
    @staticmethod
    def get_hierarchy_stats(
        chunked_doc: ChunkedDocument,
        parsed_doc: ParsedDocument,
    ) -> Dict[str, any]:
        """
        Get statistics about chunk hierarchy.
        
        Args:
            chunked_doc: Chunked document
            parsed_doc: Original parsed document
            
        Returns:
            Dict: Hierarchy statistics
        """
        section_chunks = HierarchicalChunker.get_chunks_by_section(chunked_doc)
        
        # Calculate stats
        sections_with_chunks = len(section_chunks)
        total_sections = len(parsed_doc.sections)
        chunks_per_section = [len(chunks) for chunks in section_chunks.values()]
        
        avg_chunks_per_section = (
            sum(chunks_per_section) / len(chunks_per_section)
            if chunks_per_section else 0
        )
        max_chunks_per_section = max(chunks_per_section) if chunks_per_section else 0
        min_chunks_per_section = min(chunks_per_section) if chunks_per_section else 0
        
        stats = {
            "total_sections": total_sections,
            "sections_with_chunks": sections_with_chunks,
            "avg_chunks_per_section": round(avg_chunks_per_section, 2),
            "max_chunks_per_section": max_chunks_per_section,
            "min_chunks_per_section": min_chunks_per_section,
        }
        
        logger.debug(
            f"Hierarchy statistics",
            extra={
                "document_id": str(chunked_doc.document_id),
                **stats,
            }
        )
        
        return stats
