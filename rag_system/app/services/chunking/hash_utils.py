"""Hash utilities for content deduplication."""
import hashlib


def generate_content_hash(content: str) -> str:
    """
    Generate SHA256 hash of content for deduplication.
    
    Args:
        content: Text content to hash
        
    Returns:
        str: Hexadecimal SHA256 hash
    """
    # Normalize content before hashing (strip whitespace)
    normalized_content = content.strip()
    
    # Generate SHA256 hash
    hash_object = hashlib.sha256(normalized_content.encode('utf-8'))
    
    return hash_object.hexdigest()


def verify_content_hash(content: str, expected_hash: str) -> bool:
    """
    Verify content matches expected hash.
    
    Args:
        content: Text content to verify
        expected_hash: Expected SHA256 hash
        
    Returns:
        bool: True if hash matches
    """
    actual_hash = generate_content_hash(content)
    return actual_hash == expected_hash
