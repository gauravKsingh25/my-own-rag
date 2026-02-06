"""Hybrid retrieval engine combining vector and BM25 search."""
from typing import List, Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.retrieval.query_classifier import QueryClassifier, QueryType
from app.services.retrieval.query_transformer import QueryTransformer
from app.services.retrieval.bm25_service import BM25Service, BM25Result
from app.services.retrieval.mmr import MMR
from app.services.retrieval.scoring import ScoringService
from app.services.vector_store import PineconeClient
from app.services.database import ChunkService
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievalResult:
    """Unified retrieval result."""
    
    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    vector_score: float
    bm25_score: float
    recency_score: float
    chunk_index: int
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "chunk_id": str(self.chunk_id),
            "document_id": str(self.document_id),
            "content": self.content,
            "score": self.score,
            "vector_score": self.vector_score,
            "bm25_score": self.bm25_score,
            "recency_score": self.recency_score,
            "chunk_index": self.chunk_index,
            "section_title": self.section_title,
            "page_number": self.page_number,
            "metadata": self.metadata,
        }


class HybridRetriever:
    """
    Hybrid retrieval engine combining vector search and BM25.
    
    Retrieval pipeline:
    1. Query classification
    2. Query transformation (normalization + embedding)
    3. Parallel retrieval:
       - Pinecone vector search (top 50)
       - PostgreSQL BM25 search (top 20)
    4. Score normalization
    5. Score combination (0.7*vector + 0.2*bm25 + 0.1*recency)
    6. MMR diversification
    7. Return top_k results
    """
    
    def __init__(
        self,
        pinecone_client: Optional[PineconeClient] = None,
        query_classifier: Optional[QueryClassifier] = None,
        query_transformer: Optional[QueryTransformer] = None,
    ):
        """
        Initialize hybrid retriever.
        
        Args:
            pinecone_client: Pinecone client instance
            query_classifier: Query classifier instance
            query_transformer: Query transformer instance
        """
        self.pinecone_client = pinecone_client or PineconeClient()
        self.query_classifier = query_classifier or QueryClassifier()
        self.query_transformer = query_transformer or QueryTransformer()
        
        logger.info("HybridRetriever initialized")
    
    async def retrieve(
        self,
        query: str,
        user_id: str,
        db: AsyncSession,
        top_k: int = 5,
        document_id: Optional[UUID] = None,
        vector_top_k: int = 50,
        bm25_top_k: int = 20,
        apply_mmr: bool = True,
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant chunks using hybrid search.
        
        Args:
            query: User query
            user_id: User ID for filtering
            db: Database session
            top_k: Number of final results to return
            document_id: Optional document ID filter
            vector_top_k: Number of vector search results
            bm25_top_k: Number of BM25 search results
            apply_mmr: Apply MMR diversification
            
        Returns:
            List[RetrievalResult]: Ranked retrieval results
        """
        logger.info(
            f"Starting hybrid retrieval",
            extra={
                "query_preview": query[:100],
                "user_id": user_id,
                "top_k": top_k,
                "document_id": str(document_id) if document_id else None,
            }
        )
        
        # Step 1: Classify query
        query_type = self.query_classifier.classify(query)
        retrieval_params = self.query_classifier.get_retrieval_params(query_type)
        
        # Override defaults with classifier recommendations
        if top_k == 5:  # Only override if using default
            top_k = retrieval_params["top_k"]
        
        logger.info(
            f"Query classified",
            extra={
                "query_type": query_type.value,
                "recommended_top_k": retrieval_params["top_k"],
            }
        )
        
        # Step 2: Transform query
        transformed = await self.query_transformer.transform(query)
        query_embedding = transformed["embedding"]
        normalized_query = transformed["normalized_query"]
        
        # Step 3: Parallel retrieval
        import asyncio
        
        vector_task = self._vector_search(
            query_embedding=query_embedding,
            user_id=user_id,
            top_k=vector_top_k,
            document_id=document_id,
        )
        
        bm25_task = BM25Service.search(
            query=normalized_query,
            user_id=user_id,
            db=db,
            top_k=bm25_top_k,
            document_id=document_id,
        )
        
        vector_results, bm25_results = await asyncio.gather(
            vector_task,
            bm25_task,
        )
        
        logger.info(
            f"Retrieval complete",
            extra={
                "vector_results": len(vector_results),
                "bm25_results": len(bm25_results),
            }
        )
        
        # Step 4: Merge and deduplicate results
        merged_results = await self._merge_results(
            vector_results=vector_results,
            bm25_results=bm25_results,
            db=db,
        )
        
        if not merged_results:
            logger.warning("No results found after merging")
            return []
        
        # Step 5: Normalize and combine scores
        scored_results = self._combine_scores(
            results=merged_results,
            vector_weight=retrieval_params["vector_weight"],
            bm25_weight=retrieval_params["bm25_weight"],
            recency_weight=retrieval_params["recency_weight"],
        )
        
        # Step 6: Apply MMR for diversification
        if apply_mmr and len(scored_results) > top_k:
            scored_results = self._apply_mmr(
                results=scored_results,
                query_embedding=query_embedding,
                top_k=top_k,
                lambda_param=retrieval_params["mmr_lambda"],
            )
        else:
            # Simple ranking by combined score
            scored_results = ScoringService.rank_results(scored_results, "score")[:top_k]
        
        # Step 7: Convert to RetrievalResult objects
        final_results = [
            RetrievalResult(
                chunk_id=UUID(r["chunk_id"]),
                document_id=UUID(r["document_id"]),
                content=r["content"],
                score=r["score"],
                vector_score=r["vector_score"],
                bm25_score=r["bm25_score"],
                recency_score=r["recency_score"],
                chunk_index=r["chunk_index"],
                section_title=r.get("section_title"),
                page_number=r.get("page_number"),
                metadata=r.get("metadata"),
            )
            for r in scored_results
        ]
        
        logger.info(
            f"Hybrid retrieval complete",
            extra={
                "query_preview": query[:100],
                "query_type": query_type.value,
                "results_count": len(final_results),
                "top_score": final_results[0].score if final_results else 0.0,
            }
        )
        
        return final_results
    
    async def _vector_search(
        self,
        query_embedding: List[float],
        user_id: str,
        top_k: int,
        document_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform vector search in Pinecone.
        
        Args:
            query_embedding: Query embedding vector
            user_id: User ID namespace
            top_k: Number of results
            document_id: Optional document filter
            
        Returns:
            List[Dict]: Vector search results
        """
        # Build metadata filter
        filter_dict = {}
        if document_id:
            filter_dict["document_id"] = str(document_id)
        
        # Query Pinecone
        matches = self.pinecone_client.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=user_id,
            filter=filter_dict if filter_dict else None,
            include_metadata=True,
        )
        
        return matches
    
    async def _merge_results(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[BM25Result],
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Merge vector and BM25 results, deduplicate by chunk_id.
        
        Args:
            vector_results: Pinecone results
            bm25_results: BM25 results
            db: Database session
            
        Returns:
            List[Dict]: Merged results with all metadata
        """
        # Create lookup by chunk_id
        results_map = {}
        
        # Add vector results
        for match in vector_results:
            metadata = match.get("metadata", {})
            chunk_id = metadata.get("chunk_id")
            
            if not chunk_id:
                # Extract from ID (format: document_id#chunk_index)
                vector_id = match["id"]
                document_id, chunk_index = vector_id.split("#")
                # We need to look up chunk_id from database
                continue
            
            results_map[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": metadata.get("document_id"),
                "content": metadata.get("content", ""),
                "vector_score": match["score"],
                "bm25_score": 0.0,
                "chunk_index": metadata.get("chunk_index", 0),
                "section_title": metadata.get("section_title"),
                "page_number": metadata.get("page_number"),
                "metadata": metadata,
                "created_at": None,  # Will fetch from DB
            }
        
        # Add/merge BM25 results
        for bm25_result in bm25_results:
            chunk_id = str(bm25_result.chunk_id)
            
            if chunk_id in results_map:
                # Update existing with BM25 score
                results_map[chunk_id]["bm25_score"] = bm25_result.score
            else:
                # Add new result
                results_map[chunk_id] = {
                    "chunk_id": chunk_id,
                    "document_id": str(bm25_result.document_id),
                    "content": bm25_result.content,
                    "vector_score": 0.0,
                    "bm25_score": bm25_result.score,
                    "chunk_index": bm25_result.chunk_index,
                    "section_title": bm25_result.section_title,
                    "page_number": bm25_result.page_number,
                    "metadata": {},
                    "created_at": None,
                }
        
        # Fetch chunk metadata from database to get created_at
        chunk_ids = [UUID(cid) for cid in results_map.keys()]
        chunks = await ChunkService.get_by_ids(chunk_ids, db)
        
        for chunk in chunks:
            chunk_id = str(chunk.id)
            if chunk_id in results_map:
                results_map[chunk_id]["created_at"] = chunk.created_at
                # Update content if missing
                if not results_map[chunk_id]["content"]:
                    results_map[chunk_id]["content"] = chunk.content
        
        return list(results_map.values())
    
    def _combine_scores(
        self,
        results: List[Dict[str, Any]],
        vector_weight: float,
        bm25_weight: float,
        recency_weight: float,
    ) -> List[Dict[str, Any]]:
        """
        Normalize and combine scores.
        
        Args:
            results: Merged results
            vector_weight: Vector score weight
            bm25_weight: BM25 score weight
            recency_weight: Recency score weight
            
        Returns:
            List[Dict]: Results with combined scores
        """
        # Extract individual scores
        vector_scores = [r["vector_score"] for r in results]
        bm25_scores = [r["bm25_score"] for r in results]
        
        # Calculate recency scores
        recency_scores = []
        for r in results:
            if r["created_at"]:
                recency = ScoringService.calculate_recency_score(r["created_at"])
            else:
                recency = 0.0
            recency_scores.append(recency)
        
        # Normalize scores
        norm_vector = ScoringService.normalize_scores(vector_scores)
        norm_bm25 = ScoringService.normalize_scores(bm25_scores)
        norm_recency = ScoringService.normalize_scores(recency_scores)
        
        # Combine scores
        combined = ScoringService.combine_scores(
            vector_scores=norm_vector,
            bm25_scores=norm_bm25,
            recency_scores=norm_recency,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
            recency_weight=recency_weight,
        )
        
        # Attach combined scores and normalized individual scores
        for i, r in enumerate(results):
            r["score"] = combined[i]
            r["vector_score"] = norm_vector[i]
            r["bm25_score"] = norm_bm25[i]
            r["recency_score"] = norm_recency[i]
        
        return results
    
    def _apply_mmr(
        self,
        results: List[Dict[str, Any]],
        query_embedding: List[float],
        top_k: int,
        lambda_param: float,
    ) -> List[Dict[str, Any]]:
        """
        Apply MMR for result diversification.
        
        Args:
            results: Scored results
            query_embedding: Query embedding
            top_k: Number of results to return
            lambda_param: MMR lambda parameter
            
        Returns:
            List[Dict]: Diversified results
        """
        # Extract embeddings from metadata
        # Note: For BM25-only results, we don't have embeddings
        # Filter to only results with embeddings
        results_with_emb = [
            r for r in results
            if r.get("metadata") and "embedding" in r["metadata"]
        ]
        
        if len(results_with_emb) < top_k:
            # Not enough results with embeddings, return all sorted by score
            logger.warning(
                f"Insufficient results with embeddings for MMR: {len(results_with_emb)}",
                extra={"required": top_k}
            )
            return ScoringService.rank_results(results, "score")[:top_k]
        
        # Extract embeddings and scores
        embeddings = [r["metadata"]["embedding"] for r in results_with_emb]
        scores = [r["score"] for r in results_with_emb]
        
        # Apply MMR
        selected_indices = MMR.rerank(
            query_embedding=query_embedding,
            candidate_embeddings=embeddings,
            candidate_scores=scores,
            top_k=top_k,
            lambda_param=lambda_param,
        )
        
        # Return selected results
        diversified = [results_with_emb[i] for i in selected_indices]
        
        return diversified
