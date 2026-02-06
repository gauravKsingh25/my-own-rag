"""Token budget management for context window optimization."""
from typing import List, Optional
import tiktoken

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TokenBudgetManager:
    """
    Manage token budget for LLM context window.
    
    Features:
    - Accurate token counting with tiktoken
    - Reserve space for system prompt, query, and answer
    - Calculate available context budget
    - Handle edge cases (long queries, small budgets)
    """
    
    def __init__(
        self,
        model_max_tokens: int = None,
        max_output_tokens: int = None,
        encoding_name: str = "cl100k_base",
    ):
        """
        Initialize token budget manager.
        
        Args:
            model_max_tokens: Maximum context window size
            max_output_tokens: Maximum tokens for answer generation
            encoding_name: Tiktoken encoding name (cl100k_base for GPT-4/Gemini)
        """
        self.model_max_tokens = model_max_tokens or settings.MODEL_MAX_TOKENS
        self.max_output_tokens = max_output_tokens or settings.MAX_OUTPUT_TOKENS
        
        # Initialize tokenizer
        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except Exception as e:
            logger.warning(
                f"Failed to load encoding {encoding_name}, falling back to cl100k_base: {str(e)}"
            )
            self.encoding = tiktoken.get_encoding("cl100k_base")
        
        logger.info(
            f"TokenBudgetManager initialized",
            extra={
                "model_max_tokens": self.model_max_tokens,
                "max_output_tokens": self.max_output_tokens,
                "encoding": encoding_name,
            }
        )
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            int: Number of tokens
        """
        if not text:
            return 0
        
        try:
            tokens = self.encoding.encode(text)
            return len(tokens)
        except Exception as e:
            logger.error(
                f"Failed to count tokens: {str(e)}",
                exc_info=True
            )
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(text) // 4
    
    def count_tokens_batch(self, texts: List[str]) -> List[int]:
        """
        Count tokens for multiple texts.
        
        Args:
            texts: List of texts
            
        Returns:
            List[int]: Token counts for each text
        """
        return [self.count_tokens(text) for text in texts]
    
    def calculate_budget(
        self,
        query: str,
        system_prompt: str = "",
        safety_margin: int = 100,
    ) -> dict:
        """
        Calculate available token budget for context.
        
        Args:
            query: User query
            system_prompt: System prompt (instructions)
            safety_margin: Extra tokens to reserve for formatting
            
        Returns:
            dict: {
                "total_budget": int,
                "query_tokens": int,
                "system_tokens": int,
                "output_tokens": int,
                "safety_margin": int,
                "context_budget": int,
                "budget_exceeded": bool,
            }
        """
        # Count tokens for query and system prompt
        query_tokens = self.count_tokens(query)
        system_tokens = self.count_tokens(system_prompt)
        
        # Calculate reserved tokens
        reserved_tokens = (
            query_tokens +
            system_tokens +
            self.max_output_tokens +
            safety_margin
        )
        
        # Calculate available context budget
        context_budget = self.model_max_tokens - reserved_tokens
        
        # Check if budget is exceeded
        budget_exceeded = context_budget <= 0
        
        if budget_exceeded:
            logger.warning(
                f"Token budget exceeded",
                extra={
                    "model_max_tokens": self.model_max_tokens,
                    "reserved_tokens": reserved_tokens,
                    "context_budget": context_budget,
                    "query_tokens": query_tokens,
                }
            )
        
        logger.info(
            f"Token budget calculated",
            extra={
                "total_budget": self.model_max_tokens,
                "context_budget": context_budget,
                "reserved_tokens": reserved_tokens,
                "query_tokens": query_tokens,
            }
        )
        
        return {
            "total_budget": self.model_max_tokens,
            "query_tokens": query_tokens,
            "system_tokens": system_tokens,
            "output_tokens": self.max_output_tokens,
            "safety_margin": safety_margin,
            "context_budget": max(0, context_budget),
            "budget_exceeded": budget_exceeded,
        }
    
    def fits_budget(
        self,
        texts: List[str],
        budget: int,
    ) -> bool:
        """
        Check if texts fit within token budget.
        
        Args:
            texts: List of text chunks
            budget: Token budget
            
        Returns:
            bool: True if texts fit within budget
        """
        total_tokens = sum(self.count_tokens_batch(texts))
        return total_tokens <= budget
    
    def truncate_to_budget(
        self,
        texts: List[str],
        scores: List[float],
        budget: int,
    ) -> List[int]:
        """
        Select texts that fit within budget by removing lowest-scoring items.
        
        Args:
            texts: List of text chunks
            scores: Scores for each chunk (higher is better)
            budget: Token budget
            
        Returns:
            List[int]: Indices of selected chunks
        """
        if not texts:
            return []
        
        # Create list of (index, score, text, tokens)
        items = [
            (i, scores[i], texts[i], self.count_tokens(texts[i]))
            for i in range(len(texts))
        ]
        
        # Sort by score (descending)
        items.sort(key=lambda x: x[1], reverse=True)
        
        # Greedily select items until budget is reached
        selected_indices = []
        total_tokens = 0
        
        for idx, score, text, tokens in items:
            if total_tokens + tokens <= budget:
                selected_indices.append(idx)
                total_tokens += tokens
            else:
                logger.debug(
                    f"Skipping chunk due to budget",
                    extra={
                        "index": idx,
                        "score": score,
                        "tokens": tokens,
                        "remaining_budget": budget - total_tokens,
                    }
                )
        
        # Sort selected indices to preserve original order
        selected_indices.sort()
        
        logger.info(
            f"Budget truncation complete",
            extra={
                "original_count": len(texts),
                "selected_count": len(selected_indices),
                "total_tokens": total_tokens,
                "budget": budget,
                "utilization": round(total_tokens / budget * 100, 2) if budget > 0 else 0,
            }
        )
        
        return selected_indices
