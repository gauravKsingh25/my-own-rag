"""Tokenizer for text chunking using tiktoken."""
import re
from typing import List, Tuple
import tiktoken

from app.core.logging import get_logger

logger = get_logger(__name__)


class Tokenizer:
    """Tokenizer for counting and splitting text by tokens."""
    
    # Model to use for tokenization (cl100k_base is used by GPT-4 and GPT-3.5-turbo)
    DEFAULT_MODEL = "cl100k_base"
    
    # Sentence boundary patterns
    SENTENCE_ENDINGS = re.compile(r'[.!?]\s+')
    
    def __init__(self, encoding_name: str = None):
        """
        Initialize tokenizer.
        
        Args:
            encoding_name: Name of tiktoken encoding (default: cl100k_base)
        """
        self.encoding_name = encoding_name or self.DEFAULT_MODEL
        try:
            self.encoding = tiktoken.get_encoding(self.encoding_name)
            logger.debug(f"Tokenizer initialized with encoding: {self.encoding_name}")
        except Exception as e:
            logger.error(f"Failed to initialize tokenizer: {str(e)}", exc_info=True)
            raise
    
    def count_tokens(self, text: str) -> int:
        """
        Count number of tokens in text.
        
        Args:
            text: Input text
            
        Returns:
            int: Number of tokens
        """
        if not text:
            return 0
        
        try:
            tokens = self.encoding.encode(text)
            return len(tokens)
        except Exception as e:
            logger.error(f"Error counting tokens: {str(e)}", exc_info=True)
            # Fallback to rough estimate (4 chars per token)
            return len(text) // 4
    
    def split_by_token_limit(
        self,
        text: str,
        max_tokens: int = 500,
        overlap: int = 100,
    ) -> List[str]:
        """
        Split text into chunks by token limit, respecting sentence boundaries.
        
        Strategy:
        1. Try to split at sentence boundaries when possible
        2. If a single sentence exceeds max_tokens, split mid-sentence
        3. Add overlap between chunks for context preservation
        
        Args:
            text: Text to split
            max_tokens: Maximum tokens per chunk
            overlap: Token overlap between consecutive chunks
            
        Returns:
            List[str]: List of text chunks
        """
        if not text or not text.strip():
            return []
        
        # Validate parameters
        if overlap >= max_tokens:
            logger.warning(
                f"Overlap ({overlap}) >= max_tokens ({max_tokens}), reducing overlap"
            )
            overlap = max_tokens // 2
        
        # Check if entire text fits in one chunk
        total_tokens = self.count_tokens(text)
        if total_tokens <= max_tokens:
            return [text]
        
        # Split into sentences
        sentences = self._split_into_sentences(text)
        
        chunks = []
        current_chunk_sentences = []
        current_token_count = 0
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            
            # If single sentence exceeds max_tokens, split it forcefully
            if sentence_tokens > max_tokens:
                # Save current chunk if exists
                if current_chunk_sentences:
                    chunks.append(' '.join(current_chunk_sentences))
                    current_chunk_sentences = []
                    current_token_count = 0
                
                # Split large sentence
                sub_chunks = self._split_large_sentence(sentence, max_tokens)
                chunks.extend(sub_chunks)
                continue
            
            # Check if adding this sentence exceeds limit
            if current_token_count + sentence_tokens > max_tokens:
                # Save current chunk
                if current_chunk_sentences:
                    chunks.append(' '.join(current_chunk_sentences))
                
                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(
                    current_chunk_sentences, overlap
                )
                current_chunk_sentences = overlap_sentences + [sentence]
                current_token_count = self.count_tokens(' '.join(current_chunk_sentences))
            else:
                # Add sentence to current chunk
                current_chunk_sentences.append(sentence)
                current_token_count += sentence_tokens
        
        # Add final chunk
        if current_chunk_sentences:
            chunks.append(' '.join(current_chunk_sentences))
        
        # Clean up chunks
        chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
        
        logger.debug(
            f"Split text into {len(chunks)} chunks",
            extra={
                "total_tokens": total_tokens,
                "max_tokens": max_tokens,
                "overlap": overlap,
                "chunks_count": len(chunks),
            }
        )
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        
        Args:
            text: Input text
            
        Returns:
            List[str]: List of sentences
        """
        # Split by sentence endings
        sentences = self.SENTENCE_ENDINGS.split(text)
        
        # Clean and filter
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # If no sentences found (no punctuation), split by newlines
        if len(sentences) <= 1:
            sentences = [s.strip() for s in text.split('\n') if s.strip()]
        
        # If still no splits, return as single sentence
        if not sentences:
            sentences = [text]
        
        return sentences
    
    def _split_large_sentence(
        self,
        sentence: str,
        max_tokens: int
    ) -> List[str]:
        """
        Split a sentence that exceeds max_tokens into smaller chunks.
        
        This is a fallback for very long sentences without proper punctuation.
        
        Args:
            sentence: Long sentence to split
            max_tokens: Maximum tokens per chunk
            
        Returns:
            List[str]: List of sub-chunks
        """
        # Encode to tokens
        tokens = self.encoding.encode(sentence)
        
        chunks = []
        start_idx = 0
        
        while start_idx < len(tokens):
            # Get next chunk of tokens
            end_idx = start_idx + max_tokens
            chunk_tokens = tokens[start_idx:end_idx]
            
            # Decode back to text
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            start_idx = end_idx
        
        return chunks
    
    def _get_overlap_sentences(
        self,
        sentences: List[str],
        overlap_tokens: int
    ) -> List[str]:
        """
        Get sentences from end of list that fit within overlap token limit.
        
        Args:
            sentences: List of sentences
            overlap_tokens: Maximum tokens for overlap
            
        Returns:
            List[str]: Sentences that fit in overlap
        """
        if not sentences or overlap_tokens <= 0:
            return []
        
        overlap_sentences = []
        current_tokens = 0
        
        # Iterate from end backwards
        for sentence in reversed(sentences):
            sentence_tokens = self.count_tokens(sentence)
            
            if current_tokens + sentence_tokens <= overlap_tokens:
                overlap_sentences.insert(0, sentence)
                current_tokens += sentence_tokens
            else:
                break
        
        return overlap_sentences
