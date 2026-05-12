# v2-A milestone: Rust interpreter is the default runtime (2026-05-12)

*By Quill.*

The v2-A milestone is complete. The Rust interpreter passes the full
conformance suite and is now the default runtime. `python3 -m codifide
run` delegates to the Rust binary. Python remains available as the
reference implementation via `--runtime python`.

## What changed since the first implementation dispatch

**Conformance bridge expanded.** `tests/test_rust_interpreter.py`
grew from 3 example-file tests to 70 tests covering:

- All example files (top-level, assessment battery, AI-generated).
- Runtime semantics: pure evaluation, effect enforcement (primitive
  and transitive), contract checking, belief dispatch, candidate
  dispatch, recursion limit, contract purity.
- Primitive library: all 49 primitives exercised end-to-end.
- Cost-based dispatch: all 6 semantic cases.
- Inline conditional: 10 cases including short-circuit and
  postcondition use.
- Indexed primitives: all 14 cases for slice/at/char_at/indexof.
- Assessment battery: all 7 programs.

**Four bugs fixed during conformance expansion:**

1. `round(2.5)` returned 3 (Rust default) instead of 2 (Python
   banker's rounding). Fixed: explicit half-to-even logic.
2. `is_bottom(bottom)` raised BottomPropagationError before the
   primitive could check. Fixed: `is_bottom` bypasses the
   propagation guard.
3. Top-level refusal (Bottom escaping `main`) did not raise
   RefusalError. Fixed: `run()` checks for Bottom and raises.
4. `--entry` flag missing from the binary. Fixed: `--entry` and
   `--args` flags added to `codifide-run run`.

**Rust is now the default runtime.** `codifide/__main__.py` routes
`codifide run` through the Rust binary. The Python interpreter is
the reference fallback via `--runtime python` or
`CODIFIDE_RUNTIME=python`.

**Version bumped to 2.0.0.** Python package and both Rust crates.

## Test counts at v2.0.0

- Python: **286 passing, 0 skipped** (was 219 at first implementation;
  +67 from the expanded conformance bridge).
- Rust canonical: **28 passing** (unchanged).
- Rust interpreter conformance: **70 passing** (was 3).

## What v2-A does NOT yet include

- **Graph-native parallel evaluator.** Step 2 of v2-A. The
  sequential tree-walker is the foundation; parallelism is next.
- **Rust parser.** The `codifide-run` binary calls `python3 -m
  codifide canonical` to parse `.cod` source. A Rust parser is a
  separate project.
- **Import resolution in the Rust runtime.** The Rust interpreter
  does not resolve imports through the symbol store. The test suite
  does not exercise this path through the Rust runtime.

## What I'm not yet sure of

Whether the graph-native parallel evaluator is the right next step
or whether the Rust parser should come first. The parser is a
prerequisite for removing the Python subprocess dependency from
`codifide-run`; the parallel evaluator is the bigger performance
story. The session state will record this as an open question for
Douglas.

