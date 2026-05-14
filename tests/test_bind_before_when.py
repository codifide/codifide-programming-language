"""REQ-V2-2: Static bind-before-when detection in the parser.

The parser must raise ParseError (not a runtime error) when a `when` guard
appears after a bind (`<-`) in the same candidate body. Guards execute before
the body; bound names do not exist yet when the guard runs.

These tests verify:
1. The error is raised at parse time, not runtime.
2. The error message names the bound variable and the fix.
3. Correct programs (bind after guard, or no guard) are unaffected.
4. Multiple binds before a guard are all reported.
"""
from __future__ import annotations

import unittest

from codifide import parse
from codifide.runtime.errors import ParseError


class BindBeforeWhenDetectionTests(unittest.TestCase):
    """Parser raises ParseError for bind-before-when patterns."""

    def test_single_bind_before_when_raises_parse_error(self) -> None:
        """The canonical footgun: bind then when."""
        src = """\
def classify
  intent "classify after binding"
  sig    (msg: String) -> String
  effects {}
  cand
    label <- moderate(msg)
    when   eq(label, "unsafe")
    "blocked"
"""
        with self.assertRaises(ParseError) as ctx:
            parse(src)
        err = str(ctx.exception)
        self.assertIn("bind-before-when", err)
        self.assertIn("label", err)
        self.assertIn("when", err)
        self.assertIn("if/then/else", err)

    def test_error_message_names_the_fix(self) -> None:
        """Error message must mention if/then/else as the fix."""
        src = """\
def route
  intent "route after binding"
  sig    (msg: String) -> String
  effects {}
  cand
    result <- classify(msg)
    when   eq(result, "safe")
    "approved"
"""
        with self.assertRaises(ParseError) as ctx:
            parse(src)
        err = str(ctx.exception)
        self.assertIn("if/then/else", err)

    def test_error_is_parse_error_not_runtime(self) -> None:
        """The error must be ParseError, not a runtime DispatchError or similar."""
        src = """\
def bad
  intent "bad pattern"
  sig    (x: String) -> String
  effects {}
  cand
    y <- f(x)
    when eq(y, "a")
    y
"""
        # Must raise ParseError at parse time.
        with self.assertRaises(ParseError):
            parse(src)

    def test_multiple_binds_before_when(self) -> None:
        """Multiple binds before a when guard — all should be mentioned."""
        src = """\
def multi
  intent "multiple binds before when"
  sig    (x: String) -> String
  effects {}
  cand
    a <- f(x)
    b <- g(x)
    when eq(a, b)
    a
"""
        with self.assertRaises(ParseError) as ctx:
            parse(src)
        err = str(ctx.exception)
        self.assertIn("bind-before-when", err)
        # Both bound names should appear in the error.
        self.assertIn("a", err)
        self.assertIn("b", err)

    def test_correct_pattern_no_bind_before_when(self) -> None:
        """when guard with no preceding bind — should parse fine."""
        src = """\
def classify
  intent "classify with guard only"
  sig    (msg: String) -> String
  effects {}
  cand
    intent "unsafe"
    when   contains(lower(msg), "spam")
    "blocked"
  cand
    intent "fallback"
    "ok"
"""
        module = parse(src)
        self.assertEqual(len(module.symbols), 1)
        self.assertEqual(module.symbols[0].name, "classify")

    def test_bind_after_guard_is_fine(self) -> None:
        """Bind in the body after a when guard — correct pattern, must parse."""
        src = """\
def route
  intent "route with guard then bind"
  sig    (msg: String) -> String
  effects {}
  cand
    intent "process safe messages"
    when   contains(lower(msg), "approved")
    result <- process(msg)
    result
  cand
    intent "fallback"
    "blocked"
"""
        module = parse(src)
        self.assertEqual(len(module.symbols), 1)

    def test_no_guard_with_bind_is_fine(self) -> None:
        """Bind with no when guard — correct pattern, must parse."""
        src = """\
def moderate
  intent "moderate a message"
  sig    (msg: String) -> String
  effects {}
  cand
    result <- classify(msg)
    believe result
      ge(conf(result), 0.70) => result
      else                   => bottom
"""
        module = parse(src)
        self.assertEqual(len(module.symbols), 1)

    def test_bind_in_different_candidate_is_fine(self) -> None:
        """Bind in one candidate, when guard in another — no cross-candidate scope."""
        src = """\
def dispatch
  intent "dispatch with multiple candidates"
  sig    (msg: String) -> String
  effects {}
  cand
    intent "guarded path"
    when   contains(lower(msg), "spam")
    "blocked"
  cand
    intent "bind path"
    result <- classify(msg)
    result
"""
        module = parse(src)
        self.assertEqual(len(module.symbols), 1)
        self.assertEqual(len(module.symbols[0].candidates), 2)

    def test_error_line_number_points_to_when(self) -> None:
        """ParseError line number should point to the when line."""
        src = """\
def bad
  intent "bad"
  sig    (x: String) -> String
  effects {}
  cand
    y <- f(x)
    when eq(y, "a")
    y
"""
        with self.assertRaises(ParseError) as ctx:
            parse(src)
        # Line 7 is the `when` line (1-indexed).
        self.assertEqual(ctx.exception.line, 7)

    def test_claude_case_study_footgun(self) -> None:
        """Exact pattern Claude hit in T1-4 — must now be a ParseError."""
        src = """\
def moderate
  intent "moderate with bind-before-when"
  sig    (message: String) -> Label
  effects {}
  cand
    label <- classify_content(message)
    when   eq(label, "unsafe")
    "blocked"
"""
        with self.assertRaises(ParseError) as ctx:
            parse(src)
        err = str(ctx.exception)
        self.assertIn("bind-before-when", err)
        self.assertIn("label", err)


class BindBeforeWhenFixedPatternTests(unittest.TestCase):
    """The correct patterns that replace bind-before-when all parse cleanly."""

    def test_if_then_else_routing(self) -> None:
        """The recommended fix: bind in body, if/then/else to route."""
        src = """\
def route
  intent "route using if/then/else"
  sig    (message: String) -> Decision
  effects {}
  cand
    label <- moderate(message)
    if eq(label, "unsafe") then "blocked"
    else if eq(label, "safe") then "approved"
    else "escalate-to-human"
"""
        module = parse(src)
        self.assertEqual(len(module.symbols), 1)

    def test_multi_cand_with_when_guards_no_binds(self) -> None:
        """Multiple candidates each with when guards but no binds — fine."""
        src = """\
def classify
  intent "classify by keyword"
  sig    (msg: String) -> Label
  effects {}
  cand
    intent "unsafe"
    when   contains(lower(msg), "spam")
    belief("unsafe", 0.90)
  cand
    intent "safe"
    when   contains(lower(msg), "approved")
    belief("safe", 0.90)
  cand
    intent "uncertain"
    belief("uncertain", 0.75)
"""
        module = parse(src)
        self.assertEqual(len(module.symbols[0].candidates), 3)


if __name__ == "__main__":
    unittest.main()
