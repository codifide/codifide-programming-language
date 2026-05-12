"""Inline conditional expression: ``if cond then a else b``.

Spec amendment landed 2026-05-11. Short-circuit evaluation —
exactly one branch evaluates per call. Pins the contract.
"""
from __future__ import annotations

import unittest

from codifide import parse
from codifide.core.types import If, Module
from codifide.projection.canonical import from_canonical, to_canonical
from codifide.runtime.errors import PrimitiveError
from codifide.runtime.interpreter import run


def _run(src: str, entry: str = "f", args=None):
    return run(parse(src), entry=entry, args=args or [])


class BasicIfSemantics(unittest.TestCase):

    def test_if_true_branch_taken(self) -> None:
        src = """
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    if true then 1 else 2
"""
        self.assertEqual(_run(src), 1)

    def test_if_false_branch_taken(self) -> None:
        src = """
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    if false then 1 else 2
"""
        self.assertEqual(_run(src), 2)

    def test_if_with_computed_condition(self) -> None:
        src = """
def f
  intent "absolute value via if"
  sig (n: Int) -> Int
  effects {}
  cand
    if lt(n, 0) then neg(n) else n
"""
        self.assertEqual(_run(src, args=[-5]), 5)
        self.assertEqual(_run(src, args=[7]), 7)

    def test_if_nested(self) -> None:
        src = """
def f
  intent "sign"
  sig (n: Int) -> Int
  effects {}
  cand
    if lt(n, 0) then neg(1) else if eq(n, 0) then 0 else 1
"""
        self.assertEqual(_run(src, args=[-3]), -1)
        self.assertEqual(_run(src, args=[0]), 0)
        self.assertEqual(_run(src, args=[5]), 1)

    def test_if_used_as_call_argument(self) -> None:
        src = """
def f
  intent "if inside a call"
  sig (n: Int) -> Int
  effects {}
  cand
    add(1, if gt(n, 0) then n else neg(n))
"""
        self.assertEqual(_run(src, args=[5]), 6)
        self.assertEqual(_run(src, args=[-5]), 6)


class ShortCircuitSemantics(unittest.TestCase):
    """The un-taken branch must not evaluate.

    This is the reason `If` exists alongside candidate dispatch:
    guards don't short-circuit across candidates, but `If` does.
    """

    def test_else_branch_not_evaluated_when_cond_true(self) -> None:
        # Else branch would raise (index past end). If the
        # dispatcher evaluated both branches it would propagate
        # the error; `If`'s short-circuit semantics means it
        # doesn't.
        src = """
def safe
  intent "gate index by length"
  sig (s: String) -> String
  effects {}
  cand
    if gt(len(s), 0) then char_at(s, 0) else ""
"""
        self.assertEqual(_run(src, entry="safe", args=["hello"]), "h")
        self.assertEqual(_run(src, entry="safe", args=[""]), "")

    def test_then_branch_not_evaluated_when_cond_false(self) -> None:
        src = """
def safe
  intent "gate division by denominator"
  sig (a: Int, b: Int) -> Int
  effects {}
  cand
    if eq(b, 0) then 0 else div(a, b)
"""
        self.assertEqual(_run(src, entry="safe", args=[10, 0]), 0)
        self.assertEqual(_run(src, entry="safe", args=[10, 2]), 5)


class ParserSurfaceTests(unittest.TestCase):

    def test_identifier_containing_if_is_not_mistaken_for_keyword(self) -> None:
        src = """
def f
  intent "t"
  sig (if_flag: Bool) -> Int
  effects {}
  cand
    if if_flag then 1 else 2
"""
        self.assertEqual(_run(src, args=[True]), 1)

    def test_missing_then_raises_parse_error(self) -> None:
        from codifide.runtime.errors import ParseError
        src = """
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    if true 1 else 2
"""
        with self.assertRaises(ParseError) as cm:
            parse(src)
        self.assertIn("then", str(cm.exception))

    def test_missing_else_raises_parse_error(self) -> None:
        from codifide.runtime.errors import ParseError
        src = """
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    if true then 1
"""
        with self.assertRaises(ParseError) as cm:
            parse(src)
        self.assertIn("else", str(cm.exception))


class CanonicalRoundTrip(unittest.TestCase):

    def test_if_round_trips_through_canonical(self) -> None:
        src = """
def f
  intent "t"
  sig (n: Int) -> Int
  effects {}
  cand
    if lt(n, 0) then neg(n) else n
"""
        m = parse(src)
        obj = to_canonical(m)
        m2 = from_canonical(obj)
        self.assertEqual(
            run(m, entry="f", args=[-5]),
            run(m2, entry="f", args=[-5]),
        )

    def test_if_appears_in_canonical_with_correct_keys(self) -> None:
        src = """
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    if true then 1 else 2
"""
        obj = to_canonical(parse(src))
        body = obj["symbols"]["f"]["candidates"][0]["body"]
        self.assertEqual(body["kind"], "if")
        self.assertIn("cond", body)
        self.assertIn("then", body)
        self.assertIn("else", body)


class PureContextTests(unittest.TestCase):
    """If in a pure context (post, pre, guard) stays pure."""

    def test_if_in_postcondition(self) -> None:
        src = """
def abs_n
  intent "absolute value with if in post"
  sig (n: Int) -> Int
  effects {}
  post   eq(result, if lt(n, 0) then neg(n) else n)
  cand
    if lt(n, 0) then neg(n) else n
"""
        self.assertEqual(_run(src, entry="abs_n", args=[-7]), 7)

    def test_if_effectful_branch_in_pure_context_rejected(self) -> None:
        # A body in an effects={} function can't call io.say —
        # static transitive check catches it regardless of whether
        # it's inside an If.
        from codifide.runtime.errors import EffectViolation
        src = """
def f
  intent "try to hide io in an if"
  sig () -> String
  effects {}
  cand
    if true then io.say("hi") else "ok"
"""
        # This should be rejected at module-load time because io.say
        # is not in the declared effect set. The If node participates
        # in the transitive walk uniformly.
        with self.assertRaises(EffectViolation):
            _run(src)


if __name__ == "__main__":
    unittest.main()



class MultiLineIfTests(unittest.TestCase):
    """Multi-line ``if ... then ... else`` expressions must parse.

    The parser's continuation logic tracks unmatched ``if``/``then``/
    ``else`` keyword counts and pulls subsequent lines until the
    expression is complete. Regression for the 2026-05-11 issue
    where ``else`` was in the stop-heads set and broke continuation.
    """

    def test_if_then_else_each_on_own_line(self) -> None:
        src = """
def f
  intent "t"
  sig (n: Int) -> Int
  effects {}
  cand
    if lt(n, 0)
      then neg(n)
      else n
"""
        self.assertEqual(_run(src, args=[-5]), 5)
        self.assertEqual(_run(src, args=[5]), 5)

    def test_nested_multiline_if(self) -> None:
        src = """
def f
  intent "sign"
  sig (n: Int) -> Int
  effects {}
  cand
    if lt(n, 0)
      then neg(1)
      else if eq(n, 0)
        then 0
        else 1
"""
        self.assertEqual(_run(src, args=[-3]), -1)
        self.assertEqual(_run(src, args=[0]), 0)
        self.assertEqual(_run(src, args=[3]), 1)

    def test_believe_else_not_broken_by_multiline_if_support(self) -> None:
        # Ensure believe block's `else =>` arm still parses correctly
        # now that `else` is no longer a stop-head.
        src = """
def f
  intent "t"
  sig (n: Int) -> String
  effects {}
  cand
    believe n
      eq(it, 0) => "zero"
      else      => "nonzero"
"""
        self.assertEqual(_run(src, args=[0]), "zero")
        self.assertEqual(_run(src, args=[5]), "nonzero")
