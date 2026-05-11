"""End-to-end runtime tests.

Each test runs a full Codifide program and asserts on the result and, where
relevant, the error it provokes. These are the regression tests for the v0
semantics.
"""
from __future__ import annotations

import unittest

from codifide import parse, run
from codifide.runtime.errors import (
    BottomPropagationError,
    ContractViolation,
    DispatchError,
    EffectViolation,
    PrimitiveError,
    RecursionLimitError,
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
        src = (Path(__file__).resolve().parent.parent / "examples" / "sort.cod").read_text()
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

    def test_transitive_effect_subset_is_enforced(self) -> None:
        # P0-1 from the 2026-05-10 security audit. A pure caller must not
        # be able to launder effects through an impure callee — that would
        # invalidate the language's central soundness claim that declared
        # effects bound actual effects.
        src = """
def launder
  intent "claims pure but calls an impure callee"
  sig    () -> String
  effects {}
  cand
    impure()

def impure
  intent "actually does I/O"
  sig    () -> String
  effects {io.stdout}
  cand
    io.say("pwned")
"""
        with self.assertRaises(EffectViolation) as cm:
            run(parse(src), "launder")
        self.assertEqual(cm.exception.fn, "launder")
        self.assertEqual(cm.exception.observed, "io.stdout")

    def test_transitive_effect_check_allows_matching_effects(self) -> None:
        # The mirror test: if the caller declares what the callee needs,
        # the call is allowed.
        src = """
def outer
  intent "declares everything it needs transitively"
  sig    () -> String
  effects {io.stdout}
  cand
    inner()

def inner
  intent "uses I/O and says so"
  sig    () -> String
  effects {io.stdout}
  cand
    io.say("legit")
"""
        run(parse(src), "outer")

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
        src = (Path(__file__).resolve().parent.parent / "examples" / "classify.cod").read_text()
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

    # -- Security audit regressions (2026-05-10) --------------------------

    def test_P1_1_div_by_zero_surfaces_as_primitive_error(self) -> None:
        src = """
def boom
  intent "div by zero"
  sig    () -> Int
  effects {}
  cand
    div(1, 0)
"""
        with self.assertRaises(PrimitiveError) as cm:
            run(parse(src), "boom")
        self.assertEqual(cm.exception.fn, "div")

    def test_P1_1_bottom_into_arithmetic_is_typed(self) -> None:
        src = """
def boom
  intent "bottom into arithmetic"
  sig    () -> Int
  effects {}
  cand
    add(1, bottom)
"""
        with self.assertRaises(BottomPropagationError):
            run(parse(src), "boom")

    def test_P1_2_recursion_limit_is_enforced(self) -> None:
        # Generate a 500-deep call chain; default interpreter depth is 64
        # so this must trip with a typed Codifide error (not Python's
        # RecursionError) well before it reaches the bottom.
        parts = []
        for i in range(500):
            nxt = f"f{i+1}()" if i < 499 else "1"
            parts.append(
                f"\ndef f{i}\n  intent \"chain\"\n  sig () -> Int\n"
                f"  effects {{}}\n  cand\n    {nxt}\n"
            )
        with self.assertRaises(RecursionLimitError):
            run(parse("".join(parts)), "f0")

    def test_P2_1_contracts_are_pure(self) -> None:
        # Postconditions must not be able to perform effects, even when
        # the surrounding signature declares them. Contracts describe
        # state; they do not modify it.
        src = """
def post_has_effect
  intent "post tries to do I/O"
  sig    () -> String
  effects {io.stdout}
  post   contains(result, io.say("x"))
  cand
    "ok"
"""
        with self.assertRaises(EffectViolation):
            run(parse(src), "post_has_effect")

    def test_error_message_walks_the_intent_graph(self) -> None:
        # Roadmap v0.1 item. Errors should make the call path visible,
        # annotated with each frame's intent, so the reader knows why
        # the failing call happened rather than only what failed. Three
        # levels deep; the innermost raises, and the message must
        # mention each ancestor by name and intent.
        src = """
def outer
  intent "top-level orchestrator"
  sig    () -> Int
  effects {}
  cand
    middle()

def middle
  intent "delegates to inner"
  sig    () -> Int
  effects {}
  cand
    inner()

def inner
  intent "asserts a false postcondition"
  sig    () -> Int
  effects {}
  post   lt(result, 0)
  cand
    42
"""
        with self.assertRaises(ContractViolation) as cm:
            run(parse(src), "outer")
        msg = str(cm.exception)
        # The chain renders innermost-out, each frame annotated with
        # its intent. We verify all three names and all three intents
        # appear — rendering is not brittle-matched but content is.
        self.assertIn("outer", msg)
        self.assertIn("top-level orchestrator", msg)
        self.assertIn("middle", msg)
        self.assertIn("delegates to inner", msg)
        self.assertIn("inner", msg)
        self.assertIn("asserts a false postcondition", msg)
        # And the chain header is present so callers know this is the
        # intent-graph section.
        self.assertIn("called from", msg)


if __name__ == "__main__":
    unittest.main()
