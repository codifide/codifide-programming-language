"""Tests for the surface parser.

These tests pin down the invariants that define the language surface:
    - Intent is mandatory.
    - Signature and effects parse correctly.
    - Candidate dispatch structure is preserved.
    - Bind and believe blocks nest as expected.
"""
from __future__ import annotations

import unittest

from noema import parse
from noema.core.types import Believe, Bind, Call, Concat, Lit
from noema.runtime.errors import ParseError


class ParserTests(unittest.TestCase):
    def test_minimal_definition(self) -> None:
        src = """
def noop
  intent "nothing interesting"
  sig    () -> Unit
  effects {}
  cand
    1
"""
        m = parse(src)
        self.assertEqual(len(m.symbols), 1)
        d = m.symbols[0]
        self.assertEqual(d.name, "noop")
        self.assertEqual(d.intent, "nothing interesting")
        self.assertEqual(d.signature.returns, "Unit")
        self.assertEqual(d.signature.effects, frozenset())
        self.assertEqual(len(d.candidates), 1)

    def test_missing_intent_is_rejected(self) -> None:
        # The single most important invariant of the language. Losing it
        # would defeat the point of Noema.
        src = """
def bad
  sig    () -> Int
  effects {}
  cand
    1
"""
        with self.assertRaises(ParseError) as cm:
            parse(src)
        self.assertIn("intent", str(cm.exception).lower())

    def test_missing_candidate_is_rejected(self) -> None:
        src = """
def bad
  intent "no body"
  sig    () -> Int
  effects {}
"""
        with self.assertRaises(ParseError):
            parse(src)

    def test_effect_set_parses(self) -> None:
        src = """
def hello
  intent "greet"
  sig    () -> String
  effects {io.stdout, clock.read}
  cand
    "hi"
"""
        m = parse(src)
        self.assertEqual(
            m.symbols[0].signature.effects,
            frozenset({"io.stdout", "clock.read"}),
        )

    def test_bind_and_concat_compose(self) -> None:
        src = """
def greeting
  intent "build greeting"
  sig    (name: String) -> String
  effects {}
  cand
    prefix <- "Hello, "
    prefix ++ name
"""
        m = parse(src)
        body = m.symbols[0].candidates[0].body
        # Bind should wrap the concat as its body.
        self.assertIsInstance(body, Bind)
        self.assertEqual(body.name, "prefix")
        self.assertIsInstance(body.body, Concat)

    def test_believe_block(self) -> None:
        src = """
def judge
  intent "demo believe"
  sig    (x: Any) -> Any
  effects {}
  cand
    believe x
      ge(conf(x), 0.9) => x
      else             => bottom
"""
        m = parse(src)
        body = m.symbols[0].candidates[0].body
        self.assertIsInstance(body, Believe)
        self.assertEqual(len(body.arms), 1)

    def test_believe_must_have_else(self) -> None:
        src = """
def judge
  intent "demo believe"
  sig    (x: Any) -> Any
  effects {}
  cand
    believe x
      ge(conf(x), 0.9) => x
"""
        with self.assertRaises(ParseError):
            parse(src)


if __name__ == "__main__":
    unittest.main()
