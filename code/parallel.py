"""Each search, split across processes.

Menu choice 4 asks which algorithm to parallelize.

Hash table and meaningful messages split the counter. Each process
hashes its own share, and the parent merges the prefixes.
Floyd starts one tortoise-hare walk per process, from different seeds.
Distinguished points split the chains. The parent merges the endpoints.
"""

import time
import tracemalloc
from concurrent.futures import ProcessPoolExecutor, as_completed

from collision import Collision
from distinguished import chain_start, colliding_states, walk_to_distinguished
from floyd import _cycle_pair
from meaningful import LETTER, ORDER, _with_serial
from truncate import sha256, truncate


def _ranges(total, workers):
    workers = max(1, min(workers, total))
    base, extra = divmod(total, workers)
    start = 0
    groups = []
    for worker in range(workers):
        size = base + (1 if worker < extra else 0)
        if size:
            groups.append((start, start + size))
            start += size
    return groups


def _hash_batch(spec):
    """Hash one share of the decimal counters."""
    n, start, count, step = spec
    rows = []
    for k in range(count):
        message = str(start + k * step).encode()
        rows.append((truncate(sha256(message), n), message))
    return rows


def _floyd_seed(spec):
    """One tortoise-hare walk from a single seed."""
    n, seed = spec
    width = n // 8
    hashes = 0
    step_limit = max(64 * (1 << (n // 2)), 1000)

    def step(state):
        """One step: hash the state, keep the leading n bits."""
        nonlocal hashes
        hashes += 1
        digest = sha256(state.to_bytes(width, "big"))
        return truncate(digest, n)

    pair = _cycle_pair(step, seed, step_limit)
    if pair is None:
        return None
    left, right = pair
    message = left.to_bytes(width, "big")
    return message, right.to_bytes(width, "big"), truncate(sha256(message), n), hashes


def _walk_many(spec):
    """Walk one batch of distinguished-point chains."""
    n, distinguish_bits, first, count, max_steps = spec
    chains = []
    hashes = 0
    for index in range(first, first + count):
        start = chain_start(index, n, distinguish_bits)
        hit = walk_to_distinguished(n, start, distinguish_bits, max_steps)
        if hit is None:
            continue
        endpoint, steps, used = hit
        hashes += used
        chains.append((endpoint, start, steps))
    return chains, hashes


def _letter_slice(spec):
    n, start, stop = spec
    found = {}
    hashes = 0
    for serial in range(start, stop):
        message = _with_serial(LETTER, serial)
        found.setdefault(truncate(sha256(message), n), serial)
        hashes += 1
    return found, hashes


def _order_slice(spec):
    n, start, stop, letters = spec
    hashes = 0
    for serial in range(start, stop):
        order = _with_serial(ORDER, serial)
        prefix = truncate(sha256(order), n)
        hashes += 1
        letter_serial = letters.get(prefix)
        if letter_serial is not None:
            return (prefix, letter_serial, serial), hashes
    return None, hashes


def _finished(n, method, message, other, prefix, hashes, started):
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return Collision(
        n=n,
        method=method,
        message=message,
        other=other,
        prefix=prefix,
        hashes=hashes,
        time_in_seconds=elapsed,
        peak_bytes=peak,
    )


def parallel_hash_table(n: int, workers: int) -> Collision:
    """Split the counters. The parent keeps the one prefix table."""
    workers = max(1, workers)
    batch = 2048
    seen = {}
    hashes = 0
    cursors = list(range(workers))
    tracemalloc.start()
    started = time.perf_counter()
    pool = ProcessPoolExecutor(max_workers=workers)
    try:
        while True:
            specs = [(n, cursors[w], batch, workers) for w in range(workers)]
            for rows in pool.map(_hash_batch, specs):
                for prefix, message in rows:
                    hashes += 1
                    other = seen.get(prefix)
                    if other is not None:
                        return _finished(
                            n, "parallel hash_table", message, other,
                            prefix, hashes, started,
                        )
                    seen[prefix] = message
            for w in range(workers):
                cursors[w] += batch * workers
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def parallel_floyd(n: int, workers: int) -> Collision:
    """One tortoise-hare walk per process, each from its own seed."""
    workers = max(1, workers)
    tracemalloc.start()
    started = time.perf_counter()
    pool = ProcessPoolExecutor(max_workers=workers)
    try:
        for round_index in range(4):
            seeds = range(round_index * workers, (round_index + 1) * workers)
            futures = [pool.submit(_floyd_seed, (n, seed)) for seed in seeds]
            for future in as_completed(futures):
                result = future.result()
                if result is None:
                    continue
                message, other, prefix, used = result
                return _finished(
                    n, "parallel floyd", message, other, prefix, used, started,
                )
        tracemalloc.stop()
        raise RuntimeError(f"no parallel Floyd collision for n={n}")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def parallel_distinguished(n: int, workers: int) -> Collision:
    """Split the chains. The parent merges the distinguished endpoints."""
    distinguish_bits = max(1, min(n // 4, n - 1))
    per_round = 4 * max((1 << (n // 2)) >> distinguish_bits, 1)
    max_steps = 32 * (1 << distinguish_bits)
    stored = {}
    hashes = 0
    tracemalloc.start()
    started = time.perf_counter()
    pool = ProcessPoolExecutor(max_workers=max(1, workers))
    try:
        for round_index in range(4):
            first = round_index * per_round
            specs = [
                (n, distinguish_bits, first + start, stop - start, max_steps)
                for start, stop in _ranges(per_round, workers)
            ]
            for chains, used in pool.map(_walk_many, specs):
                hashes += used
                for endpoint, start, steps in chains:
                    earlier = stored.get(endpoint)
                    if earlier is None:
                        stored[endpoint] = (start, steps)
                        continue
                    found = colliding_states(n, start, steps, earlier[0], earlier[1])
                    if found is None:
                        continue
                    left, right, extra = found
                    hashes += extra
                    width = n // 8
                    return _finished(
                        n, "parallel distinguished",
                        left.to_bytes(width, "big"),
                        right.to_bytes(width, "big"),
                        truncate(sha256(left.to_bytes(width, "big")), n),
                        hashes, started,
                    )
        tracemalloc.stop()
        raise RuntimeError(f"no parallel distinguished collision for n={n}")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def parallel_meaningful(n: int, workers: int) -> Collision:
    """Split the serials. The parent merges the letter prefixes."""
    width = 3 * (1 << (n // 2))
    hashes = 0
    letters = {}
    tracemalloc.start()
    started = time.perf_counter()
    pool = ProcessPoolExecutor(max_workers=max(1, workers))
    try:
        letter_specs = [(n, start, stop) for start, stop in _ranges(width, workers)]
        for found, used in pool.map(_letter_slice, letter_specs):
            hashes += used
            for prefix, serial in found.items():
                letters.setdefault(prefix, serial)

        order_specs = [
            (n, start, stop, letters) for start, stop in _ranges(width, workers)
        ]
        for hit, used in pool.map(_order_slice, order_specs):
            hashes += used
            if hit is None:
                continue
            prefix, letter_serial, order_serial = hit
            return _finished(
                n, "parallel meaningful",
                _with_serial(LETTER, letter_serial),
                _with_serial(ORDER, order_serial),
                prefix, hashes, started,
            )
        tracemalloc.stop()
        raise RuntimeError(f"no parallel meaningful collision for n={n}")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def parallel(n: int, workers: int, algorithm: str) -> Collision:
    """Run the chosen algorithm on several processes."""
    if algorithm == "1":
        return parallel_hash_table(n, workers)
    if algorithm == "2":
        return parallel_floyd(n, workers)
    if algorithm == "3":
        return parallel_distinguished(n, workers)
    if algorithm == "4":
        return parallel_meaningful(n, workers)
    raise ValueError(f"{algorithm} is outside 1 to 4")
