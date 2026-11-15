"""Run one search from the command line, without the menu.

    python cli.py floyd --n 32
    python cli.py distinguished --n 40 --distinguish-bits 10
    python cli.py parallel --n 40 --workers 4 --json

main.py is the interactive menu. This is the same searches for scripts:
run_experiments.py starts one `python cli.py ... --json` per run and reads
the single JSON line it prints.

n follows the menu's rule: a multiple of 8, from 8 to 256.
parallel splits distinguished-point chains, the method the runner compares
against distinguished with the same d.

The searches are deterministic. --seed is accepted and recorded so the
runner can number its trials, but it does not change the search.
"""

import argparse
import hashlib
import json
import multiprocessing
import sys

from collision import Collision, show
from distinguished import distinguished
from floyd import floyd
from hash_table import hash_table
from meaningful import meaningful
from parallel import parallel_distinguished

METHODS = ["hash_table", "floyd", "distinguished", "parallel", "meaningful"]


def check_n(n: int) -> str | None:
    """The menu's rule for n. Returns what is wrong, or None."""
    if n % 8 != 0:
        return "n must be a multiple of 8"
    if not 8 <= n <= 256:
        return "n must be from 8 to 256"
    return None


def peak_rss_bytes(children: bool = False):
    """Peak resident memory in bytes: of this process, or with children=True
    of its largest finished child process. None if unavailable."""
    try:
        import resource
    except ImportError:  # Windows
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


def run_search(method, n, distinguish_bits, workers) -> Collision:
    if method == "hash_table":
        return hash_table(n)
    if method == "floyd":
        return floyd(n)
    if method == "distinguished":
        return distinguished(n, distinguish_bits)
    if method == "parallel":
        return parallel_distinguished(n, workers, distinguish_bits)
    return meaningful(n)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collision search on truncated SHA-256, without the menu.")
    parser.add_argument("method", choices=METHODS)
    parser.add_argument("--n", type=int, default=32,
                        help="prefix length in bits, a multiple of 8 from 8 "
                             "to 256 (default 32)")
    parser.add_argument("--seed", type=int,
                        help="trial number; recorded only, the searches are "
                             "deterministic")
    parser.add_argument("--distinguish-bits", type=int,
                        help="d for distinguished and parallel (default n // 4)")
    parser.add_argument("--workers", type=int,
                        help="processes for parallel (default 4, as the menu)")
    parser.add_argument("--json", action="store_true",
                        help="print one JSON line instead (run_experiments.py)")
    args = parser.parse_args()

    problem = check_n(args.n)
    if problem:
        parser.error(problem)
    d = None
    if args.method in ("distinguished", "parallel"):
        d = args.distinguish_bits if args.distinguish_bits is not None else args.n // 4
        if not 1 <= d < args.n:
            parser.error(f"distinguish bits must be from 1 to {args.n - 1}")
    workers = None
    if args.method == "parallel":
        workers = args.workers if args.workers is not None else 4
        if workers < 1:
            parser.error("workers must be at least 1")

    baseline = peak_rss_bytes()  # interpreter and imports, before the search
    try:
        found = run_search(args.method, args.n, d, workers)
    except MemoryError:
        if not args.json:
            raise
        print(json.dumps({"status": "out_of_memory", "baseline_bytes": baseline,
                          "distinguish_bits": d, "workers": workers}))
        sys.exit(3)

    if not args.json:
        show(found)
        return

    # Reap parallel's workers so their peak memory is counted. Python
    # waits for them at exit anyway.
    for child in multiprocessing.active_children():
        child.join()
    print(json.dumps({
        "status": "ok" if is_verified(found) else "invalid",
        "hashes": found.hashes,
        "seconds": found.time_in_seconds,
        "peak_bytes": found.peak_bytes,
        "baseline_bytes": baseline,
        "children_peak_bytes": peak_rss_bytes(children=True),
        "distinguish_bits": d,
        "workers": workers,
        "message": found.message.hex(),
        "other": found.other.hex(),
        "prefix": f"{found.prefix:0{found.n // 4}x}",
    }))


if __name__ == "__main__":
    main()
