"""Vector storage service."""
from typing import List, Optional
from uuid import UUID

from app.services.embeddings import EmbeddedChunk
from app.services.vector_store.pinecone_client import PineconeClient, VectorRecord
from app.core.logging import get_logger

logger = get_logger(__name__)


class VectorService:
    """
    Service for managing vector storage operations.
    
    Features:
    - Convert chunks to vector records
    - Batch upsert with namespacing
    - Document deletion
    - Metadata enrichment
    """
    
    def __init__(self, pinecone_client: PineconeClient = None):
        """
        Initialize vector service.
        
        Args:
            pinecone_client: Pinecone client instance (optional)
        """
        self.pinecone_client = pinecone_client or PineconeClient()
        logger.info("VectorService initialized")
    
    def store_document_chunks(
        self,
        embedded_chunks: List[EmbeddedChunk],
        document_id: str,
        user_id: str,
    ) -> int:
        """
        Store document chunks in vector database.
        
        Args:
            embedded_chunks: Chunks with embeddings
            document_id: Document UUID
            user_id: User ID for namespacing
            
        Returns:
            int: Number of vectors stored
        """
        if not embedded_chunks:
            logger.warning("No embedded chunks to store")
            return 0
        
        logger.info(
            f"Storing document chunks",
            extra={
                "document_id": document_id,
                "user_id": user_id,
                "chunks": len(embedded_chunks),
            }
        )
        
        # Convert to vector records
        vector_records = self._chunks_to_vectors(
            embedded_chunks=embedded_chunks,
            document_id=document_id,
        )
        
        # Upsert to Pinecone with user namespace
        upserted_count = self.pinecone_client.upsert(
            vectors=vector_records,
            namespace=user_id,
        )
        
        logger.info(
            f"Document chunks stored",
            extra={
                "document_id": document_id,
                "user_id": user_id,
                "chunks": len(embedded_chunks),
                "vectors_stored": upserted_count,
            }
        )
        
        return upserted_count
    
    def delete_document(
        self,
        document_id: str,
        user_id: str,
    ):
        """
        Delete all vectors for a document.
        
        Args:
            document_id: Document UUID to delete
            user_id: User ID namespace
        """
        logger.info(
            f"Deleting document vectors",
            extra={
                "document_id": document_id,
                "user_id": user_id,
            }
        )
        
        self.pinecone_client.delete_by_document_id(
            document_id=document_id,
            namespace=user_id,
        )
        
        logger.info(
            f"Document vectors deleted",
            extra={
                "document_id": document_id,
                "user_id": user_id,
            }
        )
    
    def _chunks_to_vectors(
        self,
        embedded_chunks: List[EmbeddedChunk],
        document_id: str,
    ) -> List[VectorRecord]:
        """
        Convert embedded chunks to vector records.
        
        Args:
            embedded_chunks: Chunks with embeddings
            document_id: Document UUID
            
        Returns:
            List[VectorRecord]: Vector records for upsert
        """
        vector_records = []
        
        for embedded_chunk in embedded_chunks:
            chunk = embedded_chunk.chunk
            
            # Create vector ID: document_id + chunk_index
            vector_id = f"{document_id}#{chunk.chunk_index}"
            
            # Prepare metadata
            metadata = {
                "document_id": document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "content_hash": chunk.content_hash,
                "token_count": chunk.token_count,
                "section_title": chunk.section_title,
                "page_number": chunk.page_number,
            }
            
            # Add hierarchy if present
            if chunk.hierarchy:
                metadata["hierarchy"] = chunk.hierarchy
            
            # Create vector record
            vector_record = VectorRecord(
                id=vector_id,
                values=embedded_chunk.embedding,
                metadata=metadata,
            )
            
            vector_records.append(vector_record)
        
        return vector_records
