"""End-to-end runtime tests.

Each test runs a full Noema program and asserts on the result and, where
relevant, the error it provokes. These are the regression tests for the v0
semantics.
"""
from __future__ import annotations

import unittest

from noema import parse, run
from noema.runtime.errors import (
    ContractViolation,
    DispatchError,
    EffectViolation,
    RefusalError,
)


class RuntimeTests(unittest.TestCase):
    # -- Pure evaluation ---------------------------------------------------

    def test_pure_expression_evaluation(self) -> None:
        src = """
def answer
  intent "compute 42"
  sig    () -> Int
  effects {}
  cand
    add(40, 2)
"""
        self.assertEqual(run(parse(src), "answer"), 42)

    def test_sort_example_end_to_end(self) -> None:
        # Loads the real example file so we also exercise the file layout.
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "examples" / "sort.nm").read_text()
        result = run(parse(src), "main")
        self.assertEqual(result, [1, 1, 2, 3, 3, 4, 5, 5, 6, 9])

    # -- Effect enforcement -----------------------------------------------

    def test_undeclared_effect_is_rejected(self) -> None:
        src = """
def sneaky
  intent "phones home without declaring it"
  sig    () -> String
  effects {}
  cand
    io.say("oops")
"""
        with self.assertRaises(EffectViolation) as cm:
            run(parse(src), "sneaky")
        self.assertEqual(cm.exception.observed, "io.stdout")

    def test_declared_effect_is_allowed(self) -> None:
        src = """
def honest
  intent "declares what it does"
  sig    () -> String
  effects {io.stdout}
  cand
    io.say("hello")
"""
        # Should run without raising; we just assert it completes.
        run(parse(src), "honest")

    # -- Contract checking ------------------------------------------------

    def test_precondition_failure(self) -> None:
        src = """
def nonempty
  intent "require a non-empty name"
  sig    (name: String) -> String
  effects {}
  pre    ne(name, "")
  cand
    name
"""
        with self.assertRaises(ContractViolation) as cm:
            run(parse(src), "nonempty", args=[""])
        self.assertEqual(cm.exception.kind, "pre")

    def test_postcondition_failure_is_reported_against_promiser(self) -> None:
        src = """
def liar
  intent "promises a name in output but does not deliver"
  sig    (name: String) -> String
  effects {}
  post   contains(result, name)
  cand
    "something else"
"""
        with self.assertRaises(ContractViolation) as cm:
            run(parse(src), "liar", args=["Ada"])
        self.assertEqual(cm.exception.kind, "post")
        self.assertEqual(cm.exception.fn, "liar")

    # -- Belief dispatch and refusal --------------------------------------

    def test_belief_dispatch_picks_high_confidence_arm(self) -> None:
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "examples" / "classify.nm").read_text()
        result = run(parse(src), "main")
        self.assertEqual(result, "cat")

    def test_belief_dispatch_refuses_below_threshold(self) -> None:
        src = """
def classify
  intent "refuse rather than guess"
  sig    (img: Image) -> Label
  effects {model.vision}
  cand
    label <- vision.classify(img)
    believe label
      ge(conf(label), 0.9) => label
      else                 => bottom

def main
  intent "low-confidence path"
  sig    () -> Label
  effects {model.vision}
  cand
    classify(low_conf_image())

def low_conf_image
  intent "deliberately low confidence"
  sig    () -> Image
  effects {}
  cand
    host_image("maybe-cat", 0.3)
"""
        # Low confidence -> ⊥ escapes to `main`, whose top-level call raises.
        with self.assertRaises(RefusalError):
            run(parse(src), "main")

    # -- Dispatch ---------------------------------------------------------

    def test_candidate_guards_are_tried_in_order(self) -> None:
        src = """
def classify_size
  intent "pick tiny vs default by size"
  sig    (n: Int) -> String
  effects {}
  cand
    intent "tiny"
    when   lt(n, 10)
    "tiny"
  cand
    intent "default"
    "default"
"""
        m = parse(src)
        self.assertEqual(run(m, "classify_size", args=[5]), "tiny")
        self.assertEqual(run(m, "classify_size", args=[100]), "default")

    def test_dispatch_error_when_no_guard_matches(self) -> None:
        src = """
def strict
  intent "no default candidate"
  sig    (n: Int) -> String
  effects {}
  cand
    when   lt(n, 0)
    "negative"
"""
        with self.assertRaises(DispatchError):
            run(parse(src), "strict", args=[1])


if __name__ == "__main__":
    unittest.main()
