"""The four searches split across worker processes.

Each worker runs tracemalloc and reports how many hashes it did, so the numbers
can be compared with the sequential searches. When a collision is found, the
workers are told to stop: tasks that are already running finish and are
counted, tasks still waiting are skipped.
"""

import multiprocessing
import os
import time
import tracemalloc

from collision import Collision
from distinguished import chain_start, colliding_states, walk_to_distinguished
from floyd import _cycle_pair
from meaningful import LETTER, ORDER, _with_serial
from truncate import sha256, truncate

BATCH = 4096           # hashes per task for the hash table and meaningful messages
CHAINS_PER_TASK = 16   # chains per task for distinguished points
STOP_CHECK = 2 ** 16   # a Floyd walk looks at the stop signal every 2^16 steps

stop_signal = None     # each worker gets its own copy in _start_worker


class _Stopped(Exception):  # empty exception
    pass


# Code that runs in the workers

def _start_worker(stop):
    """Runs once in every worker process."""
    global stop_signal
    stop_signal = stop
    tracemalloc.start()


def _reply(result, hashes):
    """What every task sends back to the parent."""
    worker_id = os.getpid()
    _, memory = tracemalloc.get_traced_memory()
    return result, hashes, worker_id, memory


def _hash_batch(task):
    n, first, count = task
    if stop_signal.is_set():
        return _reply([], 0)
    rows = []
    for counter in range(first, first + count):
        message = str(counter).encode()
        rows.append((truncate(sha256(message), n), message))
    return _reply(rows, count)


def _hash_serials(task):
    n, template, first, count = task
    if stop_signal.is_set():
        return _reply([], 0)
    rows = []
    for serial in range(first, first + count):
        prefix = truncate(sha256(_with_serial(template, serial)), n)
        rows.append((prefix, serial))
    return _reply(rows, count)


def _floyd_seed(task):
    n, seed = task
    width = n // 8
    hashes = 0

    def step(state):
        nonlocal hashes
        hashes += 1
        if hashes % STOP_CHECK == 0 and stop_signal.is_set():
            raise _Stopped
        return truncate(sha256(state.to_bytes(width, "big")), n)

    if stop_signal.is_set():
        return _reply(None, 0)
    try:
        pair = _cycle_pair(step, seed, max(64 * 2 ** (n // 2), 1000))
    except _Stopped:
        pair = None
    return _reply(pair, hashes)


def _walk_many(task):
    n, d, first, count, max_steps = task
    if stop_signal.is_set():
        return _reply([], 0)
    chains = []
    hashes = 0
    for index in range(first, first + count):
        start = chain_start(index, n, d)
        hit = walk_to_distinguished(n, start, d, max_steps)
        if hit is None:
            hashes += max_steps  # gave up on this chain, but the hashes were done
            continue
        endpoint, length, used = hit
        hashes += used
        chains.append((endpoint, start, length))
    return _reply(chains, hashes)


# Code that runs in the parent

def _new_pool(workers):
    """A pool of worker processes, and the signal that tells them to stop."""
    stop = multiprocessing.Event()
    pool = multiprocessing.Pool(max(1, workers), initializer=_start_worker, initargs=(stop,))
    return pool, stop


def _finish(n, method, message, other, hashes, start_time, worker_memory):
    """Stop the clock and the memory tracing, and return the Collision."""
    seconds = time.perf_counter() - start_time
    _, parent_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if message is None:
        raise RuntimeError(f"no {method} collision for n={n}")
    return Collision(
        n=n,
        method=method,
        message=message,
        other=other,
        prefix=truncate(sha256(message), n),
        hashes=hashes,
        time_in_seconds=seconds,
        peak_bytes=parent_memory + sum(worker_memory.values()),
    )


def parallel_hash_table(n: int, workers: int) -> Collision:
    """Workers hash batches of counters. The parent keeps the one prefix table."""
    number_of_counters = 8 * 2 ** (n // 2)  # far more than a collision needs
    tasks = [(n, first, BATCH) for first in range(0, number_of_counters, BATCH)]
    seen = {}            # prefix -> message
    total_hashes = 0
    worker_memory = {}   # worker id -> its memory peak
    message = other = None

    tracemalloc.start()
    start_time = time.perf_counter()
    pool, stop = _new_pool(workers)
    with pool:
        for rows, hashes, worker_id, memory in pool.imap_unordered(_hash_batch, tasks):
            total_hashes += hashes
            worker_memory[worker_id] = memory  # a worker's peak only grows
            if message is not None:
                continue  # already found: just collect the last results
            for prefix, new_message in rows:
                if prefix not in seen:
                    seen[prefix] = new_message
                else:
                    message, other = new_message, seen[prefix]
                    stop.set()
                    break

    return _finish(n, "parallel hash_table", message, other, total_hashes, start_time, worker_memory)


def parallel_floyd(n: int, workers: int) -> Collision:
    """Independent restarts: each worker runs a whole Floyd walk from its own seed."""
    tasks = [(n, seed) for seed in range(4 * max(1, workers))]
    total_hashes = 0
    worker_memory = {}
    message = other = None

    tracemalloc.start()
    start_time = time.perf_counter()
    pool, stop = _new_pool(workers)
    with pool:
        for pair, hashes, worker_id, memory in pool.imap_unordered(_floyd_seed, tasks):
            total_hashes += hashes
            worker_memory[worker_id] = memory
            if message is None and pair is not None:
                left, right = pair
                message = left.to_bytes(n // 8, "big")
                other = right.to_bytes(n // 8, "big")
                stop.set()

    return _finish(n, "parallel floyd (independent restarts)", message, other,
                   total_hashes, start_time, worker_memory)


def parallel_distinguished(n: int, workers: int,
                           distinguish_bits: int | None = None) -> Collision:
    """Workers walk batches of chains. The parent merges the distinguished endpoints."""
    d = distinguish_bits if distinguish_bits is not None else max(1, min(n // 4, n - 1))
    max_steps = 32 * 2 ** d
    number_of_chains = 8 * 2 ** (n // 2 - d)  # far more than a collision needs
    tasks = [(n, d, first, CHAINS_PER_TASK, max_steps)
             for first in range(0, number_of_chains, CHAINS_PER_TASK)]
    endpoints = {}       # endpoint -> (start, length) of the first chain that reached it
    total_hashes = 0
    worker_memory = {}
    message = other = None

    tracemalloc.start()
    start_time = time.perf_counter()
    pool, stop = _new_pool(workers)
    with pool:
        for chains, hashes, worker_id, memory in pool.imap_unordered(_walk_many, tasks):
            total_hashes += hashes
            worker_memory[worker_id] = memory
            if message is not None:
                continue
            for endpoint, start, length in chains:
                if endpoint not in endpoints:
                    endpoints[endpoint] = (start, length)
                    continue
                earlier_start, earlier_length = endpoints[endpoint]
                found = colliding_states(n, start, length, earlier_start, earlier_length)
                if found is not None:
                    left, right, extra = found
                    total_hashes += extra  # the re-walk ran in the parent
                    message = left.to_bytes(n // 8, "big")
                    other = right.to_bytes(n // 8, "big")
                    stop.set()
                    break

    return _finish(n, "parallel distinguished", message, other, total_hashes, start_time, worker_memory)


def parallel_meaningful(n: int, workers: int) -> Collision:
    """Workers hash the letters, then the orders. The parent keeps the letter table."""
    count = 3 * 2 ** (n // 2)
    letter_tasks = [(n, LETTER, first, min(BATCH, count - first)) for first in range(0, count, BATCH)]
    order_tasks = [(n, ORDER, first, min(BATCH, count - first)) for first in range(0, count, BATCH)]
    letters = {}         # prefix -> letter serial
    total_hashes = 0
    worker_memory = {}
    message = other = None

    tracemalloc.start()
    start_time = time.perf_counter()
    pool, stop = _new_pool(workers)
    with pool:
        # First every letter ...
        for rows, hashes, worker_id, memory in pool.imap_unordered(_hash_serials, letter_tasks):
            total_hashes += hashes
            worker_memory[worker_id] = memory
            for prefix, serial in rows:
                letters.setdefault(prefix, serial)

        # ... then the orders, until one has the same prefix as a letter.
        for rows, hashes, worker_id, memory in pool.imap_unordered(_hash_serials, order_tasks):
            total_hashes += hashes
            worker_memory[worker_id] = memory
            if message is not None:
                continue
            for prefix, serial in rows:
                if prefix in letters:
                    message = _with_serial(LETTER, letters[prefix])
                    other = _with_serial(ORDER, serial)
                    stop.set()
                    break

    return _finish(n, "parallel meaningful", message, other, total_hashes, start_time, worker_memory)


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
