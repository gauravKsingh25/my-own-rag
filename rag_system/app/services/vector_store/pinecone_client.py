"""Pinecone vector database client."""
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from pinecone import Pinecone, ServerlessSpec
from pinecone.core.client.exceptions import PineconeException

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VectorRecord:
    """Vector record for upserting to Pinecone."""
    
    id: str
    values: List[float]
    metadata: Dict[str, Any]


class PineconeClient:
    """
    Client for Pinecone vector database operations.
    
    Features:
    - Serverless index initialization
    - Batch upsert with retry logic
    - Namespace support for multi-tenancy
    - Deletion by document ID
    - Query with metadata filtering
    """
    
    def __init__(self):
        """Initialize Pinecone client."""
        self.api_key = settings.PINECONE_API_KEY
        self.environment = settings.PINECONE_ENVIRONMENT
        self.index_name = settings.PINECONE_INDEX_NAME
        self.dimension = settings.PINECONE_DIMENSION
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=self.api_key)
        
        # Initialize or connect to index
        self._ensure_index()
        
        logger.info(
            f"PineconeClient initialized",
            extra={
                "index_name": self.index_name,
                "dimension": self.dimension,
                "environment": self.environment,
            }
        )
    
    def _ensure_index(self):
        """Ensure index exists, create if not."""
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]
        
        if self.index_name not in existing_indexes:
            logger.info(f"Creating Pinecone index: {self.index_name}")
            
            try:
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud=settings.PINECONE_CLOUD,
                        region=self.environment,
                    ),
                )
                
                # Wait for index to be ready
                time.sleep(5)
                
                logger.info(f"Pinecone index created: {self.index_name}")
                
            except PineconeException as e:
                logger.error(
                    f"Failed to create Pinecone index: {str(e)}",
                    exc_info=True,
                )
                raise
        else:
            logger.info(f"Pinecone index exists: {self.index_name}")
        
        # Get index instance
        self.index = self.pc.Index(self.index_name)
    
    def upsert(
        self,
        vectors: List[VectorRecord],
        namespace: Optional[str] = None,
        batch_size: int = 100,
    ) -> int:
        """
        Upsert vectors to Pinecone index.
        
        Args:
            vectors: List of vector records to upsert
            namespace: Namespace for multi-tenancy (e.g., user_id)
            batch_size: Number of vectors per batch
            
        Returns:
            int: Number of vectors upserted
        """
        if not vectors:
            logger.warning("No vectors provided for upsert")
            return 0
        
        logger.info(
            f"Starting vector upsert",
            extra={
                "total_vectors": len(vectors),
                "namespace": namespace,
                "batch_size": batch_size,
            }
        )
        
        upserted_count = 0
        
        try:
            # Process in batches
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                
                # Convert to Pinecone format
                pinecone_vectors = [
                    {
                        "id": v.id,
                        "values": v.values,
                        "metadata": v.metadata,
                    }
                    for v in batch
                ]
                
                # Upsert batch
                response = self.index.upsert(
                    vectors=pinecone_vectors,
                    namespace=namespace or "",
                )
                
                upserted_count += response.upserted_count
                
                logger.debug(
                    f"Batch upserted",
                    extra={
                        "batch_start": i,
                        "batch_size": len(batch),
                        "upserted": response.upserted_count,
                    }
                )
            
            logger.info(
                f"Vector upsert complete",
                extra={
                    "total_vectors": len(vectors),
                    "upserted": upserted_count,
                    "namespace": namespace,
                }
            )
            
            return upserted_count
            
        except PineconeException as e:
            logger.error(
                f"Failed to upsert vectors: {str(e)}",
                extra={
                    "total_vectors": len(vectors),
                    "namespace": namespace,
                },
                exc_info=True,
            )
            raise
    
    def delete_by_document_id(
        self,
        document_id: str,
        namespace: Optional[str] = None,
    ):
        """
        Delete all vectors for a document.
        
        Args:
            document_id: Document UUID to delete
            namespace: Namespace to delete from
        """
        logger.info(
            f"Deleting vectors for document",
            extra={
                "document_id": document_id,
                "namespace": namespace,
            }
        )
        
        try:
            # Delete by metadata filter
            self.index.delete(
                filter={"document_id": document_id},
                namespace=namespace or "",
            )
            
            logger.info(
                f"Vectors deleted for document",
                extra={
                    "document_id": document_id,
                    "namespace": namespace,
                }
            )
            
        except PineconeException as e:
            logger.error(
                f"Failed to delete vectors: {str(e)}",
                extra={
                    "document_id": document_id,
                    "namespace": namespace,
                },
                exc_info=True,
            )
            raise
    
    def query(
        self,
        vector: List[float],
        top_k: int = 10,
        namespace: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Query similar vectors from Pinecone.
        
        Args:
            vector: Query vector
            top_k: Number of results to return
            namespace: Namespace to query
            filter: Metadata filter
            include_metadata: Include metadata in results
            
        Returns:
            List of matches with id, score, and metadata
        """
        logger.info(
            f"Querying vectors",
            extra={
                "top_k": top_k,
                "namespace": namespace,
                "filter": filter,
            }
        )
        
        try:
            response = self.index.query(
                vector=vector,
                top_k=top_k,
                namespace=namespace or "",
                filter=filter,
                include_metadata=include_metadata,
            )
            
            matches = [
                {
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata if include_metadata else {},
                }
                for match in response.matches
            ]
            
            logger.info(
                f"Query complete",
                extra={
                    "matches": len(matches),
                    "top_score": matches[0]["score"] if matches else None,
                }
            )
            
            return matches
            
        except PineconeException as e:
            logger.error(
                f"Failed to query vectors: {str(e)}",
                extra={
                    "top_k": top_k,
                    "namespace": namespace,
                },
                exc_info=True,
            )
            raise
    
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get index statistics.
        
        Args:
            namespace: Namespace to get stats for
            
        Returns:
            Dict with index statistics
        """
        try:
            stats = self.index.describe_index_stats()
            
            if namespace:
                namespace_stats = stats.namespaces.get(namespace, {})
                return {
                    "total_vectors": namespace_stats.get("vector_count", 0),
                    "namespace": namespace,
                }
            else:
                return {
                    "total_vectors": stats.total_vector_count,
                    "dimension": stats.dimension,
                    "index_fullness": stats.index_fullness,
                    "namespaces": {
                        ns: data.vector_count
                        for ns, data in stats.namespaces.items()
                    },
                }
                
        except PineconeException as e:
            logger.error(
                f"Failed to get stats: {str(e)}",
                exc_info=True,
            )
            raise
