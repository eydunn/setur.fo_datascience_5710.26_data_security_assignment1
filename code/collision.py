"""One finished pair, and the printout of what it cost."""
import hashlib


class Collision:
    """Fill the fields when a search returns."""

    def __init__(self, n, method, message, other, prefix, hashes,
                 time_in_seconds=None, peak_bytes=None):
        self.n = n                    # prefix length in bits
        self.method = method          # e.g. "floyd", "hash table"
        self.message = message        # bytes
        self.other = other            # bytes, must differ from message
        self.prefix = prefix          # int: the shared top n bits (as H_n returns)
        self.hashes = hashes          # number of SHA-256 evaluations
        self.time_in_seconds = time_in_seconds        # wall-clock time of the search
        self.peak_bytes = peak_bytes  # peak memory of the search


def _human_bytes(b) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    i = 0
    while b >= 1024 and i < len(units) - 1:
        b /= 1024
        i += 1
    return f"{b:.1f} {units[i]}"


def show(found: Collision) -> None:
    """Print the pair, the shared prefix, and the cost of finding it."""
    n = found.n
    d1 = hashlib.sha256(found.message).digest()
    d2 = hashlib.sha256(found.other).digest()
    p1 = int.from_bytes(d1, "big") >> (256 - n)
    p2 = int.from_bytes(d2, "big") >> (256 - n)

    problems = []
    if found.message == found.other:
        problems.append("the two messages are identical")
    if p1 != p2:
        problems.append("the recomputed prefixes differ")
    elif p1 != found.prefix:
        problems.append("the stored prefix does not match the recomputed one")

    print(f"=== {found.method}, n = {n} ===")
    print(f"message  {found.message.hex()}")
    print(f"  SHA-256  {d1.hex()}")
    print(f"other    {found.other.hex()}")
    print(f"  SHA-256  {d2.hex()}")
    print(f"prefix   {found.prefix:0{n}b}  ({n} bits)")
    if n % 4 == 0:
        print(f"         {found.prefix:0{n // 4}x}  (hex)")
    if problems:
        print("verified NO: " + "; ".join(problems))
    else:
        print("verified yes")

    print(f"hashes:   {found.hashes}")
    if found.time_in_seconds is None:
        print("time     not recorded")
    else:
        print(f"time     {found.time_in_seconds:.3f} s")
    if found.peak_bytes is None:
        print("memory   not recorded")
    else:
        print(f"memory   {_human_bytes(found.peak_bytes)}")
