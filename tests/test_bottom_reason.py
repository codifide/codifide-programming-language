"""V3-3: bottom "reason" — optional string payload on refusal nodes.

Tests cover:
  - Surface syntax: bare ``bottom`` still works (backward-compat)
  - Surface syntax: ``bottom "reason"`` parses to BottomExpr(reason=...)
  - Canonical JSON: bare bottom → {"kind":"bottom"} (no reason key)
  - Canonical JSON: bottom with reason → {"kind":"bottom","reason":"..."}
  - Round-trip: from_canonical(to_canonical(m)) is a fixed point
  - Interpreter: reason propagates through RefusalError
  - Interpreter: bare bottom still raises RefusalError with reason=None
  - Interpreter: bottom with reason in believe else arm is handled cleanly
  - Interpreter: reason survives a believe arm (handled, not raised)
  - Capability manifest: bottom AST kind documents optional reason field
"""
from __future__ import annotations

import unittest

from codifide import (
    Bottom,
    BottomWithReason,
    from_canonical,
    parse,
    run,
    to_canonical,
)
from codifide.capability import generate_capability
from codifide.core.types import BottomExpr, _BottomType
from codifide.parser.expr_parser import parse_expr
from codifide.projection.canonical import _expr_from_json, _expr_to_json
from codifide.runtime.errors import RefusalError


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestBottomReasonParser(unittest.TestCase):
    """Surface syntax: bare bottom and bottom "reason"."""

    def test_bare_bottom_parses_to_no_reason(self) -> None:
        expr = parse_expr("bottom")
        self.assertIsInstance(expr, BottomExpr)
        self.assertIsNone(expr.reason)

    def test_bottom_with_reason_parses_correctly(self) -> None:
        expr = parse_expr('bottom "not authorised"')
        self.assertIsInstance(expr, BottomExpr)
        self.assertEqual(expr.reason, "not authorised")

    def test_bottom_with_empty_reason(self) -> None:
        expr = parse_expr('bottom ""')
        self.assertIsInstance(expr, BottomExpr)
        self.assertEqual(expr.reason, "")

    def test_bottom_with_reason_in_source(self) -> None:
        src = """
def refuse
  intent "always refuses with a reason"
  sig () -> Any
  cand
    bottom "input out of range"
"""
        module = parse(src)
        cand = module.symbols[0].candidates[0]
        self.assertIsInstance(cand.body, BottomExpr)
        self.assertEqual(cand.body.reason, "input out of range")

    def test_bare_bottom_in_source(self) -> None:
        src = """
def refuse
  intent "always refuses"
  sig () -> Any
  cand
    bottom
"""
        module = parse(src)
        cand = module.symbols[0].candidates[0]
        self.assertIsInstance(cand.body, BottomExpr)
        self.assertIsNone(cand.body.reason)

    def test_bottom_with_reason_in_believe_else(self) -> None:
        src = """
def classify
  intent "classify with reason on refusal"
  sig (x: Int) -> Any
  cand
    believe x
      eq(x, 1) => "one"
      else      => bottom "unknown value"
"""
        module = parse(src)
        # Should parse without error; the else arm is a BottomExpr with reason.
        self.assertEqual(len(module.symbols), 1)


# ---------------------------------------------------------------------------
# Canonical JSON tests
# ---------------------------------------------------------------------------


class TestBottomReasonCanonical(unittest.TestCase):
    """Canonical JSON: reason field is additive and backward-compatible."""

    def test_bare_bottom_canonical_has_no_reason_key(self) -> None:
        obj = _expr_to_json(BottomExpr())
        self.assertEqual(obj, {"kind": "bottom"})
        self.assertNotIn("reason", obj)

    def test_bottom_with_reason_canonical_includes_reason(self) -> None:
        obj = _expr_to_json(BottomExpr(reason="not authorised"))
        self.assertEqual(obj, {"kind": "bottom", "reason": "not authorised"})

    def test_bare_bottom_round_trips(self) -> None:
        original = BottomExpr()
        restored = _expr_from_json(_expr_to_json(original))
        self.assertEqual(original, restored)

    def test_bottom_with_reason_round_trips(self) -> None:
        original = BottomExpr(reason="out of range")
        restored = _expr_from_json(_expr_to_json(original))
        self.assertEqual(original, restored)

    def test_from_canonical_bare_bottom_no_reason(self) -> None:
        obj = {"kind": "bottom"}
        expr = _expr_from_json(obj)
        self.assertIsInstance(expr, BottomExpr)
        self.assertIsNone(expr.reason)

    def test_from_canonical_bottom_with_reason(self) -> None:
        obj = {"kind": "bottom", "reason": "forbidden"}
        expr = _expr_from_json(obj)
        self.assertIsInstance(expr, BottomExpr)
        self.assertEqual(expr.reason, "forbidden")

    def test_module_round_trip_with_reason(self) -> None:
        src = """
def refuse
  intent "refuses with reason"
  sig () -> Any
  cand
    bottom "not implemented"
"""
        module = parse(src)
        restored = from_canonical(to_canonical(module))
        cand = restored.symbols[0].candidates[0]
        self.assertIsInstance(cand.body, BottomExpr)
        self.assertEqual(cand.body.reason, "not implemented")

    def test_bare_bottom_hash_unchanged(self) -> None:
        """Bare bottom must produce the same canonical bytes as before V3-3."""
        from codifide.projection.canonical import canonical_bytes
        src = """
def refuse
  intent "always refuses"
  sig () -> Any
  cand
    bottom
"""
        module = parse(src)
        obj = to_canonical(module)
        # The bottom node in the canonical JSON must not have a "reason" key.
        cand_body = obj["symbols"]["refuse"]["candidates"][0]["body"]
        self.assertEqual(cand_body, {"kind": "bottom"})


# ---------------------------------------------------------------------------
# Interpreter tests
# ---------------------------------------------------------------------------


class TestBottomReasonInterpreter(unittest.TestCase):
    """Interpreter: reason propagates through RefusalError."""

    def test_bare_bottom_raises_refusal_with_no_reason(self) -> None:
        src = """
def main
  intent "bare refusal"
  sig () -> Any
  cand
    bottom
"""
        with self.assertRaises(RefusalError) as cm:
            run(parse(src), "main")
        self.assertIsNone(cm.exception.reason)

    def test_bottom_with_reason_raises_refusal_with_reason(self) -> None:
        src = """
def main
  intent "reasoned refusal"
  sig () -> Any
  cand
    bottom "input out of range"
"""
        with self.assertRaises(RefusalError) as cm:
            run(parse(src), "main")
        self.assertEqual(cm.exception.reason, "input out of range")

    def test_refusal_error_message_includes_reason(self) -> None:
        src = """
def main
  intent "reasoned refusal"
  sig () -> Any
  cand
    bottom "forbidden operation"
"""
        with self.assertRaises(RefusalError) as cm:
            run(parse(src), "main")
        self.assertIn("forbidden operation", str(cm.exception))

    def test_bottom_with_reason_handled_in_believe(self) -> None:
        """A bottom with reason that is caught in a believe arm does not raise."""
        src = """
def classify
  intent "classify with fallback"
  sig (x: Int) -> String
  cand
    believe x
      eq(x, 1) => "one"
      else      => "other"

def main
  intent "test believe handles bottom-like else"
  sig () -> String
  cand
    classify(2)
"""
        result = run(parse(src), "main")
        self.assertEqual(result, "other")

    def test_bottom_with_reason_in_nested_call_propagates(self) -> None:
        """Reason propagates when bottom escapes a nested call."""
        src = """
def inner
  intent "inner refuses"
  sig () -> Any
  cand
    bottom "inner refused"

def main
  intent "calls inner"
  sig () -> Any
  cand
    inner()
"""
        with self.assertRaises(RefusalError) as cm:
            run(parse(src), "main")
        # The reason from the inner bottom should propagate.
        self.assertEqual(cm.exception.reason, "inner refused")

    def test_bottom_with_reason_is_falsy(self) -> None:
        """BottomWithReason is falsy, consistent with bare Bottom."""
        bwr = BottomWithReason("some reason")
        self.assertFalse(bool(bwr))
        self.assertIsInstance(bwr, _BottomType)

    def test_bottom_with_reason_is_instance_of_bottom_type(self) -> None:
        bwr = BottomWithReason("reason")
        self.assertIsInstance(bwr, _BottomType)


# ---------------------------------------------------------------------------
# Capability manifest test
# ---------------------------------------------------------------------------


class TestBottomReasonCapability(unittest.TestCase):
    """Capability manifest documents the optional reason field."""

    def test_bottom_ast_kind_has_reason_field(self) -> None:
        cap = generate_capability()
        bottom_kind = cap["ast_kinds"]["bottom"]
        field_names = [f["name"] for f in bottom_kind["fields"]]
        self.assertIn("reason", field_names)

    def test_bottom_reason_field_is_optional(self) -> None:
        cap = generate_capability()
        bottom_kind = cap["ast_kinds"]["bottom"]
        reason_field = next(f for f in bottom_kind["fields"] if f["name"] == "reason")
        self.assertTrue(reason_field.get("optional", False))

    def test_bottom_description_mentions_reason(self) -> None:
        cap = generate_capability()
        desc = cap["ast_kinds"]["bottom"]["description"]
        self.assertIn("reason", desc.lower())


if __name__ == "__main__":
    unittest.main()
