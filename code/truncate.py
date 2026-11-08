"""H_n from hashlib.sha256.

sha256() is the 32-byte digest. truncate() keeps the leading n bits.
"""

import hashlib


def sha256(message: bytes) -> bytes:
    """Return the 32-byte SHA-256 digest of message."""
    return hashlib.sha256(message).digest()


def truncate(digest: bytes, n: int) -> bytes:
    """Return the most significant n bits of a SHA-256 digest."""
    
    if n % 8 != 0:
        raise ValueError("n must be a multiple of 8")
        
    return digest[:n // 8]
    

