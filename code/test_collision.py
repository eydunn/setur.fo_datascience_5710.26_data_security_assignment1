import hashlib

import pytest

from collision import Collision, is_verified, show
from search import METHODS, check_n, run_search

# A known pair that collides on the first 24 bits (74ef0b).
N = 24
A = bytes.fromhex("4074c0")
B = bytes.fromhex("930708")


def prefix_of(message, n):
    return int.from_bytes(hashlib.sha256(message).digest(), "big") >> (256 - n)


@pytest.fixture
def good():
    return Collision(N, "test", A, B, prefix_of(A, N), hashes=1000, time_in_seconds=0.5)


def test_valid_pair_is_verified(good, capsys):
    show(good)
    out = capsys.readouterr().out
    assert "Verified collision" in out
    assert "74ef0b" in out


def test_identical_messages_are_rejected(capsys):
    show(Collision(N, "test", A, A, prefix_of(A, N), hashes=1))
    out = capsys.readouterr().out
    assert "verified NO" in out
    assert "identical" in out


def test_wrong_stored_prefix_is_rejected(capsys):
    show(Collision(N, "test", A, B, prefix_of(A, N) ^ 1, hashes=1))
    assert "does not match" in capsys.readouterr().out


def test_missing_cost_fields_say_not_recorded(capsys):
    show(Collision(N, "test", A, B, prefix_of(A, N), hashes=1))
    out = capsys.readouterr().out
    assert "time     not recorded" in out
    assert "memory   not recorded" in out


def test_hex_line_only_when_n_is_multiple_of_4(capsys):
    # The same pair also collides on its first 22 bits.
    show(Collision(22, "test", A, B, prefix_of(A, 22), hashes=1))
    assert "(hex)" not in capsys.readouterr().out


def test_is_verified_accepts_good_pair_and_rejects_bad_ones(good):
    assert is_verified(good)
    assert not is_verified(Collision(N, "test", A, A, prefix_of(A, N), hashes=1))
    assert not is_verified(Collision(N, "test", A, B, prefix_of(A, N) ^ 1, hashes=1))


def test_check_n_follows_the_menu_rule():
    assert check_n(32) is None
    assert check_n(12) == "n must be a multiple of 8"
    assert check_n(0) == "n must be from 8 to 256"
    assert check_n(264) == "n must be from 8 to 256"


def test_run_search_finds_verified_pair_for_each_method():
    for method in METHODS:
        assert is_verified(run_search(method, 16)), method
