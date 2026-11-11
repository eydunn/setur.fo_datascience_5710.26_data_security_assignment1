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
    parallel.py       split those chains across processes
    meaningful.py     a letter and an order with the same prefix
    collision.py      the pair a search returns, and how it is printed
"""

from collision import show
from distinguished import distinguished
from floyd import floyd
from hash_table import hash_table
from meaningful import meaningful
from parallel import parallel


def read_n() -> int:
    """Ask for a prefix length. It must be a multiple of 8."""
    input_number = input("Prefix length n (multiple of 8, from 8 to 256): ")
    try:
        n = int(input_number)
    except ValueError:
        raise SystemExit("n must be an integer")
    if n % 8 != 0:
        raise SystemExit("n must be a multiple of 8")
    if not 8 <= n <= 256:
        raise SystemExit("n must be from 8 to 256")
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


def run_search(choice: str, n: int):
    if choice == "1":
        return hash_table(n)
    if choice == "2":
        return floyd(n)
    if choice == "3":
        return distinguished(n, n // 4)
    if choice == "4":
        return parallel(n, workers=4)
    return meaningful(n)


def main() -> None:
    choice = read_method()
    if choice == "6":
        return
    n = read_n()
    found = run_search(choice, n)
    if found is None:
        raise SystemExit("that method has no search yet")
    show(found)


if __name__ == "__main__":
    main()
