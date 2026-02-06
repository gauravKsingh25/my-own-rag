"""Score normalization and combination for hybrid retrieval."""
from typing import List, Dict, Any
import numpy as np
from datetime import datetime

from app.core.logging import get_logger

logger = get_logger(__name__)


class ScoringService:
    """
    Service for normalizing and combining retrieval scores.
    
    Features:
    - Min-max normalization
    - Z-score normalization
    - Weighted score combination
    - Recency scoring
    """
    
    @staticmethod
    def normalize_scores(
        scores: List[float],
        method: str = "min_max",
    ) -> List[float]:
        """
        Normalize scores to [0, 1] range.
        
        Args:
            scores: List of scores to normalize
            method: Normalization method ("min_max" or "z_score")
            
        Returns:
            List[float]: Normalized scores
        """
        if not scores:
            return []
        
        if len(scores) == 1:
            return [1.0]
        
        scores_array = np.array(scores, dtype=np.float32)
        
        if method == "min_max":
            # Min-max normalization: (x - min) / (max - min)
            min_score = np.min(scores_array)
            max_score = np.max(scores_array)
            
            if max_score - min_score < 1e-8:
                # All scores are the same
                return [1.0] * len(scores)
            
            normalized = (scores_array - min_score) / (max_score - min_score)
            
        elif method == "z_score":
            # Z-score normalization then sigmoid
            mean = np.mean(scores_array)
            std = np.std(scores_array)
            
            if std < 1e-8:
                # No variance
                return [0.5] * len(scores)
            
            z_scores = (scores_array - mean) / std
            # Apply sigmoid to map to [0, 1]
            normalized = 1.0 / (1.0 + np.exp(-z_scores))
            
        else:
            raise ValueError(f"Unknown normalization method: {method}")
        
        return normalized.tolist()
    
    @staticmethod
    def combine_scores(
        vector_scores: List[float],
        bm25_scores: List[float],
        recency_scores: List[float],
        vector_weight: float = 0.7,
        bm25_weight: float = 0.2,
        recency_weight: float = 0.1,
    ) -> List[float]:
        """
        Combine multiple score types with weights.
        
        Args:
            vector_scores: Normalized vector similarity scores
            bm25_scores: Normalized BM25 scores
            recency_scores: Normalized recency scores
            vector_weight: Weight for vector scores
            bm25_weight: Weight for BM25 scores
            recency_weight: Weight for recency scores
            
        Returns:
            List[float]: Combined scores
        """
        if not vector_scores:
            return []
        
        # Ensure all score lists have the same length
        n = len(vector_scores)
        if len(bm25_scores) != n or len(recency_scores) != n:
            raise ValueError("All score lists must have the same length")
        
        # Validate weights sum to 1.0
        total_weight = vector_weight + bm25_weight + recency_weight
        if abs(total_weight - 1.0) > 1e-6:
            logger.warning(
                f"Weights do not sum to 1.0: {total_weight}. Normalizing.",
                extra={
                    "vector_weight": vector_weight,
                    "bm25_weight": bm25_weight,
                    "recency_weight": recency_weight,
                }
            )
            vector_weight /= total_weight
            bm25_weight /= total_weight
            recency_weight /= total_weight
        
        # Convert to numpy arrays
        v_scores = np.array(vector_scores, dtype=np.float32)
        b_scores = np.array(bm25_scores, dtype=np.float32)
        r_scores = np.array(recency_scores, dtype=np.float32)
        
        # Weighted combination
        combined = (
            vector_weight * v_scores +
            bm25_weight * b_scores +
            recency_weight * r_scores
        )
        
        logger.debug(
            f"Scores combined",
            extra={
                "count": len(combined),
                "weights": {
                    "vector": vector_weight,
                    "bm25": bm25_weight,
                    "recency": recency_weight,
                },
                "max_score": float(np.max(combined)),
                "min_score": float(np.min(combined)),
            }
        )
        
        return combined.tolist()
    
    @staticmethod
    def calculate_recency_score(
        created_at: datetime,
        decay_days: int = 365,
    ) -> float:
        """
        Calculate recency score based on document age.
        
        Uses exponential decay:
            score = exp(-age_in_days / decay_days)
        
        Args:
            created_at: Document creation timestamp
            decay_days: Half-life for recency decay (default 365 days)
            
        Returns:
            float: Recency score (0-1)
        """
        now = datetime.utcnow()
        age_days = (now - created_at).total_seconds() / 86400  # Convert to days
        
        # Exponential decay
        # After decay_days, score = ~0.37
        # After 2*decay_days, score = ~0.14
        score = np.exp(-age_days / decay_days)
        
        return float(score)
    
    @staticmethod
    def calculate_recency_scores(
        timestamps: List[datetime],
        decay_days: int = 365,
    ) -> List[float]:
        """
        Calculate recency scores for multiple timestamps.
        
        Args:
            timestamps: List of creation timestamps
            decay_days: Half-life for recency decay
            
        Returns:
            List[float]: Recency scores
        """
        scores = [
            ScoringService.calculate_recency_score(ts, decay_days)
            for ts in timestamps
        ]
        
        return scores
    
    @staticmethod
    def rank_results(
        results: List[Dict[str, Any]],
        score_key: str = "score",
        reverse: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Rank results by score.
        
        Args:
            results: List of result dictionaries
            score_key: Key for score field
            reverse: If True, rank in descending order (higher is better)
            
        Returns:
            List[Dict[str, Any]]: Ranked results
        """
        ranked = sorted(
            results,
            key=lambda x: x.get(score_key, 0.0),
            reverse=reverse,
        )
        
        return ranked
