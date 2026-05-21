"""Multiple `when` clause tests.

Verifies that multiple `when` clauses on a single candidate are implicitly
ANDed — all must hold for the candidate to be selected. This matches the
behavior of `pre` and `post` (all enforced) and prevents silent guard loss
when agents naturally write one condition per line.

Key invariants:
- A single `when` clause behaves identically to before (no regression).
- Multiple `when` clauses are combined with `and()` — all must be true.
- The canonical form emits `and(guard1, guard2, ...)` for multiple guards.
- bind-before-when detection still works with multiple `when` clauses.
- Cost-based dispatch interacts correctly with multi-when candidates.
"""
from __future__ import annotations

import unittest

from codifide import parse, run
from codifide.runtime.errors import ParseError, DispatchError
from codifide.core.types import Call


class SingleWhenUnchanged(unittest.TestCase):
    """Single `when` clause behavior is identical to pre-amendment."""

    def test_single_when_selects_candidate(self) -> None:
        src = """
module test

def f
  intent "test"
  sig    (x: Int) -> String
  effects {}
  cand
    intent "positive"
    when gt(x, 0)
    "positive"
  cand
    intent "fallback"
    "non-positive"
"""
        m = parse(src)
        self.assertEqual(run(m, "f", args=[5]), "positive")
        self.assertEqual(run(m, "f", args=[-1]), "non-positive")

    def test_single_when_guard_is_direct_expr(self) -> None:
        """A single when clause produces a direct expression, not and(expr)."""
        src = """
module test

def f
  intent "test"
  sig    (x: Int) -> String
  effects {}
  cand
    when gt(x, 0)
    "yes"
"""
        m = parse(src)
        guard = m.symbols[0].candidates[0].guard
        # Should be a Call to 'gt', not wrapped in 'and'
        self.assertIsInstance(guard, Call)
        self.assertEqual(guard.fn, "gt")


class MultiWhenImplicitAnd(unittest.TestCase):
    """Multiple `when` clauses are implicitly ANDed."""

    def test_two_when_clauses_both_must_hold(self) -> None:
        src = """
module test

def in_range
  intent "check if x is in range (0, 10)"
  sig    (x: Int) -> String
  effects {}
  cand
    intent "in range"
    when gt(x, 0)
    when lt(x, 10)
    "in range"
  cand
    intent "out of range"
    "out of range"
"""
        m = parse(src)
        self.assertEqual(run(m, "in_range", args=[5]), "in range")
        self.assertEqual(run(m, "in_range", args=[0]), "out of range")
        self.assertEqual(run(m, "in_range", args=[10]), "out of range")
        self.assertEqual(run(m, "in_range", args=[-1]), "out of range")

    def test_three_when_clauses_all_must_hold(self) -> None:
        src = """
module test

def classify
  intent "classify number"
  sig    (x: Int) -> String
  effects {}
  cand
    intent "sweet spot"
    when gt(x, 0)
    when lt(x, 100)
    when eq(mod(x, 2), 0)
    "even and in range"
  cand
    intent "fallback"
    "other"
"""
        m = parse(src)
        self.assertEqual(run(m, "classify", args=[4]), "even and in range")
        self.assertEqual(run(m, "classify", args=[3]), "other")  # odd
        self.assertEqual(run(m, "classify", args=[100]), "other")  # out of range
        self.assertEqual(run(m, "classify", args=[-2]), "other")  # negative

    def test_multi_when_produces_and_call_in_ast(self) -> None:
        """Multiple when clauses produce an and() Call node in the AST."""
        src = """
module test

def f
  intent "test"
  sig    (x: Int) -> String
  effects {}
  cand
    when gt(x, 0)
    when lt(x, 10)
    "yes"
"""
        m = parse(src)
        guard = m.symbols[0].candidates[0].guard
        self.assertIsInstance(guard, Call)
        self.assertEqual(guard.fn, "and")
        self.assertEqual(len(guard.args), 2)

    def test_multi_when_with_cost_dispatch(self) -> None:
        """Multi-when interacts correctly with cost-based dispatch."""
        src = """
module test

def route
  intent "route by multiple conditions"
  sig    (x: Int, y: Int) -> String
  effects {}
  cand
    intent "both positive and x > y"
    cost 1
    when gt(x, 0)
    when gt(y, 0)
    when gt(x, y)
    "x wins"
  cand
    intent "both positive and y >= x"
    cost 2
    when gt(x, 0)
    when gt(y, 0)
    "y wins or tie"
  cand
    intent "fallback"
    cost 100
    "invalid"
"""
        m = parse(src)
        self.assertEqual(run(m, "route", args=[5, 3]), "x wins")
        self.assertEqual(run(m, "route", args=[3, 5]), "y wins or tie")
        self.assertEqual(run(m, "route", args=[3, 3]), "y wins or tie")
        self.assertEqual(run(m, "route", args=[-1, 5]), "invalid")

    def test_first_when_false_short_circuits(self) -> None:
        """If the first when is false, the candidate is not selected."""
        src = """
module test

def f
  intent "test"
  sig    (x: Int) -> String
  effects {}
  cand
    intent "guarded"
    when gt(x, 100)
    when lt(x, 0)
    "impossible"
  cand
    intent "fallback"
    "fallback"
"""
        m = parse(src)
        # No value satisfies both gt(x, 100) AND lt(x, 0)
        self.assertEqual(run(m, "f", args=[50]), "fallback")
        self.assertEqual(run(m, "f", args=[200]), "fallback")


class MultiWhenBindBeforeWhenDetection(unittest.TestCase):
    """bind-before-when detection still works with multiple when clauses."""

    def test_bind_before_first_when_raises(self) -> None:
        src = """
module test

def f
  intent "test"
  sig    (x: Int) -> String
  effects {}
  cand
    y <- add(x, 1)
    when gt(y, 0)
    "yes"
"""
        with self.assertRaises(ParseError) as ctx:
            parse(src)
        self.assertIn("bind-before-when", str(ctx.exception))

    def test_bind_before_second_when_raises(self) -> None:
        src = """
module test

def f
  intent "test"
  sig    (x: Int) -> String
  effects {}
  cand
    when gt(x, 0)
    y <- add(x, 1)
    when lt(y, 10)
    "yes"
"""
        with self.assertRaises(ParseError) as ctx:
            parse(src)
        self.assertIn("bind-before-when", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
