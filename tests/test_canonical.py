"""Round-trip tests for the canonical JSON projection.

Canonical form is the truth. Surface text is a projection. Therefore:
    parse → to_canonical → from_canonical must preserve the Module structurally.
"""
from __future__ import annotations

import json
import unittest

from noema import parse
from noema.projection.canonical import from_canonical, to_canonical


class CanonicalRoundTripTests(unittest.TestCase):
    SOURCES = [
        # Minimal definition.
        """
def noop
  intent "nothing"
  sig    () -> Unit
  effects {}
  cand
    1
""",
        # With bind, concat, pre/post.
        """
def greet
  intent "greet"
  sig    (name: String) -> String
  effects {}
  pre    ne(name, "")
  post   contains(result, name)
  cand
    prefix <- "Hello, "
    prefix ++ name
""",
        # With believe and bottom.
        """
def judge
  intent "dispatch on confidence"
  sig    (x: Any) -> Any
  effects {}
  cand
    believe x
      ge(conf(x), 0.9) => x
      else             => bottom
""",
    ]

    def test_round_trip_equality(self) -> None:
        for src in self.SOURCES:
            with self.subTest(src=src.strip().splitlines()[1]):
                module_a = parse(src)
                json_a = to_canonical(module_a)

                # Round-trip through a JSON string so we exercise the real
                # serialization path, not just dict equality.
                serialized = json.dumps(json_a, sort_keys=True)
                json_b = json.loads(serialized)

                module_b = from_canonical(json_b)
                json_b_again = to_canonical(module_b)

                self.assertEqual(
                    json.dumps(json_a, sort_keys=True),
                    json.dumps(json_b_again, sort_keys=True),
                )

    def test_canonical_has_intent_preserved(self) -> None:
        m = parse(self.SOURCES[1])
        obj = to_canonical(m)
        self.assertEqual(obj["symbols"]["greet"]["intent"], "greet")

    def test_nested_believe_round_trips_through_canonical_form(self) -> None:
        # Security audit unknown from the original v0 dispatch: does
        # believe-in-believe nesting round-trip through canonical form?
        # The *surface parser* does not yet accept multi-line values in
        # believe arms, so we build this form directly and verify the
        # canonical JSON layer preserves the structure.
        from noema.core.types import (
            Believe, BottomExpr, Call, Candidate, Definition,
            Lit, Module, Ref, Signature,
        )
        inner = Believe(
            subject=Ref("y"),
            arms=((
                Call("ge", (Call("conf", (Ref("y"),)), Lit(0.9, type="Float"))),
                Ref("y"),
            ),),
            otherwise=BottomExpr(),
        )
        outer = Believe(
            subject=Ref("x"),
            arms=((
                Call("ge", (Call("conf", (Ref("x"),)), Lit(0.9, type="Float"))),
                inner,
            ),),
            otherwise=BottomExpr(),
        )
        m = Module(
            name="nested",
            symbols=(
                Definition(
                    name="deep",
                    intent="nested believe",
                    signature=Signature(returns="Any"),
                    candidates=(Candidate(body=outer),),
                ),
            ),
        )
        json_a = to_canonical(m)
        m2 = from_canonical(json.loads(json.dumps(json_a, sort_keys=True)))
        json_b = to_canonical(m2)
        self.assertEqual(
            json.dumps(json_a, sort_keys=True),
            json.dumps(json_b, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
