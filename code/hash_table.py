"""Birthday search that stores every prefix. Memory grows like 2^(n/2)."""
import hashlib

from collision import Collision
from truncate import truncate


def hash_table(n: int) -> Collision:
    """Remember every prefix that has been seen."""
    
    seen = {}
    hashes = 0
    i = 0
    while True:
        message = str(i).encode()
        digest = hashlib.sha256(message).digest()
        prefix = truncate(digest, n)
        hashes += 1
        
        if prefix in seen:
            other = seen[prefix]
            return Collision(n=n, method="hash_table", other=other, message=message, prefix=prefix, hashes=hashes)
        seen[prefix] = message
        i = i+1