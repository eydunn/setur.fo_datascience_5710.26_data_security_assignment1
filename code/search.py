"""What main.py, cli.py and run_experiments.py share: the method names, the
rule for n, the defaults, and the call that runs one search."""

from collision import Collision
from distinguished import default_distinguish_bits, distinguished
from floyd import floyd
from hash_table import hash_table
from meaningful import meaningful
from parallel import parallel_distinguished

METHODS = ["hash_table", "floyd", "distinguished", "parallel", "meaningful"]
D_METHODS = ("distinguished", "parallel")  # the methods that take distinguish bits
DEFAULT_WORKERS = 4


def check_n(n: int) -> str | None:
    """The rule for n. Returns what is wrong, or None."""
    if n % 8 != 0:
        return "n must be a multiple of 8"
    if not 8 <= n <= 256:
        return "n must be from 8 to 256"
    return None


def run_search(method: str, n: int, distinguish_bits: int | None = None,
               workers: int = DEFAULT_WORKERS) -> Collision:
    """Run one method. parallel splits distinguished-point chains."""
    if method == "hash_table":
        return hash_table(n)
    if method == "floyd":
        return floyd(n)
    if method == "distinguished":
        return distinguished(n, distinguish_bits or default_distinguish_bits(n))
    if method == "parallel":
        return parallel_distinguished(n, workers, distinguish_bits)
    return meaningful(n)
