"""Primitive library tests.

Roadmap v0.1 extended the pure primitive set with math helpers,
collection aggregates, and string operations. Each test below runs a
small Noema program that exercises a group of primitives end-to-end, so
we cover the parser, the effect check (every new primitive is pure),
and the `_call_primitive` wrapping path in one shot.

The failure-mode test at the bottom is the regression for empty-list
aggregates: an empty `min_of` must surface as a typed `PrimitiveError`,
not a bare Python `ValueError`.
"""
from __future__ import annotations

import unittest

from noema import parse, run
from noema.runtime.errors import PrimitiveError


class PrimitiveLibraryTests(unittest.TestCase):
    # -- Math ------------------------------------------------------------

    def test_math_primitives(self) -> None:
        # Pack several math results into a list so one program exercises
        # abs/min/max/pow/floor/ceil/round together. Each primitive call
        # stays on one line because the outer parser is line-oriented.
        src = """
def answer
  intent "exercise the new math primitives"
  sig    () -> List
  effects {}
  cand
    list(abs(neg(7)), min(3, 9), max(3, 9), pow(2, 10), floor(2.9), ceil(2.1), round(2.5))
"""
        result = run(parse(src), "answer")
        # abs(-7)=7, min(3,9)=3, max(3,9)=9, 2**10=1024, floor(2.9)=2,
        # ceil(2.1)=3. Python's banker's rounding sends 2.5 to 2.
        self.assertEqual(result, [7, 3, 9, 1024, 2, 3, 2])

    # -- Collections -----------------------------------------------------

    def test_collection_primitives(self) -> None:
        # Build a list, reverse it, append to it, and aggregate over it.
        # Also checks `contains_item` (list membership) is distinct from
        # the existing `contains` (string substring).
        src = """
def roll
  intent "exercise the new collection primitives"
  sig    () -> List
  effects {}
  cand
    xs <- list(3, 1, 4, 1, 5)
    list(min_of(xs), max_of(xs), sum(xs), reverse(xs), append(xs, 9), contains_item(xs, 4), contains_item(xs, 99), sum(list()))
"""
        result = run(parse(src), "roll")
        self.assertEqual(
            result,
            [
                1,                   # min_of
                5,                   # max_of
                14,                  # sum
                [5, 1, 4, 1, 3],     # reverse
                [3, 1, 4, 1, 5, 9],  # append (non-mutating)
                True,                # contains_item(xs, 4)
                False,               # contains_item(xs, 99)
                0,                   # sum(list()) -> 0 by definition
            ],
        )

    def test_append_does_not_mutate_input(self) -> None:
        # Regression: `append` must return a fresh list. If it mutated,
        # `len(xs)` below would be 3, not 2.
        src = """
def grow
  intent "show append is non-mutating"
  sig    () -> List
  effects {}
  cand
    xs <- list(1, 2)
    ys <- append(xs, 3)
    list(len(xs), len(ys))
"""
        self.assertEqual(run(parse(src), "grow"), [2, 3])

    # -- Strings ---------------------------------------------------------

    def test_string_primitives(self) -> None:
        # Cover case/trim/prefix/suffix/replace/split/join in one program.
        # The final `join` round-trips a split string to verify the two
        # are genuine inverses for a simple input.
        src = """
def bake
  intent "exercise the new string primitives"
  sig    () -> List
  effects {}
  cand
    list(upper("cafe"), lower("NOEMA"), trim("  hi  "), starts_with("noema", "no"), ends_with("noema", "ma"), replace("a-b-c", "-", "/"), split("a,b,c", ","), join("/", split("a,b,c", ",")))
"""
        result = run(parse(src), "bake")
        self.assertEqual(
            result,
            [
                "CAFE",
                "noema",
                "hi",
                True,
                True,
                "a/b/c",
                ["a", "b", "c"],
                "a/b/c",
            ],
        )

    # -- Failure modes ---------------------------------------------------

    def test_min_of_empty_surfaces_as_primitive_error(self) -> None:
        # `min([])` raises ValueError in Python; `_call_primitive` must
        # wrap that as a typed Noema error so hosts can classify it
        # uniformly. Mirrors the div-by-zero regression in test_runtime.
        src = """
def boom
  intent "min of empty list"
  sig    () -> Any
  effects {}
  cand
    min_of(list())
"""
        with self.assertRaises(PrimitiveError) as cm:
            run(parse(src), "boom")
        self.assertEqual(cm.exception.fn, "min_of")


if __name__ == "__main__":
    unittest.main()
