"""Tests for the surface parser.

These tests pin down the invariants that define the language surface:
    - Intent is mandatory.
    - Signature and effects parse correctly.
    - Candidate dispatch structure is preserved.
    - Bind and believe blocks nest as expected.
"""
from __future__ import annotations

import unittest

from codifide import parse
from codifide.core.types import Believe, Bind, Call, Concat, Lit
from codifide.runtime.errors import ParseError


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
        # would defeat the point of Codifide.
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

    def test_module_name_grammar_is_enforced(self) -> None:
        # Security audit P2-2. A module name must look like an identifier,
        # not arbitrary text — canonical form echoes it into displays and
        # arbitrary content creates ambiguity in downstream consumers.
        src = """module foo; bad stuff
def x
  intent "x"
  sig () -> Int
  effects {}
  cand
    1
"""
        with self.assertRaises(ParseError) as cm:
            parse(src)
        self.assertIn("module name", str(cm.exception).lower())

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


class MultiLineExpressionTests(unittest.TestCase):
    """Regression tests for the 2026-05-11 parser fix.

    An expression split across multiple physical lines while brackets
    are unbalanced must parse as a single expression. Previously this
    leaked ``AttributeError`` from the expression parser because the
    line-oriented outer parser handed each physical line to
    ``parse_expr`` independently, and a trailing open paren sent the
    inner parser off the end of its token stream.

    Both fixtures below are the exact programs Gemini 2.5 Pro wrote on
    2026-05-11 (see ``dispatches/2026-05-11-gemini-2-5-pro-programs-
    feedback.md``). They are checked in to prevent silent regression.
    """

    def test_multi_line_list_literal_in_main_parses(self) -> None:
        src = """
module palindrome_example

def is_palindrome
  intent "return true iff a list reads the same forwards and backwards"
  sig    (xs: List) -> Bool
  effects {}
  cand
    eq(xs, reverse(xs))

def main
  intent "check a known palindrome and a known non-palindrome"
  sig    () -> List
  effects {}
  cand
    list(
      is_palindrome(list(1, 2, 3, 2, 1)),
      is_palindrome(list(1, 2, 3, 4, 5))
    )
"""
        module = parse(src)
        self.assertEqual(len(module.symbols), 2)
        main = module.lookup("main")
        self.assertIsNotNone(main)
        # The whole multi-line call should parse as a single Call("list", ...)
        # with two arguments, not as three separate expression steps.
        body = main.candidates[0].body
        self.assertIsInstance(body, Call)
        self.assertEqual(body.fn, "list")
        self.assertEqual(len(body.args), 2)

    def test_multi_line_classify_numeric_parses_and_runs(self) -> None:
        src = """
module classify_numeric_example

def classify_number
  intent "return a label for a number based on its value"
  sig    (n: Number) -> String
  effects {}

  cand
    intent "handle low numbers"
    when   lt(n, 10)
    "low"

  cand
    intent "handle medium numbers"
    when   le(n, 100)
    "medium"

  cand
    intent "handle high numbers"
    "high"

def main
  intent "classify a set of known inputs"
  sig    () -> List
  effects {}
  cand
    list(
      classify_number(5),
      classify_number(50),
      classify_number(500)
    )
"""
        module = parse(src)
        from codifide.runtime.interpreter import run
        self.assertEqual(run(module), ["low", "medium", "high"])

    def test_multi_line_bind_rhs_parses(self) -> None:
        # The right-hand side of a bind may also span multiple lines.
        src = """
def demo
  intent "multi-line bind"
  sig    () -> List
  effects {}
  cand
    xs <- list(
      1,
      2,
      3
    )
    xs
"""
        module = parse(src)
        from codifide.runtime.interpreter import run
        self.assertEqual(run(module, entry="demo"), [1, 2, 3])

    def test_unbalanced_brackets_are_a_clean_parse_error(self) -> None:
        # Multi-line continuation stops at the next keyword head, so
        # leaving a bracket unclosed produces a ParseError rather than
        # an AttributeError or silently eating the next clause.
        src = """
def oops
  intent "unbalanced"
  sig    () -> List
  effects {}
  cand
    list(1, 2, 3
"""
        with self.assertRaises(ParseError) as cm:
            parse(src)
        self.assertIn("brackets", str(cm.exception).lower())

    def test_percent_operator_suggests_mod(self) -> None:
        # Regression for the ergonomics pass: the lexer's unexpected-
        # character error for '%' names the `mod` primitive.
        src = """
def is_even
  intent "parity"
  sig    (n: Int) -> Bool
  effects {}
  cand
    eq(n % 2, 0)
"""
        with self.assertRaises(ParseError) as cm:
            parse(src)
        self.assertIn("mod", str(cm.exception))


class HintMessageTests(unittest.TestCase):
    """The runtime's ``unknown callable`` and ``unbound name`` errors
    include one-line hints for common-guess misses. Regression tests
    for the 2026-05-11 ergonomics pass.
    """

    def test_str_reverse_suggests_polymorphic_reverse(self) -> None:
        src = """
def main
  intent "reverse via guessed method name"
  sig    () -> String
  effects {}
  cand
    str.reverse("abc")
"""
        from codifide.runtime.errors import CodifideError
        from codifide.runtime.interpreter import run
        module = parse(src)
        with self.assertRaises(CodifideError) as cm:
            run(module)
        self.assertIn("reverse", str(cm.exception))
        self.assertIn("polymorphic", str(cm.exception))

    def test_clock_hour_suggests_clock_now(self) -> None:
        src = """
def main
  intent "read the hour"
  sig    () -> Int
  effects {clock.read}
  cand
    hour <- clock.hour
    hour
"""
        # clock.hour is not a primitive; the lookup falls through to
        # the Attr path which tries Ref("clock"), which is unbound.
        # The hint on "hour" fires when the bind later tries to use it.
        from codifide.runtime.errors import CodifideError
        from codifide.runtime.interpreter import run
        module = parse(src)
        with self.assertRaises(CodifideError) as cm:
            run(module)
        msg = str(cm.exception)
        self.assertIn("clock.now", msg)



class BooleanPrimitiveCallTests(unittest.TestCase):
    """Regression for the 2026-05-11 assessment-battery parser bug.

    Before the fix, calling `and(...)` or `or(...)` as a function
    (rather than using `a and b` infix) was misrewritten by the
    desugarer: `and` and `or` are in the infix table, and the
    desugar pass tried to extract left/right operands from a
    call-shaped `and(...)` and failed with an opaque parser
    error.

    The fix: when a word operator is immediately followed by `(`
    (after optional whitespace), treat it as a call, not infix.
    """

    def test_and_as_function_call_parses(self) -> None:
        from codifide.parser.expr_parser import parse_expr
        # Must not raise.
        parse_expr("and(true, true)")
        parse_expr("and(contains(s, \"@\"), contains(s, \".\"))")

    def test_or_as_function_call_parses(self) -> None:
        from codifide.parser.expr_parser import parse_expr
        parse_expr("or(eq(n, 0), eq(n, 1))")

    def test_infix_and_still_works(self) -> None:
        from codifide.parser.expr_parser import parse_expr
        # Belt-and-braces: the fix must not regress infix `and`.
        parse_expr("p and q")

    def test_and_call_runs_end_to_end(self) -> None:
        src = """
def f
  intent "and as call"
  sig    (x: Bool, y: Bool) -> Bool
  effects {}
  cand
    and(x, y)
"""
        from codifide.runtime.interpreter import run
        m = parse(src)
        self.assertTrue(run(m, entry="f", args=[True, True]))
        self.assertFalse(run(m, entry="f", args=[True, False]))


    def test_identifier_containing_or_does_not_split(self) -> None:
        # Regression: `greet_or_refuse("Ada")` was being desugared as
        # `or(greet_, _refuse(...))` because the infix-operator
        # boundary check treated `_` as a word boundary. Found while
        # writing 2026-05-11 assessment programs.
        from codifide.parser.expr_parser import parse_expr
        from codifide.core.types import Call
        e = parse_expr('greet_or_refuse("Ada")')
        self.assertIsInstance(e, Call)
        self.assertEqual(e.fn, "greet_or_refuse")

    def test_identifier_containing_and_does_not_split(self) -> None:
        from codifide.parser.expr_parser import parse_expr
        from codifide.core.types import Call
        e = parse_expr('check_and_act(x)')
        self.assertIsInstance(e, Call)
        self.assertEqual(e.fn, "check_and_act")
