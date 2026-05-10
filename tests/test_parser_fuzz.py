"""Parser fuzz harness.

The parser's job is to turn surface text into a Module or raise a
``ParseError``. That is the only contract the embedding host can rely on.
Anything else leaking out — a bare ``LexError``, a ``RecursionError``,
a hang — is a parser bug: it means a malicious or malformed .nm file can
crash or wedge the host process.

These tests feed a large set of adversarial inputs through ``noema.parse``
and assert the only-two-outcomes invariant. Each parse is bounded by a
one-second SIGALRM so infinite-loop bugs surface as failures rather than
as a stuck test run.
"""
from __future__ import annotations

import os
import random
import signal
import string
import unittest
from typing import Callable

import noema
from noema.runtime.errors import ParseError


# ---------------------------------------------------------------------------
# Timeout helper
# ---------------------------------------------------------------------------


class _ParseTimeout(Exception):
    """Raised by the SIGALRM handler when a parse exceeds its budget."""


def _with_timeout(fn: Callable[[], object], seconds: int = 1) -> object:
    """Run ``fn`` with a SIGALRM-backed deadline.

    SIGALRM only fires on the main thread on POSIX. ``unittest`` runs the
    test body on the main thread, so this is sufficient for the suite.
    On platforms without SIGALRM (Windows), we fall back to running ``fn``
    without a timeout — the parser is expected to terminate on every
    input, and on Windows we cannot interrupt it mid-call anyway.
    """
    has_alarm = hasattr(signal, "SIGALRM") and os.name == "posix"
    if not has_alarm:
        return fn()

    def _handler(signum, frame):  # noqa: ANN001 — signal handler signature
        raise _ParseTimeout("parse exceeded timeout budget")

    prev_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)


# ---------------------------------------------------------------------------
# Adversarial input corpus
# ---------------------------------------------------------------------------


def _valid_skeleton(body: str = "    1") -> str:
    """Return a minimally valid definition so we can splice bodies in."""
    return (
        "def f\n"
        "  intent \"a\"\n"
        "  sig    () -> Int\n"
        "  effects {}\n"
        "  cand\n"
        f"{body}\n"
    )


# Each entry: (label, source). Labels make test failures self-describing.
ADVERSARIAL_INPUTS: list[tuple[str, str]] = [
    # Empty — degenerate but legal; parser must return an empty module.
    ("empty_string", ""),

    # A single bare keyword with nothing after it.
    ("single_def_token", "def"),

    # `def` with no name but a trailing newline — exercises EOF handling
    # in the definition parser.
    ("def_no_name_with_newline", "def\n"),

    # Massively nested parens — 500-deep. Would blow the Python recursion
    # limit if the expression parser does naive recursion. This is a
    # known fuzz vector against recursive-descent parsers.
    ("deep_parens_500", _valid_skeleton("    " + "(" * 500 + "1" + ")" * 500)),

    # Unclosed string literal inside a cand body. The lexer raises
    # LexError for unterminated strings; if that escapes instead of
    # being wrapped in ParseError, the host sees an unexpected type.
    (
        "unclosed_string_in_body",
        _valid_skeleton('    "missing close'),
    ),

    # String with embedded escapes mixed with an unclosed quote — the
    # escape machinery should not swallow the closing quote's absence.
    (
        "escaped_quotes_then_unclosed",
        _valid_skeleton('    "escaped \\" but then unclosed'),
    ),

    # Unicode glyphs the language does not recognize. Some (⊥) are real
    # keywords, some (⟡, σ, ⚡, ⊢, ⊣, ƒ, ¿, ⊨) are not. They should
    # either parse (if they happen to be allowed identifiers) or raise
    # ParseError — never a bare lexer error.
    (
        "unicode_glyph_soup_in_body",
        _valid_skeleton("    ⟡ σ ⚡ ⊢ ⊣ ƒ ¿ ⊨ ⊥ ≡"),
    ),

    # Glyph that collides with the expression lexer's unknown-char path.
    ("lone_bottom_glyph_expr", _valid_skeleton("    ⊥")),

    # A keyword used as a definition name. Noema does not currently
    # forbid this; whatever the outcome, it must be ParseError or OK.
    (
        "keyword_as_def_name",
        "def cand\n"
        "  intent \"a\"\n"
        "  sig () -> Int\n"
        "  effects {}\n"
        "  cand\n"
        "    1",
    ),

    # A `module` line with only whitespace after the keyword.
    ("module_only_whitespace", "module     \n"),

    # Believe block with no `=>` operators at all — an arm line that does
    # not contain the arrow should still yield a clean ParseError.
    (
        "believe_no_arrows",
        _valid_skeleton(
            "    believe 1\n"
            "      x\n"
            "      else => 1"
        ),
    ),

    # Double bind operator: `name <- <- expr`. The right-hand side is
    # then expression text starting with `<-`, which the expression
    # lexer cannot lex. Must surface as ParseError, not LexError.
    (
        "double_bind_operator",
        _valid_skeleton("    x <- <- 1"),
    ),

    # A single expression line that is 100KB long. Linear-time parsing
    # should handle this easily; quadratic bugs would time out.
    (
        "very_long_line_100kb",
        _valid_skeleton("    " + ("x" * 100_000)),
    ),

    # Lines with only tabs — preprocessing should discard them.
    ("tabs_only_lines", "\t\t\t\n\t\n\t\t\n"),

    # Lines with only spaces.
    ("spaces_only_lines", "    \n   \n     \n"),

    # Mixed tabs and spaces — whitespace-only lines either way.
    ("mixed_ws_lines", " \t \t\n\t \t \n"),

    # `from ` with nothing after it.
    ("from_empty", "from \n"),

    # `import ` with no `=` clause.
    ("import_no_equals", "import \n"),

    # NUL byte inside a string literal. Parsers that treat NUL as
    # end-of-input can truncate or crash.
    (
        "nul_byte_in_string",
        _valid_skeleton('    "a\x00b"'),
    ),

    # NUL byte at top level, outside any string. Should be rejected as
    # an unexpected top-level line, not crash the preprocessor.
    ("nul_byte_top_level", "\x00\n"),

    # Control characters outside strings: vertical tab, bell, form feed.
    ("control_chars_top_level", "\x0b\x07\x0c\n"),

    # A believe arm whose value is itself deeply nested — parser may
    # currently reject this, but it must reject cleanly.
    (
        "believe_arm_with_nested_parens",
        _valid_skeleton(
            "    believe 1\n"
            "      1 => " + "(" * 50 + "1" + ")" * 50 + "\n"
            "      else => 1"
        ),
    ),

    # Signature with an unbalanced open-paren. Must be reported as a
    # signature parse error, not propagate an index error.
    (
        "sig_unbalanced_open_paren",
        "def f\n"
        "  intent \"a\"\n"
        "  sig (a: T -> Int\n"
        "  effects {}\n"
        "  cand\n"
        "    1",
    ),

    # Signature with an unbalanced close-paren.
    (
        "sig_unbalanced_close_paren",
        "def f\n"
        "  intent \"a\"\n"
        "  sig a: T) -> Int\n"
        "  effects {}\n"
        "  cand\n"
        "    1",
    ),

    # Effect set with an unbalanced open-brace.
    (
        "effects_unbalanced_open_brace",
        "def f\n"
        "  intent \"a\"\n"
        "  sig () -> Int\n"
        "  effects {io.stdout\n"
        "  cand\n"
        "    1",
    ),

    # Effect set with an unbalanced close-brace.
    (
        "effects_unbalanced_close_brace",
        "def f\n"
        "  intent \"a\"\n"
        "  sig () -> Int\n"
        "  effects io.stdout}\n"
        "  cand\n"
        "    1",
    ),

    # `cand` with only whitespace after — trailing whitespace on the
    # keyword line should not confuse the outer parser.
    (
        "cand_only_trailing_whitespace",
        "def f\n"
        "  intent \"a\"\n"
        "  sig () -> Int\n"
        "  effects {}\n"
        "  cand   \n"
        "    1",
    ),

    # `intent` followed by a non-string payload. The parser must refuse
    # clearly rather than letting a raw value slip through.
    (
        "intent_non_string_payload",
        "def f\n"
        "  intent 42\n"
        "  sig () -> Int\n"
        "  effects {}\n"
        "  cand\n"
        "    1",
    ),

    # The same def name repeated many times. Duplicate handling lives
    # at a higher layer than parsing; the parser must still accept the
    # surface text without complaint.
    (
        "repeated_def_name_20x",
        "\n\n".join(
            [
                "def f\n"
                "  intent \"a\"\n"
                "  sig () -> Int\n"
                "  effects {}\n"
                "  cand\n"
                "    1"
            ]
            * 20
        ),
    ),

    # A thousand defs, each with a trivial cand. Linear-time stress on
    # the outer parser.
    (
        "thousand_definitions",
        "\n\n".join(
            f"def f{idx}\n"
            f"  intent \"a\"\n"
            f"  sig () -> Int\n"
            f"  effects {{}}\n"
            f"  cand\n"
            f"    1"
            for idx in range(1000)
        ),
    ),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class ParserFuzzTests(unittest.TestCase):
    """Parser never raises anything other than ``ParseError``.

    If a fuzz input raises ``RecursionError``, ``LexError``, ``IndexError``,
    or any other non-``ParseError`` exception, that is a real parser bug.
    The test surfaces the specific input via ``self.fail`` so the bug is
    actionable rather than swallowed.
    """

    def _assert_parses_or_parse_errors(self, label: str, source: str) -> None:
        """Invariant: parse(source) either returns a Module or raises ParseError."""
        def _attempt() -> object:
            return noema.parse(source)

        try:
            result = _with_timeout(_attempt, seconds=1)
        except ParseError:
            # Clean rejection — the parser's contract is satisfied.
            return
        except _ParseTimeout:
            self.fail(
                f"parse hung (>1s) on input {label!r}. "
                f"Source length={len(source)} chars."
            )
        except BaseException as exc:  # noqa: BLE001 — we want to catch anything
            # This is the bug-reporting path. Any non-ParseError exception
            # that escapes noema.parse is a contract violation.
            self.fail(
                f"parse raised {type(exc).__module__}.{type(exc).__name__} "
                f"on input {label!r}: {exc!r}. "
                f"The contract is that parse() returns a Module or raises "
                f"ParseError. Nothing else should leak."
            )
        else:
            # Accept any return value — what matters is that no exception
            # of the wrong type escaped. We do not assert on the Module
            # shape here because valid fuzz inputs may legitimately
            # produce empty or unusual modules.
            self.assertIsNotNone(result)

    def test_adversarial_inputs_raise_parse_error_or_succeed(self) -> None:
        """Hand-curated adversarial inputs respect the parse contract."""
        for label, source in ADVERSARIAL_INPUTS:
            with self.subTest(label=label):
                self._assert_parses_or_parse_errors(label, source)

    # ------------------------------------------------------------------
    # Structured, grammar-adjacent property fuzz
    # ------------------------------------------------------------------

    def test_structured_property_fuzz(self) -> None:
        """200 seeded, grammar-adjacent inputs respect the parse contract.

        We generate inputs by splicing real keywords into random identifier
        noise, varying indentation, stuffing many ``cand`` blocks, dropping
        ``else`` arms, etc. The seed is fixed so any failure reproduces
        on re-run.
        """
        rng = random.Random(0xC0FFEE)
        for i in range(200):
            label = f"structured_fuzz_{i}"
            source = _generate_grammar_adjacent_source(rng)
            with self.subTest(label=label, sample=i):
                self._assert_parses_or_parse_errors(label, source)


# ---------------------------------------------------------------------------
# Grammar-adjacent generator
# ---------------------------------------------------------------------------


_KEYWORDS_SOUP = [
    "def", "intent", "sig", "effects", "pre", "post",
    "cand", "when", "believe", "else", "module", "import", "from",
    "bottom", "and", "or",
]


def _rand_ident(rng: random.Random) -> str:
    """Produce an identifier — mostly valid, occasionally a keyword collision."""
    if rng.random() < 0.15:
        return rng.choice(_KEYWORDS_SOUP)
    n = rng.randint(1, 12)
    first = rng.choice(string.ascii_letters + "_")
    rest = "".join(rng.choice(string.ascii_letters + string.digits + "_.") for _ in range(n - 1))
    return first + rest


def _rand_expr_fragment(rng: random.Random) -> str:
    """Produce something that looks like an expression — possibly malformed."""
    style = rng.randint(0, 9)
    if style == 0:
        return str(rng.randint(-1_000_000, 1_000_000))
    if style == 1:
        return f'"{"".join(rng.choices(string.printable, k=rng.randint(0, 40)))}"'
    if style == 2:
        # Deeply nested parens around a literal.
        depth = rng.randint(1, 200)
        return "(" * depth + "1" + ")" * depth
    if style == 3:
        # Unbalanced parens.
        depth = rng.randint(1, 50)
        return "(" * depth + "1" + ")" * rng.randint(0, depth + 2)
    if style == 4:
        ident = _rand_ident(rng)
        return f"{ident}({rng.randint(0, 99)})"
    if style == 5:
        return _rand_ident(rng) + " ++ " + _rand_ident(rng)
    if style == 6:
        # A believe-arm-looking expression line.
        return f"{_rand_ident(rng)} => {rng.randint(0, 99)}"
    if style == 7:
        # Raw bind operator in an expression — illegal at expression level.
        return f"{_rand_ident(rng)} <- {rng.randint(0, 99)}"
    if style == 8:
        # A very long run of `++` concatenations.
        return " ++ ".join(f'"{c}"' for c in rng.choices(string.ascii_letters, k=rng.randint(1, 40)))
    return _rand_ident(rng)


def _rand_cand_block(rng: random.Random) -> str:
    """Produce a single ``cand`` block — body may be malformed."""
    lines = ["  cand"]
    # Optional intent.
    if rng.random() < 0.3:
        lines.append(f'    intent "{_rand_ident(rng)}"')
    # Optional guard.
    if rng.random() < 0.3:
        lines.append(f"    when {_rand_expr_fragment(rng)}")
    # A run of bind/expression lines.
    n_steps = rng.randint(1, 8)
    for _ in range(n_steps):
        if rng.random() < 0.4:
            lines.append(f"    {_rand_ident(rng)} <- {_rand_expr_fragment(rng)}")
        else:
            lines.append(f"    {_rand_expr_fragment(rng)}")
    # Maybe a believe block, occasionally missing its `else`.
    if rng.random() < 0.3:
        lines.append(f"    believe {_rand_expr_fragment(rng)}")
        for _ in range(rng.randint(1, 3)):
            lines.append(f"      {_rand_expr_fragment(rng)} => {_rand_expr_fragment(rng)}")
        if rng.random() < 0.6:
            lines.append(f"      else => {_rand_expr_fragment(rng)}")
    return "\n".join(lines)


def _generate_grammar_adjacent_source(rng: random.Random) -> str:
    """Compose a random .nm-ish source from mostly-valid fragments."""
    parts: list[str] = []
    # Maybe a module line.
    if rng.random() < 0.3:
        if rng.random() < 0.5:
            parts.append(f"module {_rand_ident(rng)}")
        else:
            # Sometimes produce a bad module line — whitespace or junk.
            parts.append("module " + rng.choice(["", "   ", "bad name with spaces", "weird;semi"]))
    # Maybe an import line.
    if rng.random() < 0.2:
        parts.append(
            "import "
            + _rand_ident(rng)
            + " = sha256:"
            + "".join(rng.choices("0123456789abcdef", k=rng.randint(10, 64)))
        )
    # One or more definitions.
    n_defs = rng.randint(1, 6)
    for _ in range(n_defs):
        def_lines = [f"def {_rand_ident(rng)}"]
        if rng.random() < 0.9:
            def_lines.append(f'  intent "{_rand_ident(rng)}"')
        if rng.random() < 0.9:
            def_lines.append("  sig () -> Int")
        if rng.random() < 0.6:
            def_lines.append("  effects {}")
        if rng.random() < 0.3:
            def_lines.append(f"  pre {_rand_expr_fragment(rng)}")
        if rng.random() < 0.3:
            def_lines.append(f"  post {_rand_expr_fragment(rng)}")
        for _ in range(rng.randint(1, 3)):
            def_lines.append(_rand_cand_block(rng))
        parts.append("\n".join(def_lines))
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__":
    unittest.main()
