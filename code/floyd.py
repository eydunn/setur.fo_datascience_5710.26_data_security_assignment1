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


def _cycle_pair(step, start, step_limit):
    """Return the two states that both step onto the cycle entrance."""
    # Tortoise is one step from the start. Hare is one step further.
    tortoise = step(start)
    hare = step(tortoise)
    steps = 0
    while tortoise != hare:
        tortoise = step(tortoise)
        hare = step(hare)
        hare = step(hare)
        steps += 1
        if steps > step_limit:
            return None

    tortoise = start
    steps = 0
    while tortoise != hare:
        tortoise = step(tortoise)
        hare = step(hare)
        steps += 1
        if steps > step_limit:
            return None
    entrance = tortoise

    tail = start
    current = step(start)
    steps = 0
    while current != entrance:
        tail = current
        current = step(current)
        steps += 1
        if steps > step_limit:
            return None

    cycle = entrance
    current = step(entrance)
    steps = 0
    while current != entrance:
        cycle = current
        current = step(current)
        steps += 1
        if steps > step_limit:
            return None

    if tail == cycle:
        return None
    return tail, cycle


def start_state(n: int, seed: int, attempt: int = 0) -> int:
    """Where a walk starts. Seed 0 starts at the attempt number itself."""
    return (seed * 0x9E3779B1 + attempt) & ((1 << n) - 1)


def floyd(n: int, seed: int = 0) -> Collision:
    """Walk n-bit states. Each step hashes the state and keeps the leading n bits.
    The seed moves the start states."""
    width = n // 8
    hashes = 0
    step_limit = max(64 * (1 << (n // 2)), 1000)
    tracemalloc.start()
    started = time.perf_counter()

    def step(state):
        """One step: hash the state, keep the leading n bits."""
        nonlocal hashes
        hashes += 1
        digest = sha256(state.to_bytes(width, "big"))
        return truncate(digest, n)

    pair = None
    for attempt in range(16):
        pair = _cycle_pair(step, start_state(n, seed, attempt), step_limit)
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
