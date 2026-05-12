# Rust parser — proposal (2026-05-12)

*By Quill. Proposal filed; proceeding under Douglas's standing "go" approval.*

## What this proposes

Port the Codifide surface-syntax parser from Python to Rust. The
Python parser in `codifide/parser/` is the spec; the Rust parser
must produce identical canonical JSON for every valid program.

This removes the Python subprocess dependency from `codifide-run`.
After this lands, the Rust binary is fully self-contained: parse,
evaluate, output — no Python required at runtime.

## Scope

**In scope:**
- Line-oriented outer parser (mirrors `parser.py`).
- Expression lexer (mirrors `lexer.py`).
- Recursive-descent expression parser (mirrors `expr_parser.py`).
- Infix desugaring (`<=`, `>=`, `==`, `!=`, `<`, `>`, `and`, `or`).
- Multi-line expression continuation (bracket balance + if/then/else).
- All surface keywords: `def`, `intent`, `sig`, `effects`, `pre`,
  `post`, `cand`, `when`, `cost`, `believe`, `else`, `bottom`.
- Unicode keyword glyphs (≡, ⟡, σ, ⚡, ⊢, ⊣, ƒ, ¿, ⨯, ⊥).
- `import name = sha256:<hex>` (direct identity binding).
- `module <name>` declaration.
- Comment stripping (`#`).

**Out of scope:**
- `from <identity> import <name>` (requires store access; deferred).
- Store integration in the Rust binary (deferred).

## Conformance surface

The Python parser is the spec. The Rust parser must produce canonical
JSON that round-trips identically through `codifide-canonical`'s
`from_canonical_json`. The conformance test: parse every `.cod` file
with both parsers, serialize to canonical JSON, compare bytes.

The existing `tests/test_conformance.py` already does this for the
canonical form. A new `tests/test_rust_parser.py` will run the Rust
binary's `parse` subcommand and compare output to Python's
`to_canonical(parse(src))`.

## Crate structure

The parser lives in `crates/codifide-interpreter/src/parser.rs` (and
sub-modules). It produces the same `Module` type that
`codifide-canonical` defines. The `codifide-run` binary gains a
`parse` subcommand that prints canonical JSON to stdout.

## What I'm not yet sure of

Whether the infix desugaring is best done as a pre-pass (matching
Python) or integrated into the recursive-descent parser. The pre-pass
approach is simpler to port; the integrated approach is cleaner. Will
use the pre-pass approach to match Python exactly.
