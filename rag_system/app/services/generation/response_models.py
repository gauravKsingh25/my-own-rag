"""Response models for answer generation."""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class TokenUsage:
    """Token usage statistics."""
    
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class AnswerResponse:
    """
    Structured response for RAG answer generation.
    
    Attributes:
        answer: Generated answer text
        citations: List of cited source numbers
        source_mapping: Mapping of source numbers to metadata
        confidence_score: Confidence in answer quality (0-1)
        token_usage: Token usage statistics
        latency_ms: Generation latency in milliseconds
        model: Model used for generation
        has_hallucinations: Flag for potential hallucinations
        invalid_citations: List of invalid citation numbers
        warnings: List of warning messages
        metadata: Additional metadata
    """
    
    answer: str
    citations: List[int] = field(default_factory=list)
    source_mapping: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    confidence_score: float = 1.0
    token_usage: Optional[TokenUsage] = None
    latency_ms: float = 0.0
    model: str = ""
    has_hallucinations: bool = False
    invalid_citations: List[int] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "answer": self.answer,
            "citations": self.citations,
            "source_mapping": self.source_mapping,
            "confidence_score": self.confidence_score,
            "token_usage": self.token_usage.to_dict() if self.token_usage else None,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "has_hallucinations": self.has_hallucinations,
            "invalid_citations": self.invalid_citations,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }
    
    def add_warning(self, warning: str):
        """Add a warning message."""
        self.warnings.append(warning)
    
    def validate(self) -> bool:
        """
        Validate response quality.
        
        Returns:
            bool: True if response passes quality checks
        """
        # Check for empty answer
        if not self.answer or not self.answer.strip():
            return False
        
        # Check confidence threshold
        if self.confidence_score < 0.3:
            return False
        
        # Check for excessive hallucinations
        if self.has_hallucinations and len(self.invalid_citations) > 2:
            return False
        
        return True


@dataclass
class GenerationRequest:
    """Request for answer generation."""
    
    system_prompt: str
    user_prompt: str
    model: str = ""
    temperature: float = 0.1
    max_output_tokens: int = 8192
    stream: bool = False
    timeout: int = 60
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "model": self.model,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "stream": self.stream,
            "timeout": self.timeout,
        }
