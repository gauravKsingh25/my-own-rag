"""Chat API schemas."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""
    
    query: str = Field(
        ...,
        description="User query",
        min_length=1,
        max_length=10000,
    )
    user_id: str = Field(
        ...,
        description="User ID for filtering documents",
        min_length=1,
        max_length=255,
    )
    document_id: Optional[str] = Field(
        None,
        description="Optional document ID to restrict search scope",
    )
    top_k: int = Field(
        5,
        description="Number of top results to retrieve",
        ge=1,
        le=20,
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the key benefits of machine learning?",
                "user_id": "user_123",
                "document_id": None,
                "top_k": 5,
            }
        }


class SourceInfo(BaseModel):
    """Source information for citation."""
    
    source_number: int = Field(..., description="Source number in answer")
    chunk_id: str = Field(..., description="Chunk UUID")
    document_id: str = Field(..., description="Document UUID")
    section_title: Optional[str] = Field(None, description="Section title")
    page_number: Optional[int] = Field(None, description="Page number")
    score: float = Field(..., description="Relevance score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "source_number": 1,
                "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
                "document_id": "123e4567-e89b-12d3-a456-426614174001",
                "section_title": "Introduction",
                "page_number": 3,
                "score": 0.92,
            }
        }


class TokenUsageInfo(BaseModel):
    """Token usage information."""
    
    prompt_tokens: int = Field(..., description="Tokens in prompt")
    completion_tokens: int = Field(..., description="Tokens in completion")
    total_tokens: int = Field(..., description="Total tokens used")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt_tokens": 8234,
                "completion_tokens": 312,
                "total_tokens": 8546,
            }
        }


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""
    
    interaction_id: Optional[str] = Field(
        None,
        description="Unique interaction ID for feedback",
    )
    answer: str = Field(..., description="Generated answer")
    citations: List[int] = Field(
        default_factory=list,
        description="List of cited source numbers",
    )
    confidence_score: float = Field(
        ...,
        description="Answer confidence score (0-1)",
        ge=0.0,
        le=1.0,
    )
    sources: List[SourceInfo] = Field(
        default_factory=list,
        description="Source information for citations",
    )
    token_usage: Optional[TokenUsageInfo] = Field(
        None,
        description="Token usage statistics",
    )
    latency_ms: float = Field(..., description="Total request latency in ms")
    warnings: List[str] = Field(
        default_factory=list,
        description="Warning messages",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "interaction_id": "123e4567-e89b-12d3-a456-426614174000",
                "answer": "Machine learning offers several key benefits. First, it excels at automatic feature extraction [Source 1]. Second, it handles large-scale data efficiently [Source 2, 3].",
                "citations": [1, 2, 3],
                "confidence_score": 0.92,
                "sources": [
                    {
                        "source_number": 1,
                        "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
                        "document_id": "123e4567-e89b-12d3-a456-426614174001",
                        "section_title": "Benefits of ML",
                        "page_number": 5,
                        "score": 0.95,
                    }
                ],
                "token_usage": {
                    "prompt_tokens": 8234,
                    "completion_tokens": 312,
                    "total_tokens": 8546,
                },
                "latency_ms": 3542.5,
                "warnings": [],
            }
        }


class ChatErrorResponse(BaseModel):
    """Error response schema."""
    
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Error type")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "No relevant documents found for query",
                "error_type": "NotFoundError",
                "details": {"user_id": "user_123", "query_length": 45},
            }
        }

    """Request schema for feedback endpoint."""
    
    interaction_id: str = Field(
        ...,
        description="Interaction ID from chat response",
    )
    rating: int = Field(
        ...,
        description="Rating from 1 (poor) to 5 (excellent)",
        ge=1,
        le=5,
    )
    comment: Optional[str] = Field(
        None,
        description="Optional feedback comment",
        max_length=2000,
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "interaction_id": "123e4567-e89b-12d3-a456-426614174000",
                "rating": 5,
                "comment": "Great answer with accurate citations!",
            }
        }


class FeedbackResponse(BaseModel):
    """Response schema for feedback endpoint."""
    
    success: bool = Field(..., description="Whether feedback was recorded")
    message: str = Field(..., description="Status message")
    feedback_id: Optional[str] = Field(None, description="Feedback UUID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Feedback recorded successfully",
                "feedback_id": "123e4567-e89b-12d3-a456-426614174002",
            }
        }
