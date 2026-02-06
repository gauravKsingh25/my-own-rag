"""Query classification for adaptive retrieval strategies."""
from enum import Enum
from typing import Optional
import re

from app.core.logging import get_logger

logger = get_logger(__name__)


class QueryType(str, Enum):
    """Query type enumeration."""
    
    FACTUAL = "factual"
    COMPARATIVE = "comparative"
    TEMPORAL = "temporal"
    CONVERSATIONAL = "conversational"
    MULTI_HOP = "multi_hop"


class QueryClassifier:
    """
    Classify user queries to optimize retrieval strategy.
    
    Classification types:
    - FACTUAL: Direct fact lookup (who, what, when, where)
    - COMPARATIVE: Comparison between entities (vs, compare, difference)
    - TEMPORAL: Time-based queries (before, after, during, recent)
    - CONVERSATIONAL: Follow-up or contextual queries
    - MULTI_HOP: Complex queries requiring multiple retrieval steps
    """
    
    # Pattern definitions for classification
    FACTUAL_PATTERNS = [
        r'\b(what|who|when|where|which|how many|how much)\b',
        r'\b(define|definition|explain|describe)\b',
        r'\b(is|are|was|were|does|did)\b.*\?',
    ]
    
    COMPARATIVE_PATTERNS = [
        r'\b(vs|versus|compare|comparison|difference|similar|different)\b',
        r'\b(better|worse|more|less|greater|smaller)\s+than\b',
        r'\b(advantage|disadvantage|pros|cons)\b',
    ]
    
    TEMPORAL_PATTERNS = [
        r'\b(before|after|during|since|until|between)\b',
        r'\b(recent|latest|current|past|future|history)\b',
        r'\b(today|yesterday|tomorrow|last|next)\b',
        r'\b(timeline|chronology|sequence|evolution)\b',
    ]
    
    CONVERSATIONAL_PATTERNS = [
        r'\b(also|too|as well|additionally|furthermore)\b',
        r'\b(this|that|these|those|it|they)\b',
        r'\b(tell me more|can you|what about)\b',
    ]
    
    MULTI_HOP_PATTERNS = [
        r'\band\b.*\band\b',  # Multiple conjunctions
        r'\bor\b.*\bor\b',
        r'\b(both|all|each|every)\b',
        r'\b(first.*then|step.*step)\b',
        r'\b(because|therefore|thus|hence)\b',
    ]
    
    def __init__(self):
        """Initialize query classifier."""
        # Compile patterns for efficiency
        self.factual_regex = [re.compile(p, re.IGNORECASE) for p in self.FACTUAL_PATTERNS]
        self.comparative_regex = [re.compile(p, re.IGNORECASE) for p in self.COMPARATIVE_PATTERNS]
        self.temporal_regex = [re.compile(p, re.IGNORECASE) for p in self.TEMPORAL_PATTERNS]
        self.conversational_regex = [re.compile(p, re.IGNORECASE) for p in self.CONVERSATIONAL_PATTERNS]
        self.multi_hop_regex = [re.compile(p, re.IGNORECASE) for p in self.MULTI_HOP_PATTERNS]
        
        logger.info("QueryClassifier initialized")
    
    def classify(self, query: str) -> QueryType:
        """
        Classify query into one of the defined types.
        
        Args:
            query: User query string
            
        Returns:
            QueryType: Classified query type
        """
        if not query or not query.strip():
            logger.warning("Empty query provided for classification")
            return QueryType.CONVERSATIONAL
        
        query = query.strip()
        
        # Score each category
        scores = {
            QueryType.FACTUAL: self._score_patterns(query, self.factual_regex),
            QueryType.COMPARATIVE: self._score_patterns(query, self.comparative_regex),
            QueryType.TEMPORAL: self._score_patterns(query, self.temporal_regex),
            QueryType.CONVERSATIONAL: self._score_patterns(query, self.conversational_regex),
            QueryType.MULTI_HOP: self._score_patterns(query, self.multi_hop_regex),
        }
        
        # Multi-hop has priority if score is high enough
        if scores[QueryType.MULTI_HOP] >= 2:
            classified_type = QueryType.MULTI_HOP
        else:
            # Select type with highest score
            classified_type = max(scores, key=scores.get)
            
            # Default to factual if all scores are 0
            if scores[classified_type] == 0:
                classified_type = QueryType.FACTUAL
        
        logger.info(
            f"Query classified",
            extra={
                "query_preview": query[:100],
                "query_type": classified_type.value,
                "scores": {k.value: v for k, v in scores.items()},
            }
        )
        
        return classified_type
    
    def _score_patterns(self, query: str, patterns: list) -> int:
        """
        Score query against list of regex patterns.
        
        Args:
            query: Query string
            patterns: List of compiled regex patterns
            
        Returns:
            int: Number of matching patterns
        """
        score = 0
        for pattern in patterns:
            if pattern.search(query):
                score += 1
        return score
    
    def get_retrieval_params(self, query_type: QueryType) -> dict:
        """
        Get recommended retrieval parameters based on query type.
        
        Args:
            query_type: Classified query type
            
        Returns:
            dict: Retrieval parameters
        """
        params = {
            QueryType.FACTUAL: {
                "top_k": 5,
                "vector_weight": 0.7,
                "bm25_weight": 0.2,
                "recency_weight": 0.1,
                "mmr_lambda": 0.5,  # Less diversity, more relevance
            },
            QueryType.COMPARATIVE: {
                "top_k": 8,
                "vector_weight": 0.6,
                "bm25_weight": 0.3,
                "recency_weight": 0.1,
                "mmr_lambda": 0.7,  # More diversity for comparison
            },
            QueryType.TEMPORAL: {
                "top_k": 5,
                "vector_weight": 0.5,
                "bm25_weight": 0.2,
                "recency_weight": 0.3,  # Higher recency weight
                "mmr_lambda": 0.6,
            },
            QueryType.CONVERSATIONAL: {
                "top_k": 5,
                "vector_weight": 0.8,  # Rely more on semantic similarity
                "bm25_weight": 0.1,
                "recency_weight": 0.1,
                "mmr_lambda": 0.5,
            },
            QueryType.MULTI_HOP: {
                "top_k": 10,  # Retrieve more for complex queries
                "vector_weight": 0.6,
                "bm25_weight": 0.3,
                "recency_weight": 0.1,
                "mmr_lambda": 0.8,  # High diversity for multi-faceted queries
            },
        }
        
        return params.get(query_type, params[QueryType.FACTUAL])
