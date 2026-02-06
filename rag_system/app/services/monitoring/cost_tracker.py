"""
Cost tracking service for monitoring LLM API costs.

This module provides cost calculation and tracking for various LLM models.
"""

import logging
from typing import Dict, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class ModelPricing:
    """Model pricing configuration for different LLM providers."""
    
    # Gemini 1.5 Pro pricing (per 1M tokens)
    # https://ai.google.dev/pricing
    GEMINI_15_PRO_INPUT = Decimal("0.000125")  # $0.125 per 1M input tokens
    GEMINI_15_PRO_OUTPUT = Decimal("0.000375")  # $0.375 per 1M output tokens
    
    # Gemini 1.5 Flash pricing (per 1M tokens)
    GEMINI_15_FLASH_INPUT = Decimal("0.000075")  # $0.075 per 1M input tokens
    GEMINI_15_FLASH_OUTPUT = Decimal("0.00030")  # $0.30 per 1M output tokens
    
    # Embedding models (per 1M tokens)
    EMBEDDING_001_INPUT = Decimal("0.00001")  # $0.01 per 1M tokens
    
    @classmethod
    def get_model_pricing(cls, model_name: str) -> tuple[Decimal, Decimal]:
        """
        Get input and output pricing for a model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Tuple of (input_price_per_million, output_price_per_million)
        """
        model_lower = model_name.lower()
        
        if "gemini-1.5-pro" in model_lower or "gemini-pro" in model_lower:
            return cls.GEMINI_15_PRO_INPUT, cls.GEMINI_15_PRO_OUTPUT
        elif "gemini-1.5-flash" in model_lower or "gemini-flash" in model_lower:
            return cls.GEMINI_15_FLASH_INPUT, cls.GEMINI_15_FLASH_OUTPUT
        elif "embedding" in model_lower:
            return cls.EMBEDDING_001_INPUT, Decimal("0")
        else:
            logger.warning(f"Unknown model '{model_name}', using default pricing")
            return cls.GEMINI_15_PRO_INPUT, cls.GEMINI_15_PRO_OUTPUT


class CostTracker:
    """Service for tracking and calculating LLM API costs."""
    
    def __init__(self):
        """Initialize cost tracker."""
        self.model_pricing = ModelPricing()
    
    def calculate_cost(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """
        Calculate cost for a generation request.
        
        Args:
            model_name: Name of the model used
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        try:
            input_price, output_price = self.model_pricing.get_model_pricing(model_name)
            
            # Calculate cost (prices are per 1M tokens)
            input_cost = (Decimal(prompt_tokens) / Decimal("1000000")) * input_price
            output_cost = (Decimal(completion_tokens) / Decimal("1000000")) * output_price
            
            total_cost = float(input_cost + output_cost)
            
            logger.debug(
                "Cost calculated",
                extra={
                    "model": model_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "input_cost": float(input_cost),
                    "output_cost": float(output_cost),
                    "total_cost": total_cost,
                },
            )
            
            return total_cost
            
        except Exception as e:
            logger.error(f"Error calculating cost: {str(e)}", exc_info=True)
            return 0.0
    
    def calculate_embedding_cost(
        self,
        model_name: str,
        token_count: int,
    ) -> float:
        """
        Calculate cost for embedding generation.
        
        Args:
            model_name: Name of the embedding model
            token_count: Number of tokens embedded
            
        Returns:
            Estimated cost in USD
        """
        try:
            input_price, _ = self.model_pricing.get_model_pricing(model_name)
            
            # Calculate cost (price is per 1M tokens)
            cost = float((Decimal(token_count) / Decimal("1000000")) * input_price)
            
            logger.debug(
                "Embedding cost calculated",
                extra={
                    "model": model_name,
                    "token_count": token_count,
                    "cost": cost,
                },
            )
            
            return cost
            
        except Exception as e:
            logger.error(f"Error calculating embedding cost: {str(e)}", exc_info=True)
            return 0.0
    
    def estimate_monthly_cost(
        self,
        daily_requests: int,
        avg_prompt_tokens: int,
        avg_completion_tokens: int,
        model_name: str,
    ) -> Dict[str, float]:
        """
        Estimate monthly costs based on usage patterns.
        
        Args:
            daily_requests: Average daily request count
            avg_prompt_tokens: Average prompt tokens per request
            avg_completion_tokens: Average completion tokens per request
            model_name: Model being used
            
        Returns:
            Dictionary with cost estimates
        """
        try:
            # Calculate cost per request
            cost_per_request = self.calculate_cost(
                model_name=model_name,
                prompt_tokens=avg_prompt_tokens,
                completion_tokens=avg_completion_tokens,
            )
            
            # Calculate monthly estimates
            daily_cost = cost_per_request * daily_requests
            monthly_cost = daily_cost * 30
            annual_cost = daily_cost * 365
            
            estimates = {
                "cost_per_request": cost_per_request,
                "daily_cost": daily_cost,
                "monthly_cost": monthly_cost,
                "annual_cost": annual_cost,
                "daily_requests": daily_requests,
                "model_name": model_name,
            }
            
            logger.info(
                "Monthly cost estimate calculated",
                extra=estimates,
            )
            
            return estimates
            
        except Exception as e:
            logger.error(f"Error estimating monthly cost: {str(e)}", exc_info=True)
            return {}
    
    def format_cost(self, cost: float) -> str:
        """
        Format cost as currency string.
        
        Args:
            cost: Cost in USD
            
        Returns:
            Formatted cost string (e.g., "$0.0012")
        """
        if cost < 0.01:
            return f"${cost:.6f}"
        elif cost < 1.0:
            return f"${cost:.4f}"
        else:
            return f"${cost:.2f}"
