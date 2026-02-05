"""Text normalization utilities for parsed content."""
import re
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class TextNormalizer:
    """Normalizes extracted text while preserving meaning."""
    
    @staticmethod
    def normalize(text: str) -> str:
        """
        Normalize text content.
        
        Operations:
        - Remove excessive whitespace
        - Normalize newlines
        - Preserve paragraph breaks
        - Preserve meaning, punctuation, and case
        
        Args:
            text: Raw text to normalize
            
        Returns:
            str: Normalized text
        """
        if not text:
            return ""
        
        # Normalize line endings to \n
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Replace multiple spaces with single space (but preserve newlines)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Replace more than 2 consecutive newlines with exactly 2
        # This preserves paragraph breaks
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove spaces at the beginning and end of lines
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        # Remove leading/trailing whitespace from entire text
        text = text.strip()
        
        return text
    
    @staticmethod
    def normalize_section_title(title: Optional[str]) -> Optional[str]:
        """
        Normalize section title.
        
        Args:
            title: Section title to normalize
            
        Returns:
            Optional[str]: Normalized title or None
        """
        if not title:
            return None
        
        # Remove excessive whitespace
        title = re.sub(r'\s+', ' ', title)
        
        # Strip leading/trailing whitespace
        title = title.strip()
        
        # Return None if empty after normalization
        return title if title else None
    
    @staticmethod
    def clean_bullet_point(text: str) -> str:
        """
        Clean bullet point text while preserving the bullet character.
        
        Args:
            text: Bullet point text
            
        Returns:
            str: Cleaned text
        """
        # Common bullet characters
        bullet_chars = ['•', '·', '◦', '▪', '▫', '–', '-', '*', '○', '●']
        
        text = text.strip()
        
        # If text starts with a bullet character followed by space, preserve it
        for bullet in bullet_chars:
            if text.startswith(bullet):
                # Ensure single space after bullet
                text = bullet + ' ' + text[len(bullet):].lstrip()
                break
        
        return text
    
    @staticmethod
    def preserve_paragraph_breaks(text: str) -> str:
        """
        Ensure paragraph breaks are preserved.
        
        Args:
            text: Text with potential paragraph breaks
            
        Returns:
            str: Text with preserved paragraph breaks
        """
        # Split by double newlines (paragraph breaks)
        paragraphs = text.split('\n\n')
        
        # Clean each paragraph
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # Rejoin with double newlines
        return '\n\n'.join(paragraphs)
