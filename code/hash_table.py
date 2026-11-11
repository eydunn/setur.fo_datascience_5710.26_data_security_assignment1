"""Birthday search that stores every prefix. Memory grows like 2^(n/2)."""

import time
import tracemalloc

from collision import Collision
from truncate import sha256, truncate


def hash_table(n: int) -> Collision:
    """Remember every prefix that has been seen."""
    
    seen = {}
    hashes = 0
    i = 0
    tracemalloc.start()
    start_time = time.perf_counter()
    while True:
        message = str(i).encode()
        digest = sha256(message)
        prefix = truncate(digest, n)
        hashes += 1
        
        if prefix in seen:
            other = seen[prefix]
            
            elapsed_time = time.perf_counter() - start_time
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            return Collision(n=n, method="hash_table", other=other, message=message, prefix=prefix, hashes=hashes,time_in_seconds=elapsed_time, peak_bytes=peak)
        seen[prefix] = message
        i = i+1