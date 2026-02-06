"""Maximal Marginal Relevance (MMR) for result diversification."""
from typing import List, Tuple
import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)


class MMR:
    """
    Maximal Marginal Relevance algorithm for diversifying search results.
    
    MMR balances relevance and diversity by selecting results that are:
    1. Highly relevant to the query
    2. Minimally similar to already selected results
    
    Formula:
        MMR = λ * Sim(D, Q) - (1-λ) * max[Sim(D, d) for d in Selected]
        
    Where:
        - D: candidate document
        - Q: query
        - Selected: already selected documents
        - λ: trade-off parameter (0 to 1)
          - λ = 1: pure relevance (no diversity)
          - λ = 0: pure diversity (no relevance)
          - λ = 0.7: good balance (default)
    """
    
    @staticmethod
    def rerank(
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        candidate_scores: List[float],
        top_k: int,
        lambda_param: float = 0.7,
    ) -> List[int]:
        """
        Rerank candidates using MMR for diversity.
        
        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of candidate embedding vectors
            candidate_scores: Initial relevance scores for candidates
            top_k: Number of results to return
            lambda_param: MMR trade-off parameter (0-1)
                - Higher values favor relevance
                - Lower values favor diversity
            
        Returns:
            List[int]: Indices of selected candidates in ranked order
        """
        if not candidate_embeddings:
            logger.warning("No candidates provided for MMR reranking")
            return []
        
        if top_k <= 0:
            logger.warning(f"Invalid top_k: {top_k}")
            return []
        
        logger.info(
            f"Starting MMR reranking",
            extra={
                "candidates": len(candidate_embeddings),
                "top_k": top_k,
                "lambda": lambda_param,
            }
        )
        
        # Convert to numpy arrays for efficient computation
        query_emb = np.array(query_embedding, dtype=np.float32)
        candidate_embs = np.array(candidate_embeddings, dtype=np.float32)
        
        # Normalize embeddings for cosine similarity
        query_emb = query_emb / np.linalg.norm(query_emb)
        candidate_norms = np.linalg.norm(candidate_embs, axis=1, keepdims=True)
        candidate_embs = candidate_embs / (candidate_norms + 1e-8)
        
        # Compute query-candidate similarities
        query_similarities = np.dot(candidate_embs, query_emb)
        
        # Initialize selected and remaining indices
        selected_indices = []
        remaining_indices = list(range(len(candidate_embeddings)))
        
        # Select first document (highest relevance score)
        first_idx = remaining_indices[np.argmax(candidate_scores)]
        selected_indices.append(first_idx)
        remaining_indices.remove(first_idx)
        
        # Iteratively select remaining documents
        while len(selected_indices) < min(top_k, len(candidate_embeddings)):
            if not remaining_indices:
                break
            
            # Compute MMR scores for remaining candidates
            mmr_scores = []
            
            for idx in remaining_indices:
                # Relevance term: similarity to query
                relevance = query_similarities[idx]
                
                # Diversity term: max similarity to already selected documents
                if selected_indices:
                    selected_embs = candidate_embs[selected_indices]
                    candidate_emb = candidate_embs[idx]
                    
                    # Compute similarities to selected documents
                    similarities_to_selected = np.dot(selected_embs, candidate_emb)
                    max_similarity = np.max(similarities_to_selected)
                else:
                    max_similarity = 0.0
                
                # MMR score
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                mmr_scores.append(mmr_score)
            
            # Select candidate with highest MMR score
            best_idx_in_remaining = np.argmax(mmr_scores)
            best_idx = remaining_indices[best_idx_in_remaining]
            
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)
        
        logger.info(
            f"MMR reranking complete",
            extra={
                "selected": len(selected_indices),
                "requested": top_k,
            }
        )
        
        return selected_indices
    
    @staticmethod
    def calculate_diversity_score(
        embeddings: List[List[float]],
    ) -> float:
        """
        Calculate diversity score for a set of embeddings.
        
        Diversity score is 1 - average pairwise similarity.
        - Score near 1: high diversity
        - Score near 0: low diversity
        
        Args:
            embeddings: List of embedding vectors
            
        Returns:
            float: Diversity score (0-1)
        """
        if len(embeddings) < 2:
            return 1.0  # Single item is perfectly diverse
        
        # Convert to numpy
        embs = np.array(embeddings, dtype=np.float32)
        
        # Normalize
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        embs = embs / (norms + 1e-8)
        
        # Compute pairwise similarities
        similarity_matrix = np.dot(embs, embs.T)
        
        # Get upper triangle (exclude diagonal)
        n = len(embeddings)
        upper_triangle = similarity_matrix[np.triu_indices(n, k=1)]
        
        # Average similarity
        avg_similarity = np.mean(upper_triangle)
        
        # Diversity score
        diversity = 1.0 - avg_similarity
        
        return float(diversity)
