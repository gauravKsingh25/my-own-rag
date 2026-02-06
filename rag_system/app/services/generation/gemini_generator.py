"""Gemini LLM answer generation service."""
import time
from typing import Optional, Dict, Any
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from app.services.generation.response_models import (
    GenerationRequest,
    AnswerResponse,
    TokenUsage,
)
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def retry_with_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
):
    """
    Decorator for exponential backoff retry.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay on each retry
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (
                    google_exceptions.ResourceExhausted,
                    google_exceptions.ServiceUnavailable,
                    google_exceptions.DeadlineExceeded,
                ) as e:
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Retry attempt {attempt + 1}/{max_retries} after {delay}s",
                            extra={
                                "error": str(e),
                                "attempt": attempt + 1,
                                "delay": delay,
                            }
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"All retry attempts exhausted",
                            extra={
                                "max_retries": max_retries,
                                "error": str(e),
                            },
                            exc_info=True,
                        )
                        raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


class GeminiGenerator:
    """
    Gemini LLM answer generation service.
    
    Features:
    - Non-streaming and streaming generation
    - Exponential backoff retry (1s, 2s, 4s)
    - Timeout handling
    - Token usage tracking
    - Latency measurement
    - Structured logging
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        timeout: int = 60,
    ):
        """
        Initialize Gemini generator.
        
        Args:
            model_name: Model name (default from config)
            temperature: Sampling temperature (default from config)
            max_output_tokens: Max tokens for generation (default from config)
            timeout: Request timeout in seconds
        """
        self.model_name = model_name or settings.GENERATION_MODEL
        self.temperature = temperature if temperature is not None else settings.TEMPERATURE
        self.max_output_tokens = max_output_tokens or settings.MAX_OUTPUT_TOKENS
        self.timeout = timeout
        
        # Configure Gemini API
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Initialize model
        self.model = genai.GenerativeModel(self.model_name)
        
        logger.info(
            f"GeminiGenerator initialized",
            extra={
                "model": self.model_name,
                "temperature": self.temperature,
                "max_output_tokens": self.max_output_tokens,
                "timeout": timeout,
            }
        )
    
    @retry_with_exponential_backoff(
        max_retries=3,
        initial_delay=1.0,
        backoff_factor=2.0,
    )
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        stream: bool = False,
    ) -> AnswerResponse:
        """
        Generate answer using Gemini LLM.
        
        Args:
            system_prompt: System instructions
            user_prompt: User prompt with context and query
            stream: Enable streaming (not implemented yet)
            
        Returns:
            AnswerResponse: Generated answer with metadata
        """
        if stream:
            raise NotImplementedError("Streaming generation not yet implemented")
        
        logger.info(
            f"Starting answer generation",
            extra={
                "model": self.model_name,
                "system_prompt_length": len(system_prompt),
                "user_prompt_length": len(user_prompt),
            }
        )
        
        start_time = time.time()
        
        try:
            # Combine system prompt and user prompt
            # Gemini doesn't have separate system role, so we prepend it
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
            )
            
            # Generate response
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config,
                request_options={'timeout': self.timeout},
            )
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract answer text
            answer = response.text if response.text else ""
            
            # Extract token usage
            token_usage = None
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                token_usage = TokenUsage(
                    prompt_tokens=getattr(usage, 'prompt_token_count', 0),
                    completion_tokens=getattr(usage, 'candidates_token_count', 0),
                    total_tokens=getattr(usage, 'total_token_count', 0),
                )
            
            logger.info(
                f"Answer generation complete",
                extra={
                    "latency_ms": round(latency_ms, 2),
                    "answer_length": len(answer),
                    "token_usage": token_usage.to_dict() if token_usage else None,
                }
            )
            
            # Create response object
            answer_response = AnswerResponse(
                answer=answer,
                token_usage=token_usage,
                latency_ms=latency_ms,
                model=self.model_name,
            )
            
            return answer_response
            
        except google_exceptions.InvalidArgument as e:
            logger.error(
                f"Invalid argument error: {str(e)}",
                exc_info=True,
            )
            raise ValueError(f"Invalid generation request: {str(e)}")
        
        except google_exceptions.PermissionDenied as e:
            logger.error(
                f"Permission denied: {str(e)}",
                exc_info=True,
            )
            raise PermissionError(f"API key invalid or insufficient permissions: {str(e)}")
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            
            logger.error(
                f"Answer generation failed: {str(e)}",
                extra={
                    "latency_ms": round(latency_ms, 2),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise
    
    def generate_from_request(
        self,
        request: GenerationRequest,
    ) -> AnswerResponse:
        """
        Generate answer from GenerationRequest object.
        
        Args:
            request: Generation request
            
        Returns:
            AnswerResponse: Generated answer
        """
        # Override instance settings if provided in request
        original_temp = self.temperature
        original_max_tokens = self.max_output_tokens
        original_timeout = self.timeout
        
        if request.temperature is not None:
            self.temperature = request.temperature
        if request.max_output_tokens is not None:
            self.max_output_tokens = request.max_output_tokens
        if request.timeout is not None:
            self.timeout = request.timeout
        
        try:
            response = self.generate(
                system_prompt=request.system_prompt,
                user_prompt=request.user_prompt,
                stream=request.stream,
            )
            return response
        finally:
            # Restore original settings
            self.temperature = original_temp
            self.max_output_tokens = original_max_tokens
            self.timeout = original_timeout
