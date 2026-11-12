"""Birthday search with tortoise and hare. Memory stays constant.

Each step hashes an n-bit state and keeps the leading n bits.
That result is the next state. The tortoise takes one step and the
hare takes two. They meet on the cycle. The collision is the pair of
states that both step onto the entrance of the cycle.
"""

import time
import tracemalloc

from collision import Collision
from truncate import sha256, truncate


def _cycle_pair(function, start, step_limit):
    """Return two inputs with the same image, or None."""
    tortoise = function(start)
    hare = function(tortoise)
    steps = 0
    while tortoise != hare:
        tortoise = function(tortoise)
        hare = function(function(hare))
        steps += 1
        if steps > step_limit:
            return None

    tortoise = start
    steps = 0
    while tortoise != hare:
        tortoise = function(tortoise)
        hare = function(hare)
        steps += 1
        if steps > step_limit:
            return None
    entrance = tortoise

    tail = start
    current = function(start)
    steps = 0
    while current != entrance:
        tail = current
        current = function(current)
        steps += 1
        if steps > step_limit:
            return None

    cycle = entrance
    current = function(entrance)
    steps = 0
    while current != entrance:
        cycle = current
        current = function(current)
        steps += 1
        if steps > step_limit:
            return None

    if tail == cycle:
        return None
    return tail, cycle


def floyd(n: int) -> Collision:
    """Iterate a function from n-bit states to n-bit states."""
    width = n // 8
    hashes = 0
    step_limit = max(64 * (1 << (n // 2)), 1000)
    tracemalloc.start()
    started = time.perf_counter()

    def function(state):
        nonlocal hashes
        hashes += 1
        digest = sha256(state.to_bytes(width, "big"))
        return truncate(digest, n)

    pair = None
    for seed in range(16):
        pair = _cycle_pair(function, seed, step_limit)
        if pair is not None:
            break
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if pair is None:
        raise RuntimeError(f"no Floyd collision for n={n}")

    left, right = pair
    message = left.to_bytes(width, "big")
    other = right.to_bytes(width, "big")
    return Collision(
        n=n,
        method="floyd",
        message=message,
        other=other,
        prefix=truncate(sha256(message), n),
        hashes=hashes,
        time_in_seconds=elapsed,
        peak_bytes=peak,
    )
