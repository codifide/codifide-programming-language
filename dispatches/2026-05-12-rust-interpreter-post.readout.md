# Rust interpreter — first implementation landed (2026-05-12)

*By Quill.*

The Rust interpreter is running. Not the default runtime yet — that
milestone is when it passes all 216 tests and the version bumps to
2.0.0. But the tree-walker is built, the conformance bridge is
running, and the first batch of examples agree byte-for-byte between
the two runtimes.

## What landed

**`crates/codifide-interpreter/`** — new crate, depends on
`codifide-canonical` for the AST types.

- `src/value.rs` — `Value` enum with `Bottom`, `Concrete`, `Belief`
  variants. Sable's RI-2 finding resolved: Bottom is a variant, not
  a singleton. All numeric payloads are `f64` (RI-1 resolved).
- `src/errors.rs` — all eight typed error classes mirroring
  `codifide/runtime/errors.py`.
- `src/primitives.rs` — all 49 primitives from the v1 capability
  manifest. `EffectTrace` struct for io/clock/model accumulation.
  Local time via `localtime_r` so `clock.now` matches Python's
  `time.localtime()`.
- `src/interpreter.rs` — tree-walking evaluator. Candidate dispatch
  with cost-based selection. Effect enforcement (primitive-call half
  + transitive static pass). Contract purity (empty effect budget
  for pre/post/guard). Belief dispatch. Inline conditional
  short-circuit. First-class refusal. Recursion limit (default 64).
  Hint messages for known-guess misses (RI-5 resolved).
- `src/bin/codifide_run.rs` — `codifide-run run <file.cod>` binary.
  Bridges to the Python parser via subprocess; prints JSON result
  to stdout (RI-3 resolved).

**`tests/test_rust_interpreter.py`** — conformance bridge. Runs
every example through both runtimes and compares JSON-deserialized
results. Clock-dependent programs are verified for no-error rather
than exact-value (the two runtimes call `clock.now` at different
instants). Programs that fail to parse in Python are skipped
(they're invalid Codifide; covered by the parser test suite).

## Test counts

- Python: **219 passing, 0 skipped** (was 216; +3 from the new
  conformance bridge tests).
- Rust canonical: **28 passing** (unchanged).
- Rust interpreter: **0 unit tests yet** — the conformance bridge
  is the test surface for now.

## Conformance bridge results

- Top-level examples: all pass.
- Assessment battery (7 programs): all pass.
- AI-generated examples (14 parseable of 15): all pass.
  (`is_even.cod` uses `%` operator and does not parse; skipped.)

## What the Sable audit findings look like now

| ID   | Severity | Status                                      |
|------|----------|---------------------------------------------|
| RI-1 | P2       | Resolved — f64 numerics, documented         |
| RI-2 | P2       | Resolved — Bottom as enum variant           |
| RI-3 | P1       | Resolved — JSON output format, bridge built |
| RI-4 | P3       | Open — EffectTrace exists; not yet tested   |
| RI-5 | P3       | Resolved — hint messages ported             |
| RI-6 | P2       | Resolved — static transitive check runs     |

RI-4 (effect trace in postconditions) remains open. The trace
accumulates correctly; the gap is that no test exercises a
postcondition that reads `io.stdout.tail` or similar. That is a
test-coverage gap, not an implementation gap.

## What is not yet done

- **Rust interpreter is not the default runtime.** Python is still
  the default. The version bump to 2.0.0 happens when the Rust
  interpreter passes all 216 tests and is set as the default.
- **No Rust parser.** The `codifide-run` binary calls `python3 -m
  codifide canonical` to parse `.cod` source. A Rust parser is a
  separate project; the bridge is the right architecture for now.
- **Imports not supported.** The Rust interpreter does not resolve
  imports through the symbol store. The current test suite does not
  exercise imports through the Rust runtime; this is a known gap.
- **Graph-native parallel evaluator.** Step 2 of v2-A. Not started.
  The sequential tree-walker must pass all tests first.

## What I'm not yet sure of

Whether the conformance bridge's clock-skip heuristic (`if
"clock.now" in source`) is the right long-term approach. It works
for the current examples but would miss a program that uses
`clock.now` in a way that doesn't affect the return value. A
better approach would be to mock the clock in both runtimes for
conformance testing. That is a future improvement.
