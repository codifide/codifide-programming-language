# Sable audit — Rust interpreter proposal (2026-05-12)

*By Sable. Gate: proposal review before implementation starts.*

## Scope

The proposal in
`dispatches/2026-05-12-rust-interpreter-proposal.readout.md`
proposes porting the Codifide evaluator from Python to Rust.
This audit probes the proposal for correctness, completeness,
and security-adjacent risks before implementation starts.

The proposal does not change the canonical form, the primitive
surface, or the capability manifest. It adds a second conforming
runtime and a conformance bridge. The audit focuses on:

1. Whether the semantics list is complete.
2. Whether the coexistence plan is safe.
3. Whether the conformance surface is adequate.
4. Whether the crate structure is sound.
5. Security-adjacent risks in the new runtime.

---

## Findings

### RI-1 (P2) — Integer semantics: Python is unbounded, Rust is not

**Finding.** Python's `int` is arbitrary-precision. Rust's `i64`
is not. The proposal does not address this. A Codifide program
that computes `pow(2, 100)` will produce a correct result in
Python and overflow silently (or panic in debug mode) in Rust.

**Evidence.** `codifide/runtime/primitives.py` registers `pow`
as `lambda b, e: _num(b) ** _num(e)`. Python's `**` on integers
is arbitrary-precision. Rust's `i64::pow` wraps or panics.

**Recommendation.** The proposal must specify the integer
semantics the Rust interpreter will use. Options:
- Use `f64` for all numeric literals (matches the current
  canonical form, which stores numbers as JSON numbers, which
  are `f64` in `serde_json`). This is the simplest path and
  matches what the canonical form already does.
- Use a big-integer crate (`num-bigint`). Correct but adds a
  dependency and a performance cost.
- Use `i64` with explicit overflow detection and a
  `PrimitiveError` on overflow. Correct for the current test
  suite; may diverge from Python on edge cases.

The proposal should pick one and document it. The conformance
bridge will catch divergence, but only if the test suite
exercises the edge cases.

**Disposition.** Blocking on proposal amendment. The proposal
must specify integer semantics before implementation starts.

---

### RI-2 (P2) — `Bottom` propagation: Rust has no singleton type

**Finding.** Python's `Bottom` is a singleton (`_BottomType`
with `__new__` returning the same instance). The interpreter
uses `x is Bottom` for identity checks throughout. Rust has no
singleton type; the proposal does not specify how `Bottom` is
represented.

**Evidence.** `codifide/runtime/interpreter.py` uses `if result
is not Bottom`, `if a is Bottom`, `return Bottom` throughout.
The Python `is` check is identity, not equality.

**Recommendation.** Represent `Bottom` as a variant of the
`Value` enum in Rust:

```rust
pub enum Value {
    Bottom,
    Concrete { payload: Payload, type_: String, conf: f64, ... },
    Belief { about: Box<Value>, conf: f64 },
}
```

This is the natural Rust representation and avoids the singleton
pattern entirely. The proposal should specify this explicitly.

**Disposition.** Non-blocking (the implementation will have to
solve this regardless), but the proposal should acknowledge it
so the implementer does not discover it mid-port.

---

### RI-3 (P1) — Conformance bridge: subprocess output format unspecified

**Finding.** The proposal says the Rust binary exposes a `run`
subcommand that "prints the result to stdout." It does not
specify the output format. The conformance bridge compares
output, but if the Rust binary prints `Value { payload: 42 }`
and the Python test expects `42`, the bridge will fail on every
test even when the semantics are correct.

**Evidence.** The proposal: "The Rust binary exposes a `run`
subcommand that accepts a `.cod` source file and prints the
result to stdout." No format specified.

**Recommendation.** The proposal must specify the output format
for the `run` subcommand. The simplest correct choice: print
the unwrapped payload as a Python `repr`-compatible string
(integers as decimal, strings quoted, booleans as `True`/`False`,
`None` as `None`, lists as `[...]`). This matches what the
Python test suite already expects from `run()`.

Alternatively, print JSON and have the conformance bridge
deserialize. This is more robust but requires the bridge to
know the expected type.

**Disposition.** Blocking on proposal amendment. The output
format must be specified before the conformance bridge can be
written.

---

### RI-4 (P3) — Effect trace: Rust interpreter has no equivalent

**Finding.** The Python interpreter maintains an `EffectTrace`
that records `stdout`, `clock_reads`, `model_calls`, etc.
Postconditions can reference `io.stdout.tail` and similar.
The proposal does not mention the effect trace.

**Evidence.** `codifide/runtime/primitives.py` `EffectTrace`
dataclass; `io_say` appends to `trace.stdout`; `clock_now`
appends to `trace.clock_reads`.

**Recommendation.** The Rust interpreter needs an equivalent
`EffectTrace` struct. The proposal should acknowledge this.
It is not a blocking issue for the initial port (the current
test suite does not test postconditions that reference the
trace directly), but it is a correctness gap if omitted.

**Disposition.** Non-blocking for the initial port. Document
as a known gap; close before the Rust interpreter becomes the
default.

---

### RI-5 (P3) — Hint messages: not mentioned in the proposal

**Finding.** The Python interpreter has a `_CALLABLE_HINTS`
table and `_UNBOUND_HINTS` table that produce human-readable
error messages for common agent mistakes. The proposal does not
mention these.

**Evidence.** `codifide/runtime/interpreter.py` lines 726–789.

**Recommendation.** The Rust interpreter should produce
equivalent hint messages. This is not a conformance issue (the
test suite does not test error message text), but it is a
usability issue if the Rust interpreter becomes the default and
agents lose the hints.

**Disposition.** Non-blocking. Document as a known gap; close
before the Rust interpreter becomes the default.

---

### RI-6 (P2) — `_check_transitive_effects`: static pass must run in Rust

**Finding.** The Python interpreter runs a static transitive
effect check at module load (`_check_transitive_effects`). The
proposal lists "effect-enforcement-transitive-static-pass" in
the semantics list but does not describe how it is implemented
in Rust. This is a security-adjacent surface: without the
static pass, a pure function can launder effects through an
impure callee.

**Evidence.** `codifide/runtime/interpreter.py`
`_check_transitive_effects` and `_check_transitive_effects`
call in `run()`.

**Recommendation.** The proposal should explicitly state that
the static transitive effect check runs at module load in the
Rust interpreter, before any candidate body executes. The
implementation must not defer this to runtime.

**Disposition.** Non-blocking (the proposal lists it), but the
implementation must not omit it. Flag for implementation review.

---

## Summary

| ID   | Severity | Status                        |
|------|----------|-------------------------------|
| RI-1 | P2       | Blocking — integer semantics  |
| RI-2 | P2       | Non-blocking — Bottom repr    |
| RI-3 | P1       | Blocking — output format      |
| RI-4 | P3       | Non-blocking — effect trace   |
| RI-5 | P3       | Non-blocking — hint messages  |
| RI-6 | P2       | Non-blocking — static pass    |

Two blocking findings (RI-1, RI-3). The proposal should be
amended to address them before implementation starts.

## Recommended proposal amendments

**RI-1 amendment.** Add to the proposal:

> Integer semantics: the Rust interpreter uses `f64` for all
> numeric values, matching the canonical form's JSON number
> representation. Programs that require arbitrary-precision
> integers are outside the current scope. The conformance bridge
> will catch any divergence from Python on the current test suite.

**RI-3 amendment.** Add to the proposal:

> The `codifide-run run` subcommand prints the unwrapped result
> payload to stdout in a format the conformance bridge can
> compare to Python's `run()` output: integers as decimal,
> floats as shortest round-trippable decimal, strings unquoted,
> booleans as `true`/`false`, `null` for None, lists as
> JSON arrays. The conformance bridge deserializes both sides
> as JSON for comparison.

## Gate decision

**Conditional pass.** The proposal is sound in structure and
scope. The two blocking findings (RI-1, RI-3) are specification
gaps, not design flaws. Amend the proposal to address them;
implementation may start after Douglas's approval of the amended
proposal.

The non-blocking findings (RI-2, RI-4, RI-5, RI-6) are
implementation notes. They do not block the proposal but must
be addressed before the Rust interpreter becomes the default
runtime.

