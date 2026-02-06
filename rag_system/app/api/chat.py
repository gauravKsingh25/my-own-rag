"""Chat API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.database import get_db
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatErrorResponse,
    FeedbackRequest,
    FeedbackResponse,
)
from app.services.orchestration import ChatService
from app.services.monitoring import FeedbackService
from app.services.protection import (
    RateLimitExceededError,
    QuotaExceededError,
    CircuitBreakerOpenError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with documents (with protection layer)",
    description="Process a user query through the RAG pipeline with rate limiting, quota management, and circuit breaker protection",
    responses={
        200: {
            "description": "Successful response with answer and citations",
            "model": ChatResponse,
        },
        400: {
            "description": "Invalid request",
            "model": ChatErrorResponse,
        },
        429: {
            "description": "Rate limit or quota exceeded",
            "model": ChatErrorResponse,
        },
        503: {
            "description": "Service unavailable (circuit breaker open)",
            "model": ChatErrorResponse,
        },
        500: {
            "description": "Internal server error",
            "model": ChatErrorResponse,
        },
    },
)
async def chat(
    request: ChatRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Process a chat request through the RAG pipeline with protection layer.
    
    This endpoint orchestrates the complete RAG workflow with:
    - Rate limiting (10 req/min per user)
    - Daily quota enforcement
    - Circuit breaker for Gemini failures
    - Load shedding under high system load
    
    Then executes:
    1. Retrieve relevant chunks using hybrid search (vector + BM25)
    2. Optimize context and build prompt
    3. Generate answer using Gemini LLM
    4. Extract and validate citations
    5. Return structured response with confidence score
    
    Args:
        request: Chat request with query and user_id
        response: FastAPI response object (for headers)
        db: Database session
        
    Returns:
        ChatResponse: Answer with citations, confidence, and sources
        
    Raises:
        HTTPException: 
            - 429: Rate limit or quota exceeded
            - 503: Circuit breaker open (service unavailable)
            - 400: Invalid request
            - 500: Internal error
    """
    logger.info(
        f"Chat request received",
        extra={
            "user_id": request.user_id,
            "query_length": len(request.query),
            "document_id": request.document_id,
            "top_k": request.top_k,
        }
    )
    
    try:
        # Initialize chat service
        chat_service = ChatService()
        
        # Process request through RAG pipeline with protection
        chat_response = await chat_service.process_chat(
            request=request,
            db=db,
        )
        
        # Log response summary
        logger.info(
            f"Chat request successful",
            extra={
                "user_id": request.user_id,
                "interaction_id": chat_response.interaction_id,
                "answer_length": len(chat_response.answer),
                "citations": len(chat_response.citations),
                "confidence_score": round(chat_response.confidence_score, 3),
                "latency_ms": round(chat_response.latency_ms, 2),
                "warnings": len(chat_response.warnings),
            }
        )
        
        return chat_response
    
    except RateLimitExceededError as e:
        # Rate limit exceeded - return 429 with Retry-After header
        logger.warning(
            f"Rate limit exceeded: {str(e)}",
            extra={
                "user_id": request.user_id,
                "retry_after": e.retry_after,
            },
        )
        
        # Set Retry-After header
        response.headers["Retry-After"] = str(e.retry_after)
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": str(e),
                "error_type": "RateLimitExceeded",
                "retry_after": e.retry_after,
                "details": {
                    "user_id": request.user_id,
                    "message": "You have exceeded the rate limit. Please wait before trying again.",
                },
            },
        )
    
    except QuotaExceededError as e:
        # Daily quota exceeded - return 429
        logger.warning(
            f"Quota exceeded: {str(e)}",
            extra={
                "user_id": request.user_id,
                "reset_time": e.reset_time,
            },
        )
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": str(e),
                "error_type": "QuotaExceeded",
                "reset_time": e.reset_time,
                "details": {
                    "user_id": request.user_id,
                    "message": "You have exceeded your daily quota. Please try again after reset time.",
                },
            },
        )
    
    except CircuitBreakerOpenError as e:
        # Circuit breaker open - service unavailable
        logger.error(
            f"Circuit breaker open: {str(e)}",
            extra={
                "user_id": request.user_id,
            },
        )
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "The AI service is temporarily unavailable. Please try again later.",
                "error_type": "ServiceUnavailable",
                "details": {
                    "message": "Our AI service is experiencing issues. We're working to restore it.",
                },
            },
        )
        
    except ValueError as e:
        # Invalid input or generation error
        logger.error(
            f"Invalid request: {str(e)}",
            extra={
                "user_id": request.user_id,
                "error_type": "ValueError",
            },
            exc_info=True,
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": str(e),
                "error_type": "InvalidRequest",
                "details": {
                    "user_id": request.user_id,
                    "query_length": len(request.query),
                },
            },
        )
    
    except PermissionError as e:
        # API key or permission issues
        logger.error(
            f"Permission error: {str(e)}",
            extra={
                "user_id": request.user_id,
                "error_type": "PermissionError",
            },
            exc_info=True,
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Service configuration error. Please contact support.",
                "error_type": "ServiceError",
                "details": None,
            },
        )
    
    except Exception as e:
        # Unexpected errors
        logger.error(
            f"Chat request failed: {str(e)}",
            extra={
                "user_id": request.user_id,
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "An unexpected error occurred while processing your request",
                "error_type": "InternalServerError",
                "details": {
                    "user_id": request.user_id,
                },
            },
        )


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback for a chat interaction",
    description="Submit user feedback (rating and optional comment) for a chat interaction",
    responses={
        201: {
            "description": "Feedback successfully recorded",
            "model": FeedbackResponse,
        },
        400: {
            "description": "Invalid request (e.g., invalid interaction_id or rating)",
            "model": ChatErrorResponse,
        },
        404: {
            "description": "Interaction not found",
            "model": ChatErrorResponse,
        },
        500: {
            "description": "Internal server error",
            "model": ChatErrorResponse,
        },
    },
)
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """
    Submit feedback for a chat interaction.
    
    Allows users to rate the quality of an answer and provide optional comments.
    Ratings are on a scale of 1 (poor) to 5 (excellent).
    
    Args:
        request: Feedback request with interaction_id, rating, and optional comment
        db: Database session
        
    Returns:
        FeedbackResponse: Confirmation of feedback submission
        
    Raises:
        HTTPException: If feedback submission fails
    """
    logger.info(
        f"Feedback request received",
        extra={
            "interaction_id": request.interaction_id,
            "rating": request.rating,
            "has_comment": request.comment is not None,
        }
    )
    
    try:
        # Parse interaction_id
        try:
            interaction_id = UUID(request.interaction_id)
        except ValueError:
            logger.error(
                f"Invalid interaction_id format: {request.interaction_id}",
                extra={"interaction_id": request.interaction_id}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid interaction_id format",
                    "error_type": "InvalidRequest",
                    "details": {"interaction_id": request.interaction_id},
                },
            )
        
        # Initialize feedback service
        feedback_service = FeedbackService()
        
        # Submit feedback
        feedback = await feedback_service.submit_feedback(
            db=db,
            interaction_id=interaction_id,
            rating=request.rating,
            comment=request.comment,
        )
        
        if not feedback:
            # Interaction not found or other error
            logger.error(
                f"Failed to submit feedback for interaction {interaction_id}",
                extra={
                    "interaction_id": str(interaction_id),
                    "rating": request.rating,
                }
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Interaction not found or feedback submission failed",
                    "error_type": "NotFoundError",
                    "details": {"interaction_id": str(interaction_id)},
                },
            )
        
        logger.info(
            f"Feedback submitted successfully",
            extra={
                "feedback_id": str(feedback.id),
                "interaction_id": str(interaction_id),
                "rating": request.rating,
            }
        )
        
        return FeedbackResponse(
            success=True,
            message="Feedback recorded successfully",
            feedback_id=str(feedback.id),
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        # Unexpected errors
        logger.error(
            f"Feedback submission failed: {str(e)}",
            extra={
                "interaction_id": request.interaction_id,
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "An unexpected error occurred while submitting feedback",
                "error_type": "InternalServerError",
                "details": None,
            },
        )
