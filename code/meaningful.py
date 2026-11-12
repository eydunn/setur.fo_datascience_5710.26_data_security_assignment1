"""A letter and an order that share one prefix.

The two sentences stay fixed. Only the eight-digit serial at the end
changes. Letter serials fill a table of leading bits. The first order
serial that lands on a stored prefix is the collision.
"""

import time
import tracemalloc

from collision import Collision
from truncate import sha256, truncate

LETTER = b"I recommend Alice, a careful and honest intern. Ref "
ORDER = b"Grant Alice full clearance to the secret files. Ref "


def _with_serial(template: bytes, serial: int) -> bytes:
    return template + f"{serial:08d}".encode("ascii")


def meaningful(n: int) -> Collision:
    """Two readable messages, one free block each, one shared prefix."""
    width = 3 * (1 << (n // 2))
    letters = {}
    hashes = 0
    tracemalloc.start()
    started = time.perf_counter()

    for serial in range(width):
        message = _with_serial(LETTER, serial)
        letters.setdefault(truncate(sha256(message), n), serial)
        hashes += 1

    for serial in range(width):
        order = _with_serial(ORDER, serial)
        prefix = truncate(sha256(order), n)
        hashes += 1
        letter_serial = letters.get(prefix)
        if letter_serial is None:
            continue
        letter = _with_serial(LETTER, letter_serial)
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return Collision(
            n=n,
            method="meaningful",
            message=letter,
            other=order,
            prefix=prefix,
            hashes=hashes,
            time_in_seconds=elapsed,
            peak_bytes=peak,
        )

    tracemalloc.stop()
    raise RuntimeError(f"no meaningful collision for n={n}")
