# Rust parser landed — codifide-run is fully self-contained (2026-05-12)

*By Quill.*

The Rust parser is running. `codifide-run` no longer calls Python for
anything. Parse, evaluate, output — pure Rust, no subprocess.

## What landed

**`crates/codifide-interpreter/src/parser/`** — new module:

- `tokens.rs` — keyword and operator tables (ASCII + Unicode glyphs).
- `lexer.rs` — expression-level lexer: identifiers, numbers, strings,
  operators, punctuation. Hint messages for common infix-operator
  misses (`%`, `+`, `*`, `/`).
- `expr_parser.rs` — recursive-descent expression parser with infix
  desugaring (`<=`, `>=`, `==`, `!=`, `<`, `>`, `and`, `or`).
  Inline conditional (`if ... then ... else`). Dotted-name Attr chains.
- `mod.rs` — line-oriented outer parser. All surface keywords, multi-
  line expression continuation (bracket balance + if/then/else
  tracking), bind parsing, believe blocks, cost annotations, signature
  and effects parsing, string literal escape handling.

**`codifide-run parse <file.cod>`** — new subcommand. Prints canonical
JSON to stdout. Used by the Python conformance bridge and the Python
CLI's `canonical` subcommand (which still uses the Python parser for
now; the Rust `parse` subcommand is available for direct use).

**`codifide-run run <file.cod>`** — now uses the Rust parser directly.
No Python subprocess. The binary is fully self-contained.

**`tests/test_rust_parser.py`** — 3 test classes, 3 passing. Parses
every example with both Python and Rust, serializes to canonical JSON,
compares byte-for-byte.

## One bug found and fixed

`compose_steps` was flattening multi-step candidate bodies into a
single `Seq` instead of nesting them as Python does
(`Seq(head, compose_steps(tail))`). Fixed: the Rust version now
mirrors Python's recursive nesting exactly.

## Test counts

- Python: **289 passing, 0 skipped** (was 286; +3 from parser conformance).
- Rust canonical: **28 passing** (unchanged).
- Rust interpreter conformance: **70 passing** (unchanged).
- Rust parser conformance: **3 passing** (new).

## Performance

The conformance bridge runs in **0.78s** (was 4.78s before the Rust
parser). The 6× speedup is entirely from removing the Python subprocess
for parsing.

## What is not yet done

- `from <identity> import <name>` — requires store access; deferred.
- The Python CLI's `canonical` and `run` subcommands still use the
  Python parser. Routing them through the Rust parser is a future step.
- Rust parser unit tests (beyond the conformance bridge).

## What I'm not yet sure of

Whether the `from`-import deferral is the right call for v2-A or
whether it should be tackled before the parallel evaluator. The
current test suite does not exercise `from`-imports through the Rust
runtime, so the gap is invisible to the conformance bridge. Worth
noting before the parallel evaluator work starts.
