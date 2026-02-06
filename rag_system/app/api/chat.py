"""Chat API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse, ChatErrorResponse
from app.services.orchestration import ChatService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with documents",
    description="Process a user query through the RAG pipeline and return an answer with citations",
    responses={
        200: {
            "description": "Successful response with answer and citations",
            "model": ChatResponse,
        },
        400: {
            "description": "Invalid request",
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
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Process a chat request through the RAG pipeline.
    
    This endpoint orchestrates the complete RAG workflow:
    1. Retrieve relevant chunks using hybrid search (vector + BM25)
    2. Optimize context and build prompt
    3. Generate answer using Gemini LLM
    4. Extract and validate citations
    5. Return structured response with confidence score
    
    Args:
        request: Chat request with query and user_id
        db: Database session
        
    Returns:
        ChatResponse: Answer with citations, confidence, and sources
        
    Raises:
        HTTPException: If request processing fails
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
        
        # Process request through RAG pipeline
        response = await chat_service.process_chat(
            request=request,
            db=db,
        )
        
        # Log response summary
        logger.info(
            f"Chat request successful",
            extra={
                "user_id": request.user_id,
                "answer_length": len(response.answer),
                "citations": len(response.citations),
                "confidence_score": round(response.confidence_score, 3),
                "latency_ms": round(response.latency_ms, 2),
                "warnings": len(response.warnings),
            }
        )
        
        return response
        
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
