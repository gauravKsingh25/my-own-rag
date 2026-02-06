"""Prompt building for RAG-based question answering."""
from typing import List, Optional, Any, Dict
from dataclasses import dataclass

from app.services.generation.token_budget import TokenBudgetManager
from app.services.generation.context_optimizer import ContextOptimizer
from app.services.generation.source_formatter import SourceFormatter
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PromptComponents:
    """Components of the final prompt."""
    
    system_prompt: str
    user_prompt: str
    context: str
    query: str
    source_count: int
    total_tokens: int
    context_tokens: int
    source_mapping: Dict[int, Dict[str, Any]]


class PromptBuilder:
    """
    Build prompts for RAG-based question answering.
    
    Features:
    - Comprehensive system instructions
    - Formatted context with citations
    - Token budget management
    - Context optimization
    - Source tracking
    """
    
    # System instructions for RAG
    SYSTEM_INSTRUCTIONS = """You are a helpful AI assistant that answers questions based on provided source documents.

CRITICAL RULES:
1. Answer ONLY using information from the provided sources
2. If the sources don't contain sufficient information to answer the question, explicitly state: "I don't have enough information in the provided sources to answer this question"
3. ALWAYS cite your sources using [Source X] notation when referencing information
4. If sources provide conflicting information, mention the conflict and cite both sources
5. When providing numbers, dates, or specific facts, quote them exactly as they appear in the sources
6. Do not make assumptions or add information not present in the sources
7. If a source is partially relevant, acknowledge what it does and doesn't cover
8. Be concise but complete in your answers

CITATION FORMAT:
- Reference sources as [Source 1], [Source 2], etc.
- Multiple sources for the same fact: [Source 1, Source 3]
- When quoting directly, use quotation marks and cite the source

ANSWER QUALITY:
- Provide specific, factual answers
- Use clear, professional language
- Organize information logically
- Highlight key points
- If the question has multiple parts, address each part"""
    
    def __init__(
        self,
        token_budget_manager: Optional[TokenBudgetManager] = None,
        context_optimizer: Optional[ContextOptimizer] = None,
        source_formatter: Optional[SourceFormatter] = None,
    ):
        """
        Initialize prompt builder.
        
        Args:
            token_budget_manager: Token budget manager instance
            context_optimizer: Context optimizer instance
            source_formatter: Source formatter instance
        """
        self.token_budget_manager = token_budget_manager or TokenBudgetManager()
        self.context_optimizer = context_optimizer or ContextOptimizer(
            token_budget_manager=self.token_budget_manager
        )
        self.source_formatter = source_formatter or SourceFormatter()
        
        logger.info("PromptBuilder initialized")
    
    def build_prompt(
        self,
        query: str,
        retrieval_results: List[Any],
        system_instructions: Optional[str] = None,
        optimize_context: bool = True,
    ) -> PromptComponents:
        """
        Build complete prompt from query and retrieval results.
        
        Pipeline:
        1. Calculate token budget
        2. Optimize context (if enabled)
        3. Format sources
        4. Build system and user prompts
        5. Return prompt components
        
        Args:
            query: User query
            retrieval_results: List of RetrievalResult objects
            system_instructions: Custom system instructions (optional)
            optimize_context: Apply context optimization
            
        Returns:
            PromptComponents: Complete prompt components
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        logger.info(
            f"Building prompt",
            extra={
                "query_preview": query[:100],
                "retrieval_results": len(retrieval_results),
                "optimize_context": optimize_context,
            }
        )
        
        # Use default or custom system instructions
        system_prompt = system_instructions or self.SYSTEM_INSTRUCTIONS
        
        # Step 1: Calculate token budget
        budget_info = self.token_budget_manager.calculate_budget(
            query=query,
            system_prompt=system_prompt,
        )
        
        context_budget = budget_info["context_budget"]
        
        if budget_info["budget_exceeded"]:
            logger.warning(
                f"Token budget exceeded before adding context",
                extra={
                    "query_tokens": budget_info["query_tokens"],
                    "system_tokens": budget_info["system_tokens"],
                    "context_budget": context_budget,
                }
            )
        
        # Handle empty retrieval results
        if not retrieval_results:
            logger.warning("No retrieval results provided")
            
            # Build prompt without context
            user_prompt = self._build_user_prompt_no_context(query)
            
            total_tokens = (
                budget_info["query_tokens"] +
                budget_info["system_tokens"] +
                self.token_budget_manager.count_tokens(user_prompt)
            )
            
            return PromptComponents(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                context="",
                query=query,
                source_count=0,
                total_tokens=total_tokens,
                context_tokens=0,
                source_mapping={},
            )
        
        # Step 2: Optimize context
        if optimize_context:
            optimized_results = self.context_optimizer.optimize(
                retrieval_results=retrieval_results,
                context_budget=context_budget,
            )
        else:
            optimized_results = retrieval_results
        
        # Step 3: Format sources
        formatting_info = self.source_formatter.extract_document_info(
            optimized_results
        )
        
        context = self.source_formatter.format_sources(
            contents=formatting_info["contents"],
            document_filenames=formatting_info["document_filenames"],
            section_titles=formatting_info["section_titles"],
            page_numbers=formatting_info["page_numbers"],
            metadata_list=formatting_info["metadata_list"],
        )
        
        # Create source mapping for citation tracking
        source_mapping = self.source_formatter.create_source_mapping(
            optimized_results
        )
        
        # Step 4: Build user prompt
        user_prompt = self._build_user_prompt(query, context)
        
        # Step 5: Calculate final token counts
        context_tokens = self.token_budget_manager.count_tokens(context)
        user_prompt_tokens = self.token_budget_manager.count_tokens(user_prompt)
        
        total_tokens = (
            budget_info["system_tokens"] +
            user_prompt_tokens
        )
        
        logger.info(
            f"Prompt building complete",
            extra={
                "source_count": len(optimized_results),
                "context_tokens": context_tokens,
                "total_tokens": total_tokens,
                "budget_utilization": round(
                    context_tokens / context_budget * 100, 2
                ) if context_budget > 0 else 0,
            }
        )
        
        return PromptComponents(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context=context,
            query=query,
            source_count=len(optimized_results),
            total_tokens=total_tokens,
            context_tokens=context_tokens,
            source_mapping=source_mapping,
        )
    
    def _build_user_prompt(
        self,
        query: str,
        context: str,
    ) -> str:
        """
        Build user prompt with context and query.
        
        Args:
            query: User query
            context: Formatted context sources
            
        Returns:
            str: User prompt
        """
        prompt = f"""Based on the following sources, please answer the question.

SOURCES:
{context}

QUESTION:
{query}

ANSWER:"""
        
        return prompt
    
    def _build_user_prompt_no_context(
        self,
        query: str,
    ) -> str:
        """
        Build user prompt without context (fallback).
        
        Args:
            query: User query
            
        Returns:
            str: User prompt
        """
        prompt = f"""I don't have any relevant sources to answer this question. 

QUESTION:
{query}

Please respond that you don't have information to answer this question."""
        
        return prompt
    
    def preview_prompt(
        self,
        prompt_components: PromptComponents,
        max_chars: int = 2000,
    ) -> str:
        """
        Generate a preview of the complete prompt for debugging.
        
        Args:
            prompt_components: Prompt components
            max_chars: Maximum characters to show
            
        Returns:
            str: Preview string
        """
        preview_lines = [
            "=" * 80,
            "PROMPT PREVIEW",
            "=" * 80,
            "",
            f"Source Count: {prompt_components.source_count}",
            f"Total Tokens: {prompt_components.total_tokens}",
            f"Context Tokens: {prompt_components.context_tokens}",
            "",
            "-" * 80,
            "SYSTEM PROMPT:",
            "-" * 80,
            prompt_components.system_prompt[:500] + "..." if len(prompt_components.system_prompt) > 500 else prompt_components.system_prompt,
            "",
            "-" * 80,
            "USER PROMPT:",
            "-" * 80,
        ]
        
        user_prompt_preview = prompt_components.user_prompt
        if len(user_prompt_preview) > max_chars:
            user_prompt_preview = user_prompt_preview[:max_chars] + f"\n\n... (truncated, {len(prompt_components.user_prompt) - max_chars} more chars)"
        
        preview_lines.append(user_prompt_preview)
        preview_lines.append("")
        preview_lines.append("=" * 80)
        
        return "\n".join(preview_lines)
