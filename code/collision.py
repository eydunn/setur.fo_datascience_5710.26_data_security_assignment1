"""One finished pair, and the printout of what it cost."""


class Collision:
    """Fill the fields when a search returns."""

    def __init__(self, n, method, message, other, prefix, hashes):
        self.n = n
        self.method = method
        self.message = message
        self.other = other
        self.prefix = prefix
        self.hashes = hashes


def show(found: Collision) -> None:
    """Print the pair, the shared prefix, and the cost of finding it."""
    pass
