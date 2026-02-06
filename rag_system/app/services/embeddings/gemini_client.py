"""Gemini embedding client for generating text embeddings."""
import time
from typing import List, Dict, Any
from enum import Enum
import google.generativeai as genai
from google.api_core import retry, exceptions

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TaskType(str, Enum):
    """Gemini embedding task types."""
    
    RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
    RETRIEVAL_QUERY = "RETRIEVAL_QUERY"


class GeminiEmbeddingClient:
    """Client for generating embeddings using Google Gemini API."""
    
    def __init__(
        self,
        api_key: str = None,
        model_name: str = None,
        timeout: int = None,
        max_retries: int = None,
    ):
        """
        Initialize Gemini embedding client.
        
        Args:
            api_key: Gemini API key (defaults to settings)
            model_name: Model name (defaults to settings)
            timeout: Request timeout in seconds (defaults to settings)
            max_retries: Maximum retry attempts (defaults to settings)
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self.timeout = timeout or settings.GEMINI_TIMEOUT
        self.max_retries = max_retries or settings.GEMINI_MAX_RETRIES
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        logger.info(
            f"GeminiEmbeddingClient initialized",
            extra={
                "model": self.model_name,
                "timeout": self.timeout,
                "max_retries": self.max_retries,
            }
        )
    
    @retry.Retry(
        predicate=retry.if_exception_type(
            exceptions.ServiceUnavailable,
            exceptions.DeadlineExceeded,
            exceptions.ResourceExhausted,
        ),
        initial=1.0,
        maximum=60.0,
        multiplier=2.0,
        deadline=300.0,
    )
    def embed_texts(
        self,
        texts: List[str],
        task_type: str = TaskType.RETRIEVAL_DOCUMENT,
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.
        
        Features:
        - Batch processing
        - Exponential backoff retry
        - Timeout handling
        - Latency tracking
        - Error logging
        
        Args:
            texts: List of text strings to embed
            task_type: Task type for embedding (RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY)
            
        Returns:
            List[List[float]]: List of embedding vectors
            
        Raises:
            Exception: If embedding generation fails after retries
        """
        if not texts:
            logger.warning("Empty text list provided for embedding")
            return []
        
        start_time = time.time()
        
        try:
            logger.info(
                f"Generating embeddings",
                extra={
                    "batch_size": len(texts),
                    "task_type": task_type,
                    "model": self.model_name,
                }
            )
            
            # Generate embeddings
            embeddings = []
            
            for text in texts:
                # Call Gemini API
                result = genai.embed_content(
                    model=self.model_name,
                    content=text,
                    task_type=task_type,
                )
                
                # Extract embedding vector
                embedding = result['embedding']
                embeddings.append(embedding)
            
            # Calculate latency
            latency = time.time() - start_time
            
            logger.info(
                f"Embeddings generated successfully",
                extra={
                    "batch_size": len(texts),
                    "embeddings_count": len(embeddings),
                    "latency_seconds": round(latency, 3),
                    "avg_latency_per_text": round(latency / len(texts), 3) if texts else 0,
                }
            )
            
            return embeddings
            
        except exceptions.InvalidArgument as e:
            logger.error(
                f"Invalid argument for Gemini API: {str(e)}",
                extra={"batch_size": len(texts), "task_type": task_type},
                exc_info=True,
            )
            raise Exception(f"Invalid argument for embedding: {str(e)}")
            
        except exceptions.ResourceExhausted as e:
            logger.error(
                f"Gemini API quota exhausted: {str(e)}",
                extra={"batch_size": len(texts)},
                exc_info=True,
            )
            raise Exception(f"API quota exhausted: {str(e)}")
            
        except exceptions.DeadlineExceeded as e:
            logger.error(
                f"Gemini API timeout: {str(e)}",
                extra={
                    "batch_size": len(texts),
                    "timeout": self.timeout,
                },
                exc_info=True,
            )
            raise Exception(f"API timeout: {str(e)}")
            
        except Exception as e:
            latency = time.time() - start_time
            logger.error(
                f"Failed to generate embeddings: {str(e)}",
                extra={
                    "batch_size": len(texts),
                    "latency_seconds": round(latency, 3),
                    "task_type": task_type,
                },
                exc_info=True,
            )
            raise Exception(f"Embedding generation failed: {str(e)}")
    
    def embed_single(
        self,
        text: str,
        task_type: str = TaskType.RETRIEVAL_DOCUMENT,
    ) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text string to embed
            task_type: Task type for embedding
            
        Returns:
            List[float]: Embedding vector
        """
        embeddings = self.embed_texts([text], task_type)
        return embeddings[0] if embeddings else []
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this model.
        
        Returns:
            int: Embedding dimension
        """
        # Gemini embedding-001 produces 768-dimensional embeddings
        return 768
