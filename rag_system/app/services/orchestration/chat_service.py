"""Chat orchestration service."""
import time
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.retrieval import HybridRetriever, RetrievalResult
from app.services.generation import (
    PromptBuilder,
    GeminiGenerator,
    AnswerValidator,
    AnswerResponse,
)
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SourceInfo,
    TokenUsageInfo,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class ChatService:
    """
    Orchestrate the complete RAG pipeline for chat.
    
    Pipeline:
    1. Hybrid retrieval (vector + BM25)
    2. Context optimization and prompt building
    3. LLM answer generation
    4. Citation extraction and validation
    5. Response formatting
    """
    
    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        generator: Optional[GeminiGenerator] = None,
        validator: Optional[AnswerValidator] = None,
    ):
        """
        Initialize chat service.
        
        Args:
            retriever: Hybrid retriever instance
            prompt_builder: Prompt builder instance
            generator: Gemini generator instance
            validator: Answer validator instance
        """
        self.retriever = retriever or HybridRetriever()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.generator = generator or GeminiGenerator()
        self.validator = validator or AnswerValidator()
        
        logger.info("ChatService initialized")
    
    async def process_chat(
        self,
        request: ChatRequest,
        db: AsyncSession,
    ) -> ChatResponse:
        """
        Process chat request through full RAG pipeline.
        
        Args:
            request: Chat request
            db: Database session
            
        Returns:
            ChatResponse: Structured chat response
        """
        start_time = time.time()
        
        logger.info(
            f"Processing chat request",
            extra={
                "query_preview": request.query[:100],
                "user_id": request.user_id,
                "document_id": request.document_id,
                "top_k": request.top_k,
            }
        )
        
        # Parse document_id if provided
        document_id = None
        if request.document_id:
            try:
                document_id = UUID(request.document_id)
            except ValueError:
                logger.warning(
                    f"Invalid document_id format: {request.document_id}",
                    extra={"user_id": request.user_id}
                )
        
        # Step 1: Retrieve relevant chunks
        retrieval_start = time.time()
        
        retrieval_results = await self.retriever.retrieve(
            query=request.query,
            user_id=request.user_id,
            db=db,
            top_k=request.top_k,
            document_id=document_id,
        )
        
        retrieval_latency = (time.time() - retrieval_start) * 1000
        
        logger.info(
            f"Retrieval complete",
            extra={
                "results_count": len(retrieval_results),
                "latency_ms": round(retrieval_latency, 2),
            }
        )
        
        # Handle empty retrieval results
        if not retrieval_results:
            logger.warning(
                f"No retrieval results found",
                extra={
                    "query": request.query,
                    "user_id": request.user_id,
                    "document_id": request.document_id,
                }
            )
            
            return self._create_empty_response(
                request=request,
                latency_ms=(time.time() - start_time) * 1000,
            )
        
        # Step 2: Build prompt with context optimization
        prompt_start = time.time()
        
        prompt_components = self.prompt_builder.build_prompt(
            query=request.query,
            retrieval_results=retrieval_results,
            optimize_context=True,
        )
        
        prompt_latency = (time.time() - prompt_start) * 1000
        
        logger.info(
            f"Prompt building complete",
            extra={
                "source_count": prompt_components.source_count,
                "context_tokens": prompt_components.context_tokens,
                "latency_ms": round(prompt_latency, 2),
            }
        )
        
        # Step 3: Generate answer
        generation_start = time.time()
        
        try:
            answer_response = self.generator.generate(
                system_prompt=prompt_components.system_prompt,
                user_prompt=prompt_components.user_prompt,
            )
        except Exception as e:
            logger.error(
                f"Answer generation failed: {str(e)}",
                extra={
                    "user_id": request.user_id,
                    "query": request.query,
                },
                exc_info=True,
            )
            raise
        
        generation_latency = answer_response.latency_ms
        
        logger.info(
            f"Answer generation complete",
            extra={
                "answer_length": len(answer_response.answer),
                "latency_ms": round(generation_latency, 2),
            }
        )
        
        # Step 4: Validate answer and extract citations
        validation_start = time.time()
        
        validated_response = self.validator.validate_answer(
            answer_response=answer_response,
            source_mapping=prompt_components.source_mapping,
        )
        
        validation_latency = (time.time() - validation_start) * 1000
        
        logger.info(
            f"Answer validation complete",
            extra={
                "citations": len(validated_response.citations),
                "confidence_score": round(validated_response.confidence_score, 3),
                "has_hallucinations": validated_response.has_hallucinations,
                "latency_ms": round(validation_latency, 2),
            }
        )
        
        # Step 5: Format response
        total_latency = (time.time() - start_time) * 1000
        
        chat_response = self._format_response(
            validated_response=validated_response,
            retrieval_results=retrieval_results,
            source_mapping=prompt_components.source_mapping,
            latency_ms=total_latency,
        )
        
        logger.info(
            f"Chat request complete",
            extra={
                "total_latency_ms": round(total_latency, 2),
                "retrieval_ms": round(retrieval_latency, 2),
                "prompt_ms": round(prompt_latency, 2),
                "generation_ms": round(generation_latency, 2),
                "validation_ms": round(validation_latency, 2),
                "confidence_score": chat_response.confidence_score,
                "citations": len(chat_response.citations),
            }
        )
        
        return chat_response
    
    def _format_response(
        self,
        validated_response: AnswerResponse,
        retrieval_results: List[RetrievalResult],
        source_mapping: dict,
        latency_ms: float,
    ) -> ChatResponse:
        """
        Format validated answer into ChatResponse.
        
        Args:
            validated_response: Validated answer response
            retrieval_results: Retrieval results
            source_mapping: Source number to metadata mapping
            latency_ms: Total latency
            
        Returns:
            ChatResponse: Formatted response
        """
        # Build source information list
        sources = []
        
        for source_num, metadata in source_mapping.items():
            source_info = SourceInfo(
                source_number=source_num,
                chunk_id=metadata.get("chunk_id", ""),
                document_id=metadata.get("document_id", ""),
                section_title=metadata.get("section_title"),
                page_number=metadata.get("page_number"),
                score=metadata.get("score", 0.0),
            )
            sources.append(source_info)
        
        # Sort sources by source number
        sources.sort(key=lambda x: x.source_number)
        
        # Build token usage info
        token_usage = None
        if validated_response.token_usage:
            token_usage = TokenUsageInfo(
                prompt_tokens=validated_response.token_usage.prompt_tokens,
                completion_tokens=validated_response.token_usage.completion_tokens,
                total_tokens=validated_response.token_usage.total_tokens,
            )
        
        # Create response
        response = ChatResponse(
            answer=validated_response.answer,
            citations=validated_response.citations,
            confidence_score=validated_response.confidence_score,
            sources=sources,
            token_usage=token_usage,
            latency_ms=latency_ms,
            warnings=validated_response.warnings,
        )
        
        return response
    
    def _create_empty_response(
        self,
        request: ChatRequest,
        latency_ms: float,
    ) -> ChatResponse:
        """
        Create response for empty retrieval results.
        
        Args:
            request: Original request
            latency_ms: Latency so far
            
        Returns:
            ChatResponse: Response indicating no results
        """
        answer = (
            "I don't have any relevant documents to answer this question. "
            "This could mean:\n"
            "1. No documents have been uploaded for your account\n"
            "2. Your query doesn't match any indexed content\n"
            "3. The specified document doesn't exist\n\n"
            "Please try uploading documents first or rephrasing your question."
        )
        
        response = ChatResponse(
            answer=answer,
            citations=[],
            confidence_score=0.0,
            sources=[],
            token_usage=None,
            latency_ms=latency_ms,
            warnings=[
                "No relevant documents found for query",
                "Unable to provide a factual answer",
            ],
        )
        
        return response
