"""H_n from hashlib.sha256.

sha256() is the 32-byte digest. truncate() keeps the leading n bits.
"""

import hashlib


def sha256(message: bytes) -> bytes:
    """Return the 32-byte SHA-256 digest of message."""
    return hashlib.sha256(message).digest()


def truncate(digest: bytes, n: int) -> int:
    """Return the most significant n bits of a SHA-256 digest, as an integer."""
    if not 0 < n <= 256:
        raise ValueError("n must be from 1 to 256")
    return int.from_bytes(digest, "big") >> (256 - n)
    

