"""Tests for slice / at / char_at / indexof primitives.

Added 2026-05-11 to close the gap surfaced by the six-program
assessment. See ``dispatches/2026-05-11-indexed-primitives.md``.
"""
from __future__ import annotations

import unittest

from codifide import parse
from codifide.runtime.errors import PrimitiveError
from codifide.runtime.interpreter import run


def _run(src: str, entry: str = "f", args=None):
    return run(parse(src), entry=entry, args=args or [])


class SlicePolymorphic(unittest.TestCase):
    """``slice`` works on strings and lists with the same semantics."""

    def test_slice_of_string(self) -> None:
        src = """
def f
  intent "t"
  sig (s: String) -> String
  effects {}
  cand
    slice(s, 1, 4)
"""
        self.assertEqual(_run(src, args=["abcdef"]), "bcd")

    def test_slice_of_list(self) -> None:
        src = """
def f
  intent "t"
  sig () -> List
  effects {}
  cand
    slice(list(1, 2, 3, 4, 5), 1, 4)
"""
        self.assertEqual(_run(src), [2, 3, 4])

    def test_slice_clamps_out_of_range_indices(self) -> None:
        # Agents expect slice to be total; out-of-range indices
        # clamp rather than raise.
        src = """
def f
  intent "t"
  sig (s: String) -> String
  effects {}
  cand
    slice(s, -100, 100)
"""
        self.assertEqual(_run(src, args=["abc"]), "abc")

    def test_empty_slice_when_start_ge_end(self) -> None:
        src = """
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    slice("hello", 3, 2)
"""
        self.assertEqual(_run(src), "")


class AtAccess(unittest.TestCase):
    """``at`` accesses a single element by index."""

    def test_at_of_string_returns_single_char(self) -> None:
        src = """
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    at("hello", 1)
"""
        self.assertEqual(_run(src), "e")

    def test_at_of_list_returns_element(self) -> None:
        src = """
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    at(list(10, 20, 30), 2)
"""
        self.assertEqual(_run(src), 30)

    def test_at_with_negative_index(self) -> None:
        src = """
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    at("hello", -1)
"""
        self.assertEqual(_run(src), "o")

    def test_at_out_of_range_raises_primitive_error(self) -> None:
        src = """
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    at("hi", 10)
"""
        with self.assertRaises(PrimitiveError):
            _run(src)


class CharAtStringOnly(unittest.TestCase):
    """``char_at`` is string-only and rejects lists explicitly."""

    def test_char_at_works_on_string(self) -> None:
        src = """
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    char_at("hello", 0)
"""
        self.assertEqual(_run(src), "h")

    def test_char_at_rejects_list_input(self) -> None:
        src = """
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    char_at(list(1, 2, 3), 0)
"""
        with self.assertRaises(PrimitiveError):
            _run(src)


class IndexofPolymorphic(unittest.TestCase):
    """``indexof`` returns first index or -1, works on strings and lists."""

    def test_indexof_string_substring(self) -> None:
        src = """
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    indexof("hello world", "world")
"""
        self.assertEqual(_run(src), 6)

    def test_indexof_string_not_found(self) -> None:
        src = """
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    indexof("abc", "z")
"""
        self.assertEqual(_run(src), -1)

    def test_indexof_list_element(self) -> None:
        src = """
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    indexof(list("a", "b", "c"), "b")
"""
        self.assertEqual(_run(src), 1)

    def test_indexof_list_element_not_found(self) -> None:
        src = """
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    indexof(list(1, 2, 3), 99)
"""
        self.assertEqual(_run(src), -1)


class CapabilityManifestContainsNewPrimitives(unittest.TestCase):
    """The new primitives show up in the generated capability manifest."""

    def test_slice_indexof_at_char_at_are_in_manifest(self) -> None:
        from codifide.capability import generate_capability
        manifest = generate_capability()
        names = {p["name"] for p in manifest["primitives"]}
        for n in ("slice", "at", "char_at", "indexof"):
            self.assertIn(n, names, f"{n} missing from capability manifest")


if __name__ == "__main__":
    unittest.main()
