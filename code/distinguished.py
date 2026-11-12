"""Same walk as Floyd. Store one state every 2^d steps.

A state is stored only when its lowest distinguish_bits are zero.
The chain stops there. A second chain that ends on the same state
has joined the first one, and walking both again finds the two
messages that first landed on the same value.
"""

import time
import tracemalloc

from collision import Collision
from truncate import sha256, truncate


def chain_start(index: int, n: int, distinguish_bits: int) -> int:
    """A start state whose low bits are not already zero."""
    mask = (1 << n) - 1
    low = (1 << distinguish_bits) - 1
    start = (index * 0x9E3779B1 + 1) & mask
    if (start & low) == 0:
        start = (start + 1) & mask
    return start


def step(state: int, n: int) -> int:
    """Hash the state and keep the leading n bits."""
    width = n // 8
    return truncate(sha256(state.to_bytes(width, "big")), n)


def walk_to_distinguished(n, start, distinguish_bits, max_steps):
    """Return (endpoint, steps, hashes) when the low bits are zero."""
    low = (1 << distinguish_bits) - 1
    state = start
    for steps in range(1, max_steps + 1):
        state = step(state, n)
        if (state & low) == 0:
            return state, steps, steps
    return None


def colliding_states(n, start_a, steps_a, start_b, steps_b):
    """Two states that step onto the same value, plus hashes used."""
    hashes = 0
    if steps_a < steps_b:
        start_a, steps_a, start_b, steps_b = start_b, steps_b, start_a, steps_a
    for _ in range(steps_a - steps_b):
        start_a = step(start_a, n)
        hashes += 1

    previous_a = None
    previous_b = None
    guard = 0
    limit = steps_a + steps_b + 1
    while start_a != start_b:
        previous_a = start_a
        previous_b = start_b
        start_a = step(start_a, n)
        start_b = step(start_b, n)
        hashes += 2
        guard += 1
        if guard > limit:
            return None
    if previous_a is None or previous_a == previous_b:
        return None
    return previous_a, previous_b, hashes


def _as_collision(n, method, left, right, hashes, elapsed, peak) -> Collision:
    width = n // 8
    message = left.to_bytes(width, "big")
    other = right.to_bytes(width, "big")
    return Collision(
        n=n,
        method=method,
        message=message,
        other=other,
        prefix=truncate(sha256(message), n),
        hashes=hashes,
        time_in_seconds=elapsed,
        peak_bytes=peak,
    )


def distinguished(n: int, distinguish_bits: int) -> Collision:
    """Keep a state only when it is distinguished."""
    if distinguish_bits < 1 or distinguish_bits >= n:
        raise ValueError(f"distinguish bits must be from 1 to {n - 1}")

    per_round = 4 * max((1 << (n // 2)) >> distinguish_bits, 1)
    max_steps = 32 * (1 << distinguish_bits)
    stored = {}
    hashes = 0
    tracemalloc.start()
    started = time.perf_counter()

    for round_index in range(4):
        first = round_index * per_round
        for index in range(first, first + per_round):
            start = chain_start(index, n, distinguish_bits)
            hit = walk_to_distinguished(n, start, distinguish_bits, max_steps)
            if hit is None:
                continue
            endpoint, steps, used = hit
            hashes += used
            earlier = stored.get(endpoint)
            if earlier is None:
                stored[endpoint] = (start, steps)
                continue
            found = colliding_states(n, start, steps, earlier[0], earlier[1])
            if found is None:
                continue
            left, right, extra = found
            hashes += extra
            elapsed = time.perf_counter() - started
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            return _as_collision(n, "distinguished", left, right, hashes, elapsed, peak)

    tracemalloc.stop()
    raise RuntimeError(f"no distinguished-point collision for n={n}")
