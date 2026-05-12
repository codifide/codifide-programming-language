"""Cost-based candidate dispatch (2026-05-11 spec amendment).

Pins the dispatcher rule specified in
``dispatches/2026-05-11-cost-based-dispatch-proposal.readout.md``.

Key invariants:
- Un-annotated modules dispatch in declaration order (v0 semantics).
- Any annotated candidate beats any un-annotated one when both
  satisfy their guards.
- Among annotated candidates, lower cost wins.
- Among equal-cost candidates, declaration index is the tiebreaker.
- Cost annotations do NOT affect the canonical form of an
  un-annotated candidate; the bytes and identity are unchanged.
- The canonical-form typing contract rejects non-integer or
  negative cost values.
"""
from __future__ import annotations

import unittest

from codifide import parse
from codifide.runtime.errors import ParseError
from codifide.runtime.interpreter import run


class UnannotatedDispatchIsUnchanged(unittest.TestCase):
    """Zero-cost-annotation programs behave exactly as they did pre-amendment."""

    def test_first_satisfied_candidate_wins_without_annotations(self) -> None:
        src = """
def f
  intent "unannotated"
  sig    () -> String
  effects {}
  cand
    intent "first"
    "first"
  cand
    intent "second"
    "second"
"""
        m = parse(src)
        self.assertEqual(run(m, entry="f"), "first")

    def test_canonical_bytes_unchanged_without_annotations(self) -> None:
        # Adding the cost amendment MUST NOT change the canonical bytes
        # of a program that does not use cost. If this ever breaks,
        # every existing content hash silently invalidates.
        from codifide.projection.canonical import canonical_bytes
        src = """
def g
  intent "two arms"
  sig    () -> Int
  effects {}
  cand
    when  eq(1, 1)
    1
  cand
    2
"""
        m = parse(src)
        bytes_ = canonical_bytes(m)
        # Spot-check: the candidate objects in the canonical form must
        # not include a ``cost`` key, because the amendment says cost is
        # emitted only when present.
        self.assertNotIn(b'"cost"', bytes_)


class CostBasedDispatchSemantics(unittest.TestCase):
    """The ``min((cost, index))`` rule."""

    def test_lower_cost_wins_over_higher_cost(self) -> None:
        src = """
def f
  intent "two costed"
  sig    () -> String
  effects {}
  cand
    intent "expensive"
    cost 100
    "expensive"
  cand
    intent "cheap"
    cost 10
    "cheap"
"""
        m = parse(src)
        self.assertEqual(run(m, entry="f"), "cheap")

    def test_declaration_index_breaks_equal_cost_ties(self) -> None:
        src = """
def f
  intent "equal costs"
  sig    () -> String
  effects {}
  cand
    intent "first"
    cost 5
    "first"
  cand
    intent "second"
    cost 5
    "second"
"""
        m = parse(src)
        self.assertEqual(run(m, entry="f"), "first")

    def test_annotated_candidate_beats_unannotated_when_both_satisfy(self) -> None:
        # This is the behavioral-drift notice in the proposal:
        # adding one cost annotation to a module changes the
        # dispatch semantics for the whole definition.
        src = """
def f
  intent "mixed"
  sig    () -> String
  effects {}
  cand
    intent "unannotated first"
    "from_unannotated"
  cand
    intent "annotated second"
    cost 100
    "from_annotated"
"""
        m = parse(src)
        # Pre-amendment this would return "from_unannotated" (first wins).
        # Post-amendment "from_annotated" wins because its cost 100 < ∞.
        self.assertEqual(run(m, entry="f"), "from_annotated")

    def test_unsatisfied_guarded_candidate_is_skipped(self) -> None:
        # The guard filter runs before the cost sort. A candidate
        # whose guard is false, however cheap, never wins.
        src = """
def f
  intent "guarded cheap, unguarded expensive"
  sig    () -> String
  effects {}
  cand
    intent "cheap but false"
    cost 1
    when  eq(1, 2)
    "unreachable"
  cand
    intent "expensive but reachable"
    cost 1000
    "reachable"
"""
        m = parse(src)
        self.assertEqual(run(m, entry="f"), "reachable")

    def test_zero_cost_is_accepted_and_wins(self) -> None:
        src = """
def f
  intent "zero cost is meaningful"
  sig    () -> String
  effects {}
  cand
    intent "free"
    cost 0
    "free"
  cand
    intent "paid"
    cost 1
    "paid"
"""
        m = parse(src)
        self.assertEqual(run(m, entry="f"), "free")


class CostSurfaceSyntaxValidation(unittest.TestCase):
    """The parser rejects invalid cost values with typed ``ParseError``."""

    def test_negative_cost_is_rejected(self) -> None:
        src = """
def f
  intent "bad"
  sig    () -> String
  effects {}
  cand
    cost -1
    "x"
"""
        with self.assertRaises(ParseError) as cm:
            parse(src)
        self.assertIn("non-negative", str(cm.exception))

    def test_float_cost_is_rejected(self) -> None:
        src = """
def f
  intent "bad"
  sig    () -> String
  effects {}
  cand
    cost 1.5
    "x"
"""
        with self.assertRaises(ParseError) as cm:
            parse(src)
        self.assertIn("integer", str(cm.exception).lower())

    def test_non_numeric_cost_is_rejected(self) -> None:
        src = """
def f
  intent "bad"
  sig    () -> String
  effects {}
  cand
    cost cheap
    "x"
"""
        with self.assertRaises(ParseError) as cm:
            parse(src)
        self.assertIn("integer", str(cm.exception).lower())

    def test_missing_cost_argument_is_rejected(self) -> None:
        src = """
def f
  intent "bad"
  sig    () -> String
  effects {}
  cand
    cost
    "x"
"""
        with self.assertRaises(ParseError):
            parse(src)


class CostCanonicalRoundTrip(unittest.TestCase):
    """Canonical form round-trips preserve the cost field."""

    def test_cost_survives_canonical_roundtrip(self) -> None:
        from codifide.projection.canonical import from_canonical, to_canonical
        src = """
def f
  intent "costed"
  sig    () -> String
  effects {}
  cand
    cost 42
    "x"
"""
        m = parse(src)
        self.assertEqual(m.symbols[0].candidates[0].cost, 42)
        round_tripped = from_canonical(to_canonical(m))
        self.assertEqual(round_tripped.symbols[0].candidates[0].cost, 42)

    def test_canonical_form_rejects_negative_cost(self) -> None:
        from codifide.projection.canonical import from_canonical
        malformed = {
            "codifide": "0.1",
            "module": "bad",
            "symbols": {
                "f": {
                    "kind": "definition",
                    "intent": "x",
                    "signature": {
                        "params": [], "returns": "String", "effects": [],
                    },
                    "pre": [],
                    "post": [],
                    "candidates": [{
                        "kind": "candidate",
                        "intent": "c",
                        "guard": None,
                        "body": {
                            "kind": "lit", "value": "x", "type": "String",
                            "conf": 1.0, "provenance": "literal",
                        },
                        "cost": -5,
                    }],
                }
            },
        }
        with self.assertRaises(ValueError):
            from_canonical(malformed)

    def test_canonical_form_rejects_float_cost(self) -> None:
        from codifide.projection.canonical import from_canonical
        malformed = {
            "codifide": "0.1",
            "module": "bad",
            "symbols": {
                "f": {
                    "kind": "definition",
                    "intent": "x",
                    "signature": {
                        "params": [], "returns": "String", "effects": [],
                    },
                    "pre": [],
                    "post": [],
                    "candidates": [{
                        "kind": "candidate",
                        "intent": "c",
                        "guard": None,
                        "body": {
                            "kind": "lit", "value": "x", "type": "String",
                            "conf": 1.0, "provenance": "literal",
                        },
                        "cost": 1.5,
                    }],
                }
            },
        }
        with self.assertRaises(ValueError):
            from_canonical(malformed)


if __name__ == "__main__":
    unittest.main()
