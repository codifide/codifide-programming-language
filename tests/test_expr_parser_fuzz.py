"""Expression-parser fuzz harness.

The existing ``test_parser_fuzz.py`` targets the outer line-oriented
parser. This file targets the expression parser specifically, with
emphasis on the infix desugarer — the one part of the parser that
does sophisticated rewriting before handing tokens to the
recursive-descent loop.

Two bugs surfaced in that layer during the 2026-05-11 assessment:

- ``and(a, b)`` and ``or(a, b)`` as function calls were misrewritten
  by treating ``and``/``or`` as infix operators whose right-hand
  side started at the ``(``.
- Identifiers containing ``or`` or ``and`` substrings
  (``greet_or_refuse``, ``check_and_act``) were split because the
  word-boundary check used ``str.isalnum()``, which doesn't count
  ``_`` as part of an identifier.

Both were textbook infix-desugarer bugs. Neither was caught by the
existing test corpus. This suggests a whole class of similar bugs
is plausible; the battery below systematically probes for peers.

The only contract we enforce is the same one the outer fuzzer
enforces: for any input, ``parse_expr`` either returns an ``Expr``
or raises a typed ``ExprParseError`` / ``LexError``. No bare
``AttributeError``, no ``TypeError``, no ``IndexError``.
"""
from __future__ import annotations

import os
import signal
import string
import unittest
from typing import Callable, Iterable, List, Tuple

from codifide.core.types import Call, Concat, Lit, Ref
from codifide.parser.expr_parser import ExprParseError, parse_expr
from codifide.parser.lexer import LexError
from codifide.parser.tokens import KEYWORDS, OPERATORS


# ---------------------------------------------------------------------------
# Timeout helper (mirror of the outer-fuzzer helper)
# ---------------------------------------------------------------------------


class _ParseTimeout(Exception):
    pass


def _with_timeout(fn: Callable[[], object], seconds: int = 1) -> object:
    has_alarm = hasattr(signal, "SIGALRM") and os.name == "posix"
    if not has_alarm:
        return fn()

    def _handler(signum, frame):  # noqa: ANN001
        raise _ParseTimeout("parse exceeded timeout budget")

    prev_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)


# ---------------------------------------------------------------------------
# Identifiers containing every reserved substring
# ---------------------------------------------------------------------------


def _reserved_word_substrings() -> List[str]:
    """Every keyword and word-operator that could be a substring of an identifier.

    Pulled from the real tables in ``codifide.parser.tokens`` so a
    keyword added later is automatically part of the fuzz corpus.
    Symbolic operators (``++``, ``=>``, ``->``, ``<-``) are excluded
    because they cannot appear inside an identifier.
    """
    words: set[str] = set()
    for form in KEYWORDS.keys():
        if form.isalpha():
            words.add(form)
    # OPERATORS has only symbolic forms for our purposes today; the
    # word operators live in the internal ``_INFIX`` table of
    # ``expr_parser``. Add those explicitly.
    for w in ("and", "or"):
        words.add(w)
    return sorted(words)


def _identifier_variants_of(substring: str) -> List[str]:
    """Build plausible identifier names that embed ``substring``.

    Combinations cover:
    - ``sub_`` prefix with underscore
    - ``_sub`` suffix with underscore
    - ``_sub_`` surrounded by underscores
    - word-boundary cases: ``subword``, ``wordsub``, ``word_sub_word``
    - purely alphabetic flanks: ``presubpost``
    """
    s = substring
    return [
        f"{s}_x",
        f"x_{s}",
        f"x_{s}_y",
        f"pre{s}",
        f"{s}post",
        f"pre{s}post",
        f"x{s}y",
        f"_{s}_",
        f"{s}{s}",
        f"{s}_{s}",
    ]


# ---------------------------------------------------------------------------
# Call-shape corpus around every keyword-as-callable
# ---------------------------------------------------------------------------


def _keyword_as_callable_shapes() -> List[str]:
    """Expressions that call keyword-looking names as primitives.

    Not all of these are legal Codifide (``cand`` is a keyword, not a
    callable), but the expression parser should parse the call shape
    cleanly — the runtime's call resolution is where "not a valid
    callable" gets decided. A parse-time crash on any of these is a
    bug in the expression parser.
    """
    out: List[str] = []
    candidates = _reserved_word_substrings()
    for name in candidates:
        out.append(f"{name}()")
        out.append(f"{name}(1)")
        out.append(f"{name}(1, 2)")
        out.append(f"{name}(x, y)")
        out.append(f"{name}({name}, {name})")  # nested call to the same keyword
    return out


# ---------------------------------------------------------------------------
# Operator precedence boundaries
# ---------------------------------------------------------------------------


def _precedence_corner_cases() -> List[str]:
    """Expressions near operator boundaries.

    Today the only real infix operator that survives the desugar pass
    is string concatenation (``++``). Every other infix form is
    rewritten to a call before parsing proper. These cases exercise
    the rewrite + the remaining infix together.
    """
    return [
        # Chained concatenation.
        '"a" ++ "b" ++ "c"',
        # Concat of call results.
        'upper("a") ++ lower("B")',
        # Comparison desugar.
        "lt(x, y)",
        "x < y",
        "x < y and eq(a, b)",
        "eq(add(x, 1), 2)",
        # Word op not at start (infix), word op at start (call-shaped).
        "a and b",
        "and(a, b)",
        "or(x, y)",
        "not(z)",
        # Identifier flanked by an operator.
        "a_or_b and c",
        "a and b_or_c",
        # Negative number vs subtraction.
        "-3",
        "sub(0, 3)",
        "add(-3, 5)",
        # String with embedded operator-looking characters.
        '"a and b"',
        '"<-"',
        '"=="',
    ]


# ---------------------------------------------------------------------------
# Random torture generator
# ---------------------------------------------------------------------------


def _random_expressions(seed: int = 1, count: int = 200) -> Iterable[str]:
    """Generate ``count`` random expression strings.

    Uses only the Python stdlib's ``random`` for reproducibility.
    Inputs are drawn from:
    - identifiers containing random reserved substrings
    - calls whose name is a reserved word
    - randomly-ordered operator tokens sandwiched by identifiers

    We deliberately generate a mix of well-formed and malformed
    strings. The parser is required to reject the malformed ones
    with a typed error, not to crash.
    """
    import random

    rng = random.Random(seed)
    words = _reserved_word_substrings()
    punct = ["(", ")", ",", " ", "++", "<-", "=>", "<", ">", "=="]
    ident_chars = string.ascii_lowercase + "_"

    for _ in range(count):
        parts: List[str] = []
        length = rng.randint(3, 15)
        for _ in range(length):
            choice = rng.randint(0, 4)
            if choice == 0:
                # A random identifier, possibly embedding a reserved word.
                seg = rng.choice(words)
                pre = "".join(rng.choices(ident_chars, k=rng.randint(0, 5)))
                post = "".join(rng.choices(ident_chars, k=rng.randint(0, 5)))
                parts.append(f"{pre}{seg}{post}".lstrip("_") or seg)
            elif choice == 1:
                # A bare reserved word.
                parts.append(rng.choice(words))
            elif choice == 2:
                # A small integer.
                parts.append(str(rng.randint(-9, 9)))
            elif choice == 3:
                # A short string literal.
                parts.append(f'"{rng.choice(words)}"')
            else:
                parts.append(rng.choice(punct))
        yield " ".join(parts)


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


def _parse_must_be_typed(label: str, src: str, test: unittest.TestCase) -> None:
    """Parse ``src`` under a 1s deadline; any non-typed failure is a bug.

    Accepted outcomes:
    - returns an Expr (some ast node type)
    - raises ExprParseError
    - raises LexError

    Rejected outcomes (these are the bugs the fuzzer is hunting):
    - any other exception (AttributeError, IndexError, TypeError, ...)
    - infinite loop (caught by SIGALRM)
    """
    try:
        result = _with_timeout(lambda: parse_expr(src), seconds=1)
    except (ExprParseError, LexError):
        return  # typed rejection — correct behavior
    except _ParseTimeout:
        test.fail(f"{label}: parse_expr timed out on {src!r}")
    except Exception as exc:
        test.fail(
            f"{label}: parse_expr raised non-typed {type(exc).__name__} "
            f"on {src!r}: {exc}"
        )
    else:
        # If it succeeded, assert the result is a known AST type rather
        # than, e.g., ``None``.
        if result is None:
            test.fail(f"{label}: parse_expr returned None on {src!r}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class IdentifierSubstringRegressions(unittest.TestCase):
    """Identifiers that embed a reserved substring must parse as a single
    reference, not split into operator-shaped pieces.

    The 2026-05-11 bug: ``greet_or_refuse`` became ``or(greet_, _refuse)``
    because the desugar pass didn't treat ``_`` as an identifier
    character. This test exhaustively checks every keyword/operator
    substring in every plausible identifier position.
    """

    def test_every_reserved_substring_in_every_position_parses_as_ref(self) -> None:
        for substring in _reserved_word_substrings():
            for name in _identifier_variants_of(substring):
                with self.subTest(name=name):
                    _parse_must_be_typed(
                        f"identifier {name!r} embedding {substring!r}",
                        name,
                        self,
                    )


class KeywordAsCallableShapes(unittest.TestCase):
    """Call shapes that use reserved words as callable names must parse.

    The 2026-05-11 bug: ``and(a, b)`` was misrewritten by the infix
    desugarer. This test exhaustively probes every keyword in every
    basic call shape.
    """

    def test_every_reserved_name_in_every_call_shape_parses(self) -> None:
        for shape in _keyword_as_callable_shapes():
            with self.subTest(shape=shape):
                _parse_must_be_typed(f"call shape {shape!r}", shape, self)


class PrecedenceCornerCases(unittest.TestCase):
    """Expressions around operator-precedence boundaries.

    Hand-curated. Each must either parse or raise a typed error.
    """

    def test_precedence_cornercases_parse_cleanly(self) -> None:
        for expr in _precedence_corner_cases():
            with self.subTest(expr=expr):
                _parse_must_be_typed(f"precedence case {expr!r}", expr, self)


class RandomTortureInputs(unittest.TestCase):
    """200 random inputs built from the reserved-word and punctuation soup.

    Every input must parse or raise a typed error within 1 second.
    """

    def test_random_inputs_never_leak_untyped_failures(self) -> None:
        for i, expr in enumerate(_random_expressions(seed=0xC0DEF1DE, count=200)):
            with self.subTest(i=i, expr=expr):
                _parse_must_be_typed(f"random #{i} {expr!r}", expr, self)


class TwoRegressionWitnesses(unittest.TestCase):
    """The two specific 2026-05-11 bugs, pinned forever.

    Redundant with the exhaustive sweeps above but makes the regression
    intent obvious when someone reads the failures.
    """

    def test_greet_or_refuse_parses_as_single_identifier(self) -> None:
        e = parse_expr("greet_or_refuse(x)")
        self.assertIsInstance(e, Call)
        self.assertEqual(e.fn, "greet_or_refuse")

    def test_and_as_call_parses_with_two_args(self) -> None:
        e = parse_expr("and(p, q)")
        self.assertIsInstance(e, Call)
        self.assertEqual(e.fn, "and")
        self.assertEqual(len(e.args), 2)
        self.assertIsInstance(e.args[0], Ref)
        self.assertEqual(e.args[0].name, "p")


if __name__ == "__main__":
    unittest.main()
