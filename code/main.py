"""Collision search on truncated SHA-256.

H_n(x) = prefix_n(SHA-256(x)), the n most significant bits.
A signature that checks only H_n accepts every message with that prefix.

Start at n = 32. For each method that finishes, record the two inputs,
the shared prefix, the number of hashes, the time, and the memory.

    truncate.py         hashlib.sha256, then the leading n bits
    hash_table.py       store every prefix; memory grows like 2^(n/2)
    floyd.py            tortoise and hare; memory stays constant
    distinguished.py    store one state every 2^d steps
    parallel.py         split those chains across processes
    meaningful.py       a letter and an order with the same prefix
    collision.py        the pair a search returns, and how it is printed
    run_experiments.py  many runs, one process each, one CSV row per run
    plot_results.py     the CSV turned into figures and summary tables

Run one search and print it:

    python main.py floyd --n 40 --seed 3
    python main.py distinguished --n 40 --distinguish-bits 10
    python main.py parallel --n 48 --workers 4

Each method is imported only when it runs, so unfinished modules do not stop
the others. A method is given seed, distinguish_bits and workers only if its
signature has a parameter with that name. Leave Collision.time_in_seconds and
Collision.peak_bytes as None in the methods: main measures them, so every
method is measured the same way.
"""

import argparse
import hashlib
import importlib
import inspect
import json
import sys
import time

from collision import Collision, show

METHODS = ["hash_table", "floyd", "distinguished", "parallel", "meaningful"]


def peak_rss_bytes(children: bool = False):
    """Peak resident memory in bytes: of this process, or with children=True
    of its largest child process that has finished. None if unavailable."""
    try:
        import resource
    except ImportError:  # Windows
        if children:
            return None
        try:
            import psutil
            return psutil.Process().memory_info().peak_wset
        except (ImportError, AttributeError):
            return None
    who = resource.RUSAGE_CHILDREN if children else resource.RUSAGE_SELF
    peak = resource.getrusage(who).ru_maxrss
    if children and peak == 0:
        return None
    # Linux reports KiB, macOS reports bytes.
    return peak if sys.platform == "darwin" else peak * 1024


def is_verified(found: Collision) -> bool:
    """Recompute both prefixes instead of trusting the search."""
    def prefix(message):
        digest = hashlib.sha256(message).digest()
        return int.from_bytes(digest, "big") >> (256 - found.n)

    return (found.message != found.other
            and prefix(found.message) == prefix(found.other) == found.prefix)


def run(method, n, seed=None, distinguish_bits=None, workers=None):
    """Import and run one search; return the Collision and the settings used."""
    search = getattr(importlib.import_module(method), method)
    params = inspect.signature(search).parameters

    kwargs = {}
    if "seed" in params:
        kwargs["seed"] = seed
    elif seed is not None:
        print(f"note: {method}() has no seed parameter, so its runs "
              f"cannot be reproduced", file=sys.stderr)
    if "distinguish_bits" in params:
        kwargs["distinguish_bits"] = (
            distinguish_bits if distinguish_bits is not None else n // 4)
    if "workers" in params and workers is not None:
        kwargs["workers"] = workers

    used_workers = kwargs.get("workers")
    if used_workers is None and "workers" in params:
        default = params["workers"].default
        used_workers = None if default is inspect.Parameter.empty else default

    baseline = peak_rss_bytes()  # interpreter + imports, before the search
    start = time.perf_counter()
    found = search(n, **kwargs)
    elapsed = time.perf_counter() - start

    if found.time_in_seconds is None:
        found.time_in_seconds = elapsed
    if found.peak_bytes is None:
        found.peak_bytes = peak_rss_bytes()

    settings = {
        "distinguish_bits": kwargs.get("distinguish_bits"),
        "workers": used_workers,
        "baseline_bytes": baseline,
        "children_peak_bytes": peak_rss_bytes(children=True),
    }
    return found, settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collision search on truncated SHA-256.")
    parser.add_argument("method", choices=METHODS)
    parser.add_argument("--n", type=int, default=32,
                        help="prefix length in bits (default 32)")
    parser.add_argument("--seed", type=int,
                        help="random seed, so a run can be repeated")
    parser.add_argument("--distinguish-bits", type=int,
                        help="d for distinguished and parallel (default n // 4)")
    parser.add_argument("--workers", type=int,
                        help="number of processes for parallel")
    parser.add_argument("--json", action="store_true",
                        help="print one JSON line instead (run_experiments.py)")
    args = parser.parse_args()

    try:
        found, settings = run(args.method, args.n, args.seed,
                              args.distinguish_bits, args.workers)
    except MemoryError:
        if not args.json:
            raise
        print(json.dumps({"status": "out_of_memory"}))
        sys.exit(3)

    if not args.json:
        show(found)
        return

    digits = (found.n + 3) // 4
    print(json.dumps({
        "status": "ok" if is_verified(found) else "invalid",
        "hashes": found.hashes,
        "time_in_seconds": found.time_in_seconds,
        "peak_bytes": found.peak_bytes,
        "message": found.message.hex(),
        "other": found.other.hex(),
        "prefix": f"{found.prefix:0{digits}x}",
        **settings,
    }))


if __name__ == "__main__":
    main()
