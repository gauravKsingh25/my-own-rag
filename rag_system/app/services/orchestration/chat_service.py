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
from app.services.monitoring import CostTracker
from app.services.protection import (
    RateLimiter,
    QuotaManager,
    CircuitBreakerManager,
    CircuitBreakerConfig,
    LoadShedder,
    RateLimitExceededError,
    QuotaExceededError,
    CircuitBreakerOpenError,
)
from app.db.models import ChatInteraction
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SourceInfo,
    TokenUsageInfo,
)
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ChatService:
    """
    Orchestrate the complete RAG pipeline for chat with protection layer.
    
    Pipeline:
    0. Protection checks (rate limit, quota, load shedding)
    1. Hybrid retrieval (vector + BM25)
    2. Context optimization and prompt building
    3. LLM answer generation (with circuit breaker)
    4. Citation extraction and validation
    5. Response formatting
    """
    
    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        generator: Optional[GeminiGenerator] = None,
        validator: Optional[AnswerValidator] = None,
        cost_tracker: Optional[CostTracker] = None,
        rate_limiter: Optional[RateLimiter] = None,
        quota_manager: Optional[QuotaManager] = None,
        circuit_breaker_manager: Optional[CircuitBreakerManager] = None,
        load_shedder: Optional[LoadShedder] = None,
    ):
        """
        Initialize chat service.
        
        Args:
            retriever: Hybrid retriever instance
            prompt_builder: Prompt builder instance
            generator: Gemini generator instance
            validator: Answer validator instance
            cost_tracker: Cost tracker instance
            rate_limiter: Rate limiter instance
            quota_manager: Quota manager instance
            circuit_breaker_manager: Circuit breaker manager instance
            load_shedder: Load shedder instance
        """
        self.retriever = retriever or HybridRetriever()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.generator = generator or GeminiGenerator()
        self.validator = validator or AnswerValidator()
        self.cost_tracker = cost_tracker or CostTracker()
        
        # Protection layer
        self.rate_limiter = rate_limiter or RateLimiter(
            rate=settings.RATE_LIMIT_PER_MINUTE,
            window=settings.RATE_LIMIT_WINDOW,
        )
        self.quota_manager = quota_manager or QuotaManager(
            daily_token_limit=settings.DAILY_TOKEN_LIMIT,
            daily_cost_limit=settings.DAILY_COST_LIMIT,
        )
        self.circuit_breaker_manager = circuit_breaker_manager or CircuitBreakerManager()
        self.load_shedder = load_shedder or LoadShedder(
            cpu_threshold_elevated=settings.CPU_THRESHOLD_ELEVATED,
            cpu_threshold_high=settings.CPU_THRESHOLD_HIGH,
            cpu_threshold_critical=settings.CPU_THRESHOLD_CRITICAL,
            memory_threshold_elevated=settings.MEMORY_THRESHOLD_ELEVATED,
            memory_threshold_high=settings.MEMORY_THRESHOLD_HIGH,
            memory_threshold_critical=settings.MEMORY_THRESHOLD_CRITICAL,
        )
        
        logger.info(
            "ChatService initialized with protection layer",
            extra={
                "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
                "quota_enabled": settings.QUOTA_ENABLED,
                "circuit_breaker_enabled": settings.CIRCUIT_BREAKER_ENABLED,
                "load_shedding_enabled": settings.LOAD_SHEDDING_ENABLED,
            },
        )
    
    async def process_chat(
        self,
        request: ChatRequest,
        db: AsyncSession,
    ) -> ChatResponse:
        """
        Process chat request through full RAG pipeline with protection.
        
        Args:
            request: Chat request
            db: Database session
            
        Returns:
            ChatResponse: Structured chat response
            
        Raises:
            RateLimitExceededError: If rate limit exceeded
            QuotaExceededError: If daily quota exceeded
            CircuitBreakerOpenError: If Gemini circuit is open
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
        
        # === PROTECTION LAYER: Pre-flight checks ===
        
        # Check 1: Rate limiting
        if settings.RATE_LIMIT_ENABLED:
            rate_limit_result = await self.rate_limiter.check_rate_limit(request.user_id)
            if not rate_limit_result.allowed:
                logger.warning(
                    f"Rate limit exceeded for user {request.user_id}",
                    extra={
                        "user_id": request.user_id,
                        "retry_after": rate_limit_result.retry_after,
                    },
                )
                raise RateLimitExceededError(
                    f"Rate limit exceeded. Try again in {rate_limit_result.retry_after} seconds.",
                    retry_after=rate_limit_result.retry_after,
                )
        
        # Check 2: Daily quota
        if settings.QUOTA_ENABLED:
            quota_status = await self.quota_manager.check_quota(db, request.user_id)
            if quota_status.quota_exceeded:
                logger.warning(
                    f"Quota exceeded for user {request.user_id}",
                    extra={
                        "user_id": request.user_id,
                        "tokens_used": quota_status.tokens_used,
                        "cost_used": quota_status.cost_used,
                        "reset_time": quota_status.reset_time.isoformat(),
                    },
                )
                raise QuotaExceededError(
                    f"Daily quota exceeded. Resets at {quota_status.reset_time.isoformat()}.",
                    reset_time=quota_status.reset_time.isoformat(),
                )
        
        # Check 3: Load shedding (adjust parameters if needed)
        adjusted_top_k = request.top_k
        adjusted_max_tokens = settings.MAX_OUTPUT_TOKENS
        apply_mmr = True
        
        if settings.LOAD_SHEDDING_ENABLED:
            load_metrics = self.load_shedder.check_load(
                original_top_k=request.top_k,
                original_max_tokens=settings.MAX_OUTPUT_TOKENS,
            )
            
            if load_metrics.degraded:
                degradation = load_metrics.degradation_config
                adjusted_top_k = degradation.top_k
                adjusted_max_tokens = degradation.max_output_tokens
                apply_mmr = degradation.enable_mmr
                
                logger.warning(
                    f"System under load - degraded mode active",
                    extra={
                        "load_level": load_metrics.load_level.value,
                        "cpu_percent": load_metrics.cpu_percent,
                        "memory_percent": load_metrics.memory_percent,
                        "original_top_k": request.top_k,
                        "adjusted_top_k": adjusted_top_k,
                        "original_max_tokens": settings.MAX_OUTPUT_TOKENS,
                        "adjusted_max_tokens": adjusted_max_tokens,
                        "apply_mmr": apply_mmr,
                    },
                )
        
        # === END PROTECTION LAYER ===
        
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
        
        # Step 1: Retrieve relevant chunks (with adjusted top_k and apply_mmr)
        retrieval_start = time.time()
        
        retrieval_results = await self.retriever.retrieve(
            query=request.query,
            user_id=request.user_id,
            db=db,
            top_k=adjusted_top_k,
            document_id=document_id,
            apply_mmr=apply_mmr,
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
        
        # Step 3: Generate answer (with circuit breaker protection)
        generation_start = time.time()
        
        try:
            # Get or create circuit breaker for Gemini
            if settings.CIRCUIT_BREAKER_ENABLED:
                gemini_breaker = self.circuit_breaker_manager.get_breaker(
                    name="gemini_generation",
                    config=CircuitBreakerConfig(
                        failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                        success_threshold=settings.CIRCUIT_BREAKER_SUCCESS_THRESHOLD,
                        timeout=settings.CIRCUIT_BREAKER_TIMEOUT,
                        window=settings.CIRCUIT_BREAKER_WINDOW,
                    ),
                )
                
                # Call with circuit breaker protection
                answer_response = await gemini_breaker.call(
                    self.generator.generate,
                    system_prompt=prompt_components.system_prompt,
                    user_prompt=prompt_components.user_prompt,
                    max_output_tokens=adjusted_max_tokens,
                )
            else:
                # Call directly without protection
                answer_response = self.generator.generate(
                    system_prompt=prompt_components.system_prompt,
                    user_prompt=prompt_components.user_prompt,
                    max_output_tokens=adjusted_max_tokens,
                )
                
        except CircuitBreakerOpenError as e:
            logger.error(
                f"Circuit breaker open - Gemini service unavailable",
                extra={
                    "user_id": request.user_id,
                    "query": request.query,
                },
            )
            raise
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
        
        # Step 5: Format response and store interaction
        total_latency = (time.time() - start_time) * 1000
        
        # Calculate cost
        cost_estimate = None
        if validated_response.token_usage:
            cost_estimate = self.cost_tracker.calculate_cost(
                model_name=settings.GENERATION_MODEL,
                prompt_tokens=validated_response.token_usage.prompt_tokens,
                completion_tokens=validated_response.token_usage.completion_tokens,
            )
        
        chat_response = await self._format_response(
            request=request,
            validated_response=validated_response,
            retrieval_results=retrieval_results,
            source_mapping=prompt_components.source_mapping,
            latency_ms=total_latency,
            retrieval_latency_ms=retrieval_latency,
            generation_latency_ms=generation_latency,
            cost_estimate=cost_estimate,
            db=db,
        )
        
        logger.info(
            f"Chat request complete",
            extra={
                "interaction_id": chat_response.interaction_id,
                "total_latency_ms": round(total_latency, 2),
                "retrieval_ms": round(retrieval_latency, 2),
                "prompt_ms": round(prompt_latency, 2),
                "generation_ms": round(generation_latency, 2),
                "validation_ms": round(validation_latency, 2),
                "confidence_score": chat_response.confidence_score,
                "citations": len(chat_response.citations),
                "cost": cost_estimate,
            }
        )
        
        return chat_response
    
    async def _format_response(
        self,
        request: ChatRequest,
        validated_response: AnswerResponse,
        retrieval_results: List[RetrievalResult],
        source_mapping: dict,
        latency_ms: float,
        retrieval_latency_ms: float,
        generation_latency_ms: float,
        cost_estimate: Optional[float],
        db: AsyncSession,
    ) -> ChatResponse:
        """
        Format validated answer into ChatResponse and store interaction.
        
        Args:
            request: Original chat request
            validated_response: Validated answer response
            retrieval_results: Retrieval results
            source_mapping: Source number to metadata mapping
            latency_ms: Total latency
            retrieval_latency_ms: Retrieval latency
            generation_latency_ms: Generation latency
            cost_estimate: Estimated cost in USD
            db: Database session
            
        Returns:
            ChatResponse: Formatted response with interaction_id
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
        
        # Store interaction in database
        interaction = ChatInteraction(
            user_id=request.user_id,
            query=request.query,
            answer=validated_response.answer,
            confidence_score=validated_response.confidence_score,
            citations_count=len(validated_response.citations),
            latency_ms=latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            generation_latency_ms=generation_latency_ms,
            prompt_tokens=validated_response.token_usage.prompt_tokens if validated_response.token_usage else None,
            completion_tokens=validated_response.token_usage.completion_tokens if validated_response.token_usage else None,
            total_tokens=validated_response.token_usage.total_tokens if validated_response.token_usage else None,
            model_name=settings.GENERATION_MODEL,
            cost_estimate=cost_estimate,
        )
        
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)
        
        # Create response
        response = ChatResponse(
            interaction_id=str(interaction.id),
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
