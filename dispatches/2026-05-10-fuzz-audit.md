# Noema — audit note, parser robustness and concurrency

*By Sable. 10 May 2026.*

Scope: the surface parser under adversarial input, and the store's
atomic-write path under concurrent processes. These were carried over
from prior audits as "not tested" and became actionable when
`tests/test_parser_fuzz.py` and `tests/test_store_concurrency.py` were
added to the suite.

I did not test CLI behavior against hostile file paths, model primitive
sandboxing, or `cargo audit` against the current dependency set after
today's changes. Those are the next-audit items.

## Findings

### P1-3 — Lexer errors leaked through the parser's contract

**What.** The parser's public promise is that `noema.parse(source)`
returns a `Module` or raises `ParseError`. Nothing else. In practice,
the expression lexer's `LexError` — raised for unterminated strings,
unknown characters outside strings, and stray operators — bypassed the
`_safe_parse_expr` wrapper and surfaced to the host as a bare
`LexError`.

**Probe that caught it.** The fuzz harness flagged five distinct
inputs and ~85 structurally fuzzed inputs that all reduced to this
same root cause:

- Unclosed string literal inside a candidate body.
- Escaped-quote-then-unclosed: `"escaped \" but then unclosed`.
- Any non-ASCII character appearing outside a string literal (e.g. a
  bare `⊥` glyph in an expression position).
- Double bind operator: `name <- <- expr`.
- Stray operator tokens the lexer does not know.

**Why it matters.** A host embedding Noema cannot rely on the typed-
error discipline if the parser can leak a parser-internal exception
type. Every defense we built on top of `NoemaError` (uniform
classification, intent-chain rendering, test assertions on error
kind) was one well-formed hostile string away from being wrong.

**Fixed.** `noema/parser/parser.py::_safe_parse_expr` now catches
`LexError` as well as `ExprParseError` and wraps it in `ParseError`.
All 30 hand-curated fuzz inputs and all 200 structural-fuzz inputs now
respect the contract.

### P1-4 — Deep parenthesis nesting raised RecursionError

**What.** The expression parser in `noema/parser/expr_parser.py` uses
recursive descent. A 500-paren-deep expression blew the Python call
stack and surfaced as a bare `RecursionError`. Hostile input of a few
hundred bytes was enough to crash the parser.

**Probe that caught it.** `((((...(1)...))))` nested 500 deep.

**Why it matters.** Same reason as P1-3, plus denial-of-service: a
small attacker-controlled string is enough to crash any host that
embeds the parser. `RecursionLimitError` exists at the interpreter
layer but does not protect the parser.

**Fixed.** `_Parser` now tracks a `_paren_depth` counter and raises
`ExprParseError` past `MAX_PAREN_DEPTH = 256`. That flows through
`_safe_parse_expr` as a typed `ParseError`. The paren nesting stress
fuzz input now rejects cleanly at the 256 bound rather than blowing
the stack at ~500.

## Not-findings (explicitly cleared)

- **Unicode glyphs mixed with ASCII in expressions.** Rejected via the
  wrapped `LexError` path after P1-3 fix. The parser does not accept
  non-ASCII identifiers yet; that is a language design question, not
  a bug.
- **1000-definition modules.** Parse in linear time. No quadratic
  behavior observed.
- **100KB single lines.** Parse in linear time.
- **NUL bytes and control characters.** Either rejected cleanly or
  passed through as string literal contents depending on position.
- **Unbalanced parens/braces in signatures and effect sets.** Surface
  as `ParseError` with location.

## Concurrency (P3-3, carried from previous audit, now closed)

`tests/test_store_concurrency.py` spawns 8 processes that simultaneously
`put` either the same symbol or 8 distinct symbols. Both cases pass:

- Same-symbol race produces exactly one object on disk, every worker
  receives the identical identity, no `.noema-*.tmp` leftovers.
- Distinct-symbol race produces exactly 8 objects, every worker
  receives a unique identity, no leftovers.

The `tempfile.mkstemp` + `os.replace` pattern is correct for the cases
we care about. The question Sable raised last audit — "what if two
writers race the same identity" — is answered: one wins the rename, the
other loses cleanly (its temp file is cleaned up via the write path's
`finally` clause; `os.replace` is atomic so no reader sees a partial
object).

## Index verification (P3-1, opt-in, now shipped)

The previous audit recommended an opt-in `noema store verify` rather
than a parse-time pointee check. That subcommand now exists. It walks
a module's `imports` table, confirms each pointee is present and
round-trips through canonical form, and exits non-zero if any are
missing. Test coverage is in `tests/test_store.py::StoreVerifyTests`.

## What I did not test

- The parser against a mutation-fuzzer (as opposed to the
  hand-curated + structured-sampling harness we have). Mutation fuzzing
  would give higher coverage per unit time, but needs infrastructure
  (AFL, libFuzzer) outside the current test harness.
- The CLI against hostile file paths — symlink attacks, `/dev/zero`,
  concurrent-file-growth races.
- `cargo audit` after today's dependency-free changes. The dep set has
  not changed since last audit; re-running at every release gate is
  still the discipline.
- The Rust canonical crate against the same fuzz corpus. The Rust
  crate does not parse `.nm` surface syntax so the fuzz surface is
  narrower, but its JSON decoder could have its own edge cases worth
  probing.
- Whether a hostile index with 10,000 `from`-import names produces
  pathological parse behavior. `from`-import lines fail fast on first
  missing name (sub-millisecond in our probe), but the happy-path case
  where all names resolve has not been stressed.

## Summary

Two P1 findings from the new fuzz harness, both fixed with small wrappers
and a depth counter. One P3 carried concurrency item closed with a
concrete test. One P3 carried index-verification item closed with a new
subcommand. No P0s. The parser now honors its contract under every
adversarial input the harness can generate with a seeded RNG.

The uncomfortable observation stays the same as last audit: every new
capability increases the surface an adversary can attack. The next
audit should look at the CLI's filesystem assumptions and at the Rust
crate under its own fuzz.
