"""Answer validation and citation extraction."""
import re
from typing import List, Dict, Any, Set, Tuple

from app.services.generation.response_models import AnswerResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


class AnswerValidator:
    """
    Validate generated answers and extract citations.
    
    Features:
    - Extract [Source X] citations from answer
    - Validate citations against source mapping
    - Detect potential hallucinations
    - Calculate confidence score
    - Flag invalid citations
    """
    
    # Regex pattern for citation detection
    CITATION_PATTERN = r'\[Source\s+(\d+)(?:\s*,\s*(\d+))*\]'
    
    # Keywords that suggest lack of information
    UNCERTAINTY_PATTERNS = [
        r"I don't have",
        r"I do not have",
        r"insufficient information",
        r"not enough information",
        r"cannot find",
        r"unable to answer",
        r"no information",
        r"sources don't contain",
        r"sources do not contain",
    ]
    
    # Generic filler phrases that may indicate hallucination
    GENERIC_PATTERNS = [
        r"in general",
        r"typically",
        r"usually",
        r"commonly",
        r"it is known that",
        r"studies show",
        r"research indicates",
    ]
    
    def __init__(self):
        """Initialize answer validator."""
        self.citation_regex = re.compile(self.CITATION_PATTERN, re.IGNORECASE)
        self.uncertainty_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.UNCERTAINTY_PATTERNS
        ]
        self.generic_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.GENERIC_PATTERNS
        ]
        
        logger.info("AnswerValidator initialized")
    
    def validate_answer(
        self,
        answer_response: AnswerResponse,
        source_mapping: Dict[int, Dict[str, Any]],
    ) -> AnswerResponse:
        """
        Validate answer and extract citations.
        
        Pipeline:
        1. Extract citations from answer text
        2. Validate citations against source mapping
        3. Detect hallucinations
        4. Calculate confidence score
        5. Add warnings
        
        Args:
            answer_response: Generated answer response
            source_mapping: Mapping of source numbers to metadata
            
        Returns:
            AnswerResponse: Updated with validation results
        """
        answer = answer_response.answer
        
        logger.info(
            f"Validating answer",
            extra={
                "answer_length": len(answer),
                "available_sources": len(source_mapping),
            }
        )
        
        # Step 1: Extract citations
        citations = self._extract_citations(answer)
        answer_response.citations = citations
        answer_response.source_mapping = source_mapping
        
        # Step 2: Validate citations
        invalid_citations = self._validate_citations(citations, source_mapping)
        answer_response.invalid_citations = invalid_citations
        
        # Step 3: Detect hallucinations
        has_hallucinations = self._detect_hallucinations(
            answer=answer,
            citations=citations,
            invalid_citations=invalid_citations,
        )
        answer_response.has_hallucinations = has_hallucinations
        
        # Step 4: Calculate confidence score
        confidence = self._calculate_confidence(
            answer=answer,
            citations=citations,
            invalid_citations=invalid_citations,
            source_mapping=source_mapping,
        )
        answer_response.confidence_score = confidence
        
        # Step 5: Add warnings
        self._add_warnings(answer_response)
        
        logger.info(
            f"Answer validation complete",
            extra={
                "citations": len(citations),
                "invalid_citations": len(invalid_citations),
                "has_hallucinations": has_hallucinations,
                "confidence_score": round(confidence, 3),
                "warnings": len(answer_response.warnings),
            }
        )
        
        return answer_response
    
    def _extract_citations(self, answer: str) -> List[int]:
        """
        Extract citation numbers from answer text.
        
        Parses patterns like:
        - [Source 1]
        - [Source 2, 3]
        - [Source 1, Source 2]
        
        Args:
            answer: Answer text
            
        Returns:
            List[int]: Sorted list of unique citation numbers
        """
        citations: Set[int] = set()
        
        # Find all citation patterns
        matches = self.citation_regex.finditer(answer)
        
        for match in matches:
            # Extract all numbers from the match
            # Group 0 is the full match, groups after are individual numbers
            full_match = match.group(0)
            
            # Extract all numbers from the citation
            numbers = re.findall(r'\d+', full_match)
            
            for num_str in numbers:
                try:
                    num = int(num_str)
                    citations.add(num)
                except ValueError:
                    logger.warning(
                        f"Invalid citation number: {num_str}",
                        extra={"match": full_match}
                    )
        
        # Sort for consistency
        sorted_citations = sorted(list(citations))
        
        logger.debug(
            f"Extracted citations",
            extra={
                "count": len(sorted_citations),
                "citations": sorted_citations,
            }
        )
        
        return sorted_citations
    
    def _validate_citations(
        self,
        citations: List[int],
        source_mapping: Dict[int, Dict[str, Any]],
    ) -> List[int]:
        """
        Validate citations against available sources.
        
        Args:
            citations: Extracted citation numbers
            source_mapping: Available source numbers
            
        Returns:
            List[int]: Invalid citation numbers
        """
        available_sources = set(source_mapping.keys())
        cited_sources = set(citations)
        
        # Find invalid citations
        invalid = cited_sources - available_sources
        invalid_list = sorted(list(invalid))
        
        if invalid_list:
            logger.warning(
                f"Invalid citations detected",
                extra={
                    "invalid_citations": invalid_list,
                    "available_sources": sorted(list(available_sources)),
                }
            )
        
        return invalid_list
    
    def _detect_hallucinations(
        self,
        answer: str,
        citations: List[int],
        invalid_citations: List[int],
    ) -> bool:
        """
        Detect potential hallucinations in answer.
        
        Hallucination indicators:
        - No citations when answer is substantive
        - Invalid citations
        - Generic statements without citations
        - Uncertainty expressions
        
        Args:
            answer: Answer text
            citations: Extracted citations
            invalid_citations: Invalid citation numbers
            
        Returns:
            bool: True if hallucinations detected
        """
        # Check 1: Answer has substantive content but no citations
        word_count = len(answer.split())
        if word_count > 20 and not citations:
            logger.warning(
                f"No citations in substantive answer",
                extra={"word_count": word_count}
            )
            return True
        
        # Check 2: Has invalid citations
        if invalid_citations:
            logger.warning(
                f"Invalid citations present",
                extra={"invalid_count": len(invalid_citations)}
            )
            return True
        
        # Check 3: Generic statements without citations
        # Count generic patterns
        generic_count = sum(
            len(regex.findall(answer))
            for regex in self.generic_regex
        )
        
        if generic_count > 2 and len(citations) < 2:
            logger.warning(
                f"Generic statements without sufficient citations",
                extra={
                    "generic_count": generic_count,
                    "citations": len(citations),
                }
            )
            return True
        
        # No hallucinations detected
        return False
    
    def _calculate_confidence(
        self,
        answer: str,
        citations: List[int],
        invalid_citations: List[int],
        source_mapping: Dict[int, Dict[str, Any]],
    ) -> float:
        """
        Calculate confidence score for answer.
        
        Confidence factors:
        - Has citations: +0.4
        - No invalid citations: +0.3
        - Citation density: +0.2 (citations per 100 words)
        - No uncertainty: +0.1
        
        Score ranges:
        - 0.9-1.0: High confidence
        - 0.7-0.9: Good confidence
        - 0.5-0.7: Medium confidence
        - 0.3-0.5: Low confidence
        - 0.0-0.3: Very low confidence
        
        Args:
            answer: Answer text
            citations: Valid citations
            invalid_citations: Invalid citations
            source_mapping: Available sources
            
        Returns:
            float: Confidence score (0-1)
        """
        score = 0.0
        
        # Base score
        base_score = 0.5
        score += base_score
        
        # Factor 1: Has citations (+0.4)
        if citations:
            valid_citations = [c for c in citations if c not in invalid_citations]
            if valid_citations:
                # Partial credit based on ratio of valid citations
                citation_ratio = len(valid_citations) / max(len(citations), 1)
                score += 0.4 * citation_ratio
            
            logger.debug(
                f"Citation factor",
                extra={
                    "citations": len(citations),
                    "valid": len(valid_citations) if valid_citations else 0,
                    "bonus": 0.4 * (len(valid_citations) / max(len(citations), 1)) if citations else 0,
                }
            )
        
        # Factor 2: No invalid citations (+0.3)
        if not invalid_citations:
            score += 0.3
        else:
            # Reduce score based on invalid citation ratio
            invalid_ratio = len(invalid_citations) / max(len(citations), 1)
            score -= 0.3 * invalid_ratio
            
            logger.debug(
                f"Invalid citation penalty",
                extra={
                    "invalid_count": len(invalid_citations),
                    "penalty": 0.3 * invalid_ratio,
                }
            )
        
        # Factor 3: Citation density (+0.2 max)
        word_count = len(answer.split())
        if word_count > 0:
            # Calculate citations per 100 words
            citation_density = (len(citations) / word_count) * 100
            # Cap at 0.2 bonus (density of 5+ citations per 100 words)
            density_bonus = min(0.2, citation_density / 25 * 0.2)
            score += density_bonus
            
            logger.debug(
                f"Citation density bonus",
                extra={
                    "word_count": word_count,
                    "citation_density": round(citation_density, 2),
                    "bonus": round(density_bonus, 3),
                }
            )
        
        # Factor 4: No uncertainty expressions (+0.1)
        uncertainty_count = sum(
            len(regex.findall(answer))
            for regex in self.uncertainty_regex
        )
        
        if uncertainty_count == 0:
            score += 0.1
        else:
            # Partial penalty for uncertainty
            penalty = min(0.1, uncertainty_count * 0.05)
            score -= penalty
            
            logger.debug(
                f"Uncertainty penalty",
                extra={
                    "uncertainty_count": uncertainty_count,
                    "penalty": round(penalty, 3),
                }
            )
        
        # Clamp score to [0, 1]
        score = max(0.0, min(1.0, score))
        
        logger.debug(
            f"Confidence calculation complete",
            extra={
                "final_score": round(score, 3),
            }
        )
        
        return score
    
    def _add_warnings(self, answer_response: AnswerResponse):
        """
        Add warning messages to answer response.
        
        Args:
            answer_response: Answer response to update
        """
        # Warning for no citations
        if not answer_response.citations:
            answer_response.add_warning(
                "Answer does not cite any sources. Verify factual accuracy."
            )
        
        # Warning for invalid citations
        if answer_response.invalid_citations:
            answer_response.add_warning(
                f"Answer contains invalid citations: {answer_response.invalid_citations}. "
                f"These sources were not provided in the context."
            )
        
        # Warning for low confidence
        if answer_response.confidence_score < 0.5:
            answer_response.add_warning(
                f"Low confidence score ({answer_response.confidence_score:.2f}). "
                f"Answer may not be reliable."
            )
        
        # Warning for hallucinations
        if answer_response.has_hallucinations:
            answer_response.add_warning(
                "Potential hallucinations detected. Answer may contain unsupported claims."
            )
