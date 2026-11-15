"""Each search, split across processes, with every worker's work measured.

Menu choice 4 asks which algorithm to parallelize.

Hash table and meaningful messages: workers hash batches, the parent keeps the
one table. Floyd: each worker runs a whole walk from its own seed (one walk
cannot be split, so these are independent restarts). Distinguished points:
workers walk batches of chains, the parent merges the endpoints.

Measured like the sequential searches: every worker runs tracemalloc too, every
hash any worker did is counted (also work still running when the collision
turned up), and memory is the parent's peak plus each worker's peak (an upper
bound, since the peaks need not happen at the same moment).
"""

import itertools
import multiprocessing
import os
import time
import tracemalloc
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

from collision import Collision
from distinguished import chain_start, colliding_states, walk_to_distinguished
from floyd import _cycle_pair
from meaningful import LETTER, ORDER, _with_serial
from truncate import sha256, truncate


def _batch_size(n):
    """Hashes per batch: small for small n, so little work is wasted at the end."""
    return max(1024, min(1 << 16, (1 << (n // 2)) // 16))


# ---------- runs in the workers ----------

_stop = None  # the parent's stop signal, used by Floyd walks

# A Floyd walk asks "should I stop?" once every STOP_CHECK steps. Asking costs
# about four hashes, so asking every step would slow the walk down; at this
# interval it is free, and a walk still stops within about half a second.
# 2^16 is also the largest batch the other methods hand out.
STOP_CHECK = 1 << 16


class _Stopped(Exception): # empty exception
    pass


def _init_worker(stop_event):
    """Each worker traces its memory, like a sequential search does."""
    global _stop
    _stop = stop_event
    tracemalloc.start()


def _report(result, hashes):
    """Every task sends back its result, its hashes, and this worker's memory peak."""
    return result, hashes, os.getpid(), tracemalloc.get_traced_memory()[1]


def _hash_batch(n, first, count):
    """Hash the decimal counters first, first + 1, ... like hash_table.py does."""
    rows = []
    for counter in range(first, first + count):
        message = str(counter).encode()
        rows.append((truncate(sha256(message), n), message))
    return _report(rows, count)


def _hash_serials(n, template, first, count):
    """Hash a letter or order template with the serials first, first + 1, ..."""
    rows = [(truncate(sha256(_with_serial(template, s)), n), s) for s in range(first, first + count)]
    return _report(rows, count)


def _floyd_seed(n, seed):
    """One whole tortoise-hare walk. Gives up early when the parent says stop."""
    width = n // 8
    hashes = 0

    def step(state):
        nonlocal hashes
        hashes += 1
        if hashes % STOP_CHECK == 0 and _stop.is_set():
            raise _Stopped
        return truncate(sha256(state.to_bytes(width, "big")), n)

    try:
        pair = _cycle_pair(step, seed, max(64 * (1 << (n // 2)), 1000))
    except _Stopped:
        pair = None
    return _report(pair, hashes)


def _walk_many(n, d, first, count, max_steps):
    """Walk chains first .. first + count - 1 to their distinguished points."""
    chains, hashes = [], 0
    for index in range(first, first + count):
        start = chain_start(index, n, d)
        hit = walk_to_distinguished(n, start, d, max_steps)
        if hit is None:
            hashes += max_steps  # an abandoned walk still cost its hashes
            continue
        endpoint, steps, used = hit
        hashes += used
        chains.append((endpoint, start, steps))
    return _report(chains, hashes)


# ---------- runs in the parent ----------

class Measured:
    """Worker processes, measured like a sequential search.

        with Measured(workers) as pool:
            for result in pool.run(tasks):   # tasks: (function, arg, arg, ...)
                ...
                return pool.collision(n, method, message, other)
    """

    def __init__(self, workers, ahead=2):
        self.size = max(1, workers)
        self.in_flight = ahead * self.size  # tasks queued or running at once

    def __enter__(self):
        tracemalloc.start()
        self.started = time.perf_counter()
        context = multiprocessing.get_context()
        self.stop = context.Event()
        self.pool = ProcessPoolExecutor(self.size, mp_context=context,
                                        initializer=_init_worker, initargs=(self.stop,))
        self.running = set()
        self.hashes = 0   # every hash any worker reported
        self.peaks = {}   # worker process id -> its memory peak
        return self

    def run(self, tasks):
        """Keep every worker busy and yield each result as soon as it is ready."""
        tasks = iter(tasks)
        while True:
            while len(self.running) < self.in_flight:
                task = next(tasks, None)
                if task is None:
                    break
                self.running.add(self.pool.submit(*task))
            if not self.running:
                return
            done, _ = wait(self.running, return_when=FIRST_COMPLETED)
            for future in done:
                self.running.discard(future)
                yield self._count(future)

    def _count(self, future):
        result, hashes, pid, peak = future.result()
        self.hashes += hashes
        self.peaks[pid] = max(peak, self.peaks.get(pid, 0))
        return result

    def _stop_workers(self):
        """Cancel tasks that have not started; wait for the running ones and count them."""
        self.stop.set()
        for future in self.running:
            future.cancel()
        for future in self.running:
            if not future.cancelled():
                self._count(future)
        self.running.clear()
        self.pool.shutdown(wait=True)

    def collision(self, n, method, message, other, prefix=None, extra_hashes=0):
        """Stop the workers and record the collision with all of their work.

        message and other are bytes, or n-bit states that become n/8 bytes.
        """
        self._stop_workers()
        elapsed = time.perf_counter() - self.started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        message, other = (m if isinstance(m, bytes) else m.to_bytes(n // 8, "big")
                          for m in (message, other))
        return Collision(
            n=n,
            method=method,
            message=message,
            other=other,
            prefix=truncate(sha256(message), n) if prefix is None else prefix,
            hashes=self.hashes + extra_hashes,
            time_in_seconds=elapsed,
            peak_bytes=peak + sum(self.peaks.values()),
        )

    def __exit__(self, *exc):
        self._stop_workers()
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        return False


def parallel_hash_table(n: int, workers: int) -> Collision:
    """Workers hash batches of counters. The parent keeps the one prefix table."""
    size = _batch_size(n)
    batches = ((_hash_batch, n, first, size) for first in itertools.count(0, size))
    with Measured(workers) as pool:
        seen = {}
        for rows in pool.run(batches):
            for prefix, message in rows:
                other = seen.setdefault(prefix, message)
                if other != message:
                    return pool.collision(n, "parallel hash_table", message, other, prefix)


def parallel_floyd(n: int, workers: int) -> Collision:
    """Independent restarts: each worker runs a whole Floyd walk from its own seed."""
    walks = ((_floyd_seed, n, seed) for seed in range(4 * max(1, workers)))
    with Measured(workers, ahead=1) as pool:
        for pair in pool.run(walks):
            if pair is not None:
                return pool.collision(n, "parallel floyd (independent restarts)", *pair)
    raise RuntimeError(f"no parallel Floyd collision for n={n}")


def parallel_distinguished(n: int, workers: int) -> Collision:
    """Workers walk batches of chains. The parent merges the distinguished endpoints."""
    d = max(1, min(n // 4, n - 1))
    max_steps = 32 * (1 << d)
    per_batch = max(1, _batch_size(n) >> d)
    limit = 16 * max((1 << (n // 2)) >> d, 1)
    batches = ((_walk_many, n, d, first, min(per_batch, limit - first), max_steps)
               for first in range(0, limit, per_batch))
    with Measured(workers) as pool:
        stored = {}
        for chains in pool.run(batches):
            for endpoint, start, steps in chains:
                earlier = stored.setdefault(endpoint, (start, steps))
                if earlier == (start, steps):
                    continue  # the first chain to reach this endpoint
                found = colliding_states(n, start, steps, *earlier)
                if found is not None:
                    left, right, extra = found
                    return pool.collision(n, "parallel distinguished", left, right, extra_hashes=extra)
    raise RuntimeError(f"no parallel distinguished collision for n={n}")


def parallel_meaningful(n: int, workers: int) -> Collision:
    """Workers hash the letters, then the orders. The parent keeps the letter table."""
    width = 3 * (1 << (n // 2))
    size = _batch_size(n)

    def batches(template):
        return ((_hash_serials, n, template, first, min(size, width - first))
                for first in range(0, width, size))

    with Measured(workers) as pool:
        letters = {}
        for rows in pool.run(batches(LETTER)):
            for prefix, serial in rows:
                letters.setdefault(prefix, serial)
        for rows in pool.run(batches(ORDER)):
            for prefix, serial in rows:
                letter = letters.get(prefix)
                if letter is not None:
                    return pool.collision(n, "parallel meaningful", _with_serial(LETTER, letter),
                                          _with_serial(ORDER, serial), prefix)
    raise RuntimeError(f"no parallel meaningful collision for n={n}")


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
