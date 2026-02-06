"""BM25 full-text search service using PostgreSQL."""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.logging import get_logger

logger = get_logger(__name__)


class BM25Result:
    """BM25 search result."""
    
    def __init__(
        self,
        chunk_id: UUID,
        document_id: UUID,
        content: str,
        score: float,
        chunk_index: int,
        section_title: Optional[str] = None,
        page_number: Optional[int] = None,
    ):
        """Initialize BM25 result."""
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.content = content
        self.score = score
        self.chunk_index = chunk_index
        self.section_title = section_title
        self.page_number = page_number
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "chunk_id": str(self.chunk_id),
            "document_id": str(self.document_id),
            "content": self.content,
            "score": self.score,
            "chunk_index": self.chunk_index,
            "section_title": self.section_title,
            "page_number": self.page_number,
        }


class BM25Service:
    """
    BM25 full-text search using PostgreSQL tsvector.
    
    Features:
    - PostgreSQL ts_rank_cd for BM25-like scoring
    - GIN index for fast search
    - User-based filtering
    - Document-based filtering
    - Weighted search (section_title > content)
    """
    
    @staticmethod
    async def search(
        query: str,
        user_id: str,
        db: AsyncSession,
        top_k: int = 20,
        document_id: Optional[UUID] = None,
    ) -> List[BM25Result]:
        """
        Perform BM25 full-text search.
        
        Args:
            query: Search query
            user_id: User ID for filtering
            db: Database session
            top_k: Number of results to return
            document_id: Optional document ID filter
            
        Returns:
            List[BM25Result]: Ranked search results
        """
        if not query or not query.strip():
            logger.warning("Empty query provided for BM25 search")
            return []
        
        logger.info(
            f"Starting BM25 search",
            extra={
                "query_preview": query[:100],
                "user_id": user_id,
                "top_k": top_k,
                "document_id": str(document_id) if document_id else None,
            }
        )
        
        # Prepare search query
        # Convert user query to tsquery format
        # Use plainto_tsquery for automatic phrase handling
        search_terms = query.strip()
        
        # Build SQL query
        # ts_rank_cd uses Cover Density ranking (BM25-like)
        # Normalization flag 1 = divide rank by document length
        sql_query = """
            SELECT 
                id,
                document_id,
                content,
                chunk_index,
                section_title,
                page_number,
                ts_rank_cd(
                    content_tsvector, 
                    plainto_tsquery('english', :query),
                    1  -- Normalization: divide by document length
                ) AS bm25_score
            FROM chunks
            WHERE 
                user_id = :user_id
                AND content_tsvector @@ plainto_tsquery('english', :query)
        """
        
        params = {
            "query": search_terms,
            "user_id": user_id,
            "top_k": top_k,
        }
        
        # Add optional document filter
        if document_id:
            sql_query += " AND document_id = :document_id"
            params["document_id"] = str(document_id)
        
        # Order by score and limit
        sql_query += """
            ORDER BY bm25_score DESC
            LIMIT :top_k
        """
        
        # Execute query
        try:
            result = await db.execute(text(sql_query), params)
            rows = result.fetchall()
            
            # Convert to BM25Result objects
            results = []
            for row in rows:
                bm25_result = BM25Result(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    content=row.content,
                    score=float(row.bm25_score),
                    chunk_index=row.chunk_index,
                    section_title=row.section_title,
                    page_number=row.page_number,
                )
                results.append(bm25_result)
            
            logger.info(
                f"BM25 search complete",
                extra={
                    "query_preview": query[:100],
                    "results_count": len(results),
                    "top_score": results[0].score if results else 0.0,
                }
            )
            
            return results
            
        except Exception as e:
            logger.error(
                f"BM25 search failed: {str(e)}",
                extra={
                    "query": query,
                    "user_id": user_id,
                },
                exc_info=True,
            )
            raise
    
    @staticmethod
    async def multi_search(
        queries: List[str],
        user_id: str,
        db: AsyncSession,
        top_k: int = 20,
        document_id: Optional[UUID] = None,
    ) -> Dict[str, List[BM25Result]]:
        """
        Perform multiple BM25 searches in parallel.
        
        Args:
            queries: List of search queries
            user_id: User ID for filtering
            db: Database session
            top_k: Number of results per query
            document_id: Optional document ID filter
            
        Returns:
            Dict[str, List[BM25Result]]: Query to results mapping
        """
        import asyncio
        
        logger.info(
            f"Starting multi-BM25 search",
            extra={
                "queries_count": len(queries),
                "user_id": user_id,
                "top_k": top_k,
            }
        )
        
        # Execute searches concurrently
        tasks = [
            BM25Service.search(
                query=query,
                user_id=user_id,
                db=db,
                top_k=top_k,
                document_id=document_id,
            )
            for query in queries
        ]
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Map results to queries
        results_map = {}
        for query, results in zip(queries, results_list):
            if isinstance(results, Exception):
                logger.error(
                    f"Query failed in multi-search: {str(results)}",
                    extra={"query": query}
                )
                results_map[query] = []
            else:
                results_map[query] = results
        
        logger.info(
            f"Multi-BM25 search complete",
            extra={
                "queries_count": len(queries),
                "total_results": sum(len(r) for r in results_map.values()),
            }
        )
        
        return results_map
