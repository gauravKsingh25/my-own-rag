"""Context optimization for LLM input preparation."""
from typing import List, Optional, Any
import numpy as np

from app.services.generation.token_budget import TokenBudgetManager
from app.core.logging import get_logger

logger = get_logger(__name__)


class ContextOptimizer:
    """
    Optimize retrieved context for LLM consumption.
    
    Features:
    - Remove near-duplicate chunks (cosine similarity > 0.95)
    - Apply lost-in-the-middle mitigation (reorder for better attention)
    - Truncate lowest-scoring chunks if budget exceeded
    - Preserve important metadata
    - Track optimization statistics
    """
    
    def __init__(
        self,
        token_budget_manager: Optional[TokenBudgetManager] = None,
        similarity_threshold: float = 0.95,
    ):
        """
        Initialize context optimizer.
        
        Args:
            token_budget_manager: Token budget manager instance
            similarity_threshold: Threshold for near-duplicate detection
        """
        self.token_budget_manager = token_budget_manager or TokenBudgetManager()
        self.similarity_threshold = similarity_threshold
        
        logger.info(
            f"ContextOptimizer initialized",
            extra={
                "similarity_threshold": similarity_threshold,
            }
        )
    
    def optimize(
        self,
        retrieval_results: List[Any],
        context_budget: int,
        preserve_metadata: bool = True,
    ) -> List[Any]:
        """
        Optimize retrieval results for LLM context.
        
        Pipeline:
        1. Remove near-duplicates
        2. Truncate to budget
        3. Apply lost-in-the-middle reordering
        
        Args:
            retrieval_results: List of RetrievalResult objects
            context_budget: Available token budget for context
            preserve_metadata: Keep all metadata fields
            
        Returns:
            List[Any]: Optimized retrieval results
        """
        if not retrieval_results:
            logger.warning("No retrieval results to optimize")
            return []
        
        logger.info(
            f"Starting context optimization",
            extra={
                "initial_count": len(retrieval_results),
                "context_budget": context_budget,
            }
        )
        
        original_count = len(retrieval_results)
        
        # Step 1: Remove near-duplicates
        deduplicated = self._remove_duplicates(retrieval_results)
        
        dedup_count = len(deduplicated)
        logger.info(
            f"Deduplication complete",
            extra={
                "original": original_count,
                "deduplicated": dedup_count,
                "removed": original_count - dedup_count,
            }
        )
        
        # Step 2: Truncate to budget
        within_budget = self._truncate_to_budget(
            deduplicated,
            context_budget,
        )
        
        truncated_count = len(within_budget)
        logger.info(
            f"Budget truncation complete",
            extra={
                "before_truncation": dedup_count,
                "after_truncation": truncated_count,
                "removed": dedup_count - truncated_count,
            }
        )
        
        # Step 3: Apply lost-in-the-middle reordering
        reordered = self._reorder_lost_in_middle(within_budget)
        
        # Calculate final token usage
        final_tokens = sum(
            self.token_budget_manager.count_tokens(r.content)
            for r in reordered
        )
        
        logger.info(
            f"Context optimization complete",
            extra={
                "original_count": original_count,
                "final_count": len(reordered),
                "final_tokens": final_tokens,
                "budget": context_budget,
                "budget_utilization": round(final_tokens / context_budget * 100, 2) if context_budget > 0 else 0,
            }
        )
        
        return reordered
    
    def _remove_duplicates(
        self,
        retrieval_results: List[Any],
    ) -> List[Any]:
        """
        Remove near-duplicate chunks based on embedding similarity.
        
        Args:
            retrieval_results: List of retrieval results
            
        Returns:
            List[Any]: Deduplicated results
        """
        if len(retrieval_results) <= 1:
            return retrieval_results
        
        # Extract embeddings from metadata
        embeddings = []
        has_embeddings = []
        
        for result in retrieval_results:
            if hasattr(result, 'metadata') and result.metadata:
                embedding = result.metadata.get('embedding')
                if embedding:
                    embeddings.append(embedding)
                    has_embeddings.append(True)
                else:
                    has_embeddings.append(False)
            else:
                has_embeddings.append(False)
        
        # If no embeddings available, skip deduplication
        if not any(has_embeddings):
            logger.warning("No embeddings available for deduplication")
            return retrieval_results
        
        # Convert to numpy for efficient computation
        valid_indices = [i for i, has_emb in enumerate(has_embeddings) if has_emb]
        
        if len(valid_indices) <= 1:
            return retrieval_results
        
        valid_embeddings = np.array([embeddings[i] for i in range(len(embeddings))], dtype=np.float32)
        
        # Normalize embeddings
        norms = np.linalg.norm(valid_embeddings, axis=1, keepdims=True)
        valid_embeddings = valid_embeddings / (norms + 1e-8)
        
        # Compute similarity matrix
        similarity_matrix = np.dot(valid_embeddings, valid_embeddings.T)
        
        # Find near-duplicates
        keep_mask = np.ones(len(retrieval_results), dtype=bool)
        
        for i in range(len(valid_indices)):
            if not keep_mask[valid_indices[i]]:
                continue
            
            # Check similarity with later items
            for j in range(i + 1, len(valid_indices)):
                if not keep_mask[valid_indices[j]]:
                    continue
                
                similarity = similarity_matrix[i, j]
                
                if similarity > self.similarity_threshold:
                    # Remove the lower-scoring duplicate
                    idx_i = valid_indices[i]
                    idx_j = valid_indices[j]
                    
                    score_i = retrieval_results[idx_i].score
                    score_j = retrieval_results[idx_j].score
                    
                    if score_j < score_i:
                        keep_mask[idx_j] = False
                        logger.debug(
                            f"Removing near-duplicate",
                            extra={
                                "index": idx_j,
                                "similarity": float(similarity),
                                "score": score_j,
                            }
                        )
                    else:
                        keep_mask[idx_i] = False
                        logger.debug(
                            f"Removing near-duplicate",
                            extra={
                                "index": idx_i,
                                "similarity": float(similarity),
                                "score": score_i,
                            }
                        )
                        break
        
        # Filter results
        deduplicated = [
            retrieval_results[i]
            for i in range(len(retrieval_results))
            if keep_mask[i]
        ]
        
        return deduplicated
    
    def _truncate_to_budget(
        self,
        retrieval_results: List[Any],
        context_budget: int,
    ) -> List[Any]:
        """
        Truncate results to fit within token budget.
        
        Removes lowest-scoring chunks first.
        
        Args:
            retrieval_results: List of retrieval results
            context_budget: Available token budget
            
        Returns:
            List[Any]: Truncated results
        """
        if not retrieval_results:
            return []
        
        # Extract contents and scores
        contents = [r.content for r in retrieval_results]
        scores = [r.score for r in retrieval_results]
        
        # Get indices of chunks that fit within budget
        selected_indices = self.token_budget_manager.truncate_to_budget(
            texts=contents,
            scores=scores,
            budget=context_budget,
        )
        
        # Return selected results in original order
        truncated = [retrieval_results[i] for i in selected_indices]
        
        return truncated
    
    def _reorder_lost_in_middle(
        self,
        retrieval_results: List[Any],
    ) -> List[Any]:
        """
        Apply lost-in-the-middle mitigation by reordering chunks.
        
        Strategy:
        - Place highest-scoring chunks at beginning and end
        - Place lower-scoring chunks in the middle
        
        This helps because LLMs pay more attention to beginning and end
        of context window.
        
        Order pattern for N chunks:
        [1st best, 3rd best, 5th best, ..., 6th best, 4th best, 2nd best]
        
        Args:
            retrieval_results: List of retrieval results
            
        Returns:
            List[Any]: Reordered results
        """
        if len(retrieval_results) <= 2:
            # No reordering needed for 1-2 chunks
            return retrieval_results
        
        n = len(retrieval_results)
        
        # Create new ordering
        reordered = []
        
        # Alternate between beginning and end
        left = 0
        right = n - 1
        take_from_left = True
        
        while left <= right:
            if take_from_left:
                reordered.append(retrieval_results[left])
                left += 1
            else:
                reordered.append(retrieval_results[right])
                right -= 1
            
            take_from_left = not take_from_left
        
        logger.info(
            f"Applied lost-in-the-middle reordering",
            extra={
                "chunks": n,
                "first_score": reordered[0].score,
                "last_score": reordered[-1].score,
            }
        )
        
        return reordered
    
    def get_optimization_stats(
        self,
        original_results: List[Any],
        optimized_results: List[Any],
    ) -> dict:
        """
        Calculate statistics about optimization process.
        
        Args:
            original_results: Original retrieval results
            optimized_results: Optimized results
            
        Returns:
            dict: Optimization statistics
        """
        original_tokens = sum(
            self.token_budget_manager.count_tokens(r.content)
            for r in original_results
        )
        
        optimized_tokens = sum(
            self.token_budget_manager.count_tokens(r.content)
            for r in optimized_results
        )
        
        stats = {
            "original_count": len(original_results),
            "optimized_count": len(optimized_results),
            "removed_count": len(original_results) - len(optimized_results),
            "removal_rate": round(
                (len(original_results) - len(optimized_results)) / len(original_results) * 100, 2
            ) if original_results else 0,
            "original_tokens": original_tokens,
            "optimized_tokens": optimized_tokens,
            "token_reduction": original_tokens - optimized_tokens,
            "token_reduction_rate": round(
                (original_tokens - optimized_tokens) / original_tokens * 100, 2
            ) if original_tokens > 0 else 0,
        }
        
        return stats
