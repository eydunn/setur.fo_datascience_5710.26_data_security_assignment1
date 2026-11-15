"""
SHA-256 assignment by Kristmund, Eyðun & Torkil

H_n(x) = prefix_n(SHA-256(x)), the n most significant bits.
A signature that checks only H_n accepts every message with that prefix.

Start at n = 32. For each method that finishes, record the two inputs,
the shared prefix, the number of hashes, the time, and the memory.

    truncate.py       hashlib.sha256, then the leading n bits
    hash_table.py     store every prefix; memory grows like 2^(n/2)
    floyd.py          tortoise and hare; memory stays constant
    distinguished.py  store one state every 2^d steps
    parallel.py       run one of the four searches on several processes
    meaningful.py     a letter and an order with the same prefix
    collision.py      the pair a search returns, and how it is printed
"""

from collision import show
from parallel import parallel
from search import DEFAULT_WORKERS, check_n, run_search


def read_n() -> int:
    """Ask for a prefix length. It must be a multiple of 8."""
    input_number = input("Prefix length n (multiple of 8, from 8 to 256): ")
    try:
        n = int(input_number)
    except ValueError:
        raise SystemExit("n must be an integer")
    problem = check_n(n)
    if problem:
        raise SystemExit(problem)
    return n


def read_method() -> str:
    """Ask which search to run. Ask again when the choice is outside 1-6."""
    print("1  hash table")
    print("2  Floyd")
    print("3  distinguished points")
    print("4  parallel")
    print("5  meaningful messages")
    print("6  exit")
    while True:
        choice = input("Method: ").strip()
        if choice in {"6", "1", "2", "3", "4", "5"}:
            return choice
        print(f"{choice} is outside 1 to 6")


def read_parallel_method() -> str:
    """Ask which algorithm to split across processes."""
    print("Parallelize which algorithm?")
    print("1  hash table")
    print("2  Floyd")
    print("3  distinguished points")
    print("4  meaningful messages")
    while True:
        choice = input("Algorithm: ").strip()
        if choice in {"1", "2", "3", "4"}:
            return choice
        print(f"{choice} is outside 1 to 4")


MENU = {"1": "hash_table", "2": "floyd", "3": "distinguished", "5": "meaningful"}


def run_choice(choice: str, n: int, algorithm: str | None = None):
    """The menu can split any of the four algorithms; the CLI only chains."""
    if choice == "4":
        return parallel(n, workers=DEFAULT_WORKERS, algorithm=algorithm)
    return run_search(MENU[choice], n)


def main() -> None:
    choice = read_method()
    if choice == "6":
        return
    algorithm = read_parallel_method() if choice == "4" else None
    n = read_n()
    found = run_choice(choice, n, algorithm)
    if found is None:
        raise SystemExit("that method has no search yet")
    show(found)


if __name__ == "__main__":
    main()
