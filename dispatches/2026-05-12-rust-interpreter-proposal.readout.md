# Rust interpreter port — proposal (2026-05-12)

*By Quill. Proposal for Sable audit and Douglas's approval.*

## What this proposes

Port the Codifide evaluator from Python to Rust. The Python
reference implementation stays as the specification; the Rust
interpreter becomes the production runtime. The two coexist
during the port under a runtime-selection flag.

This is a new capability in the sense that it adds a second
conforming runtime. It does not change the language's canonical
form, its primitive surface, or its effect algebra. The
capability manifest hash does not move until the Rust interpreter
is the default and the Python interpreter is demoted to reference.

## Semantics the Rust interpreter must match

The Python interpreter in `codifide/runtime/interpreter.py` is
the spec. The Rust port must match it on every observable
behavior:

**Dispatch**
- Candidate guards evaluated in declaration order.
- Cost-based selection: among satisfied candidates, pick
  `min((cost_or_∞, declaration_index))`. Un-annotated candidates
  have effective cost `+∞` (i64::MAX in Rust).
- `DispatchError` when no candidate guard is satisfied.

**Effect enforcement**
- Primitive-call half: every primitive call's effect label must
  be in the enclosing definition's declared effect set.
- Transitive half: static pass at module load — callee effects
  must be a subset of caller effects across the whole call graph.
- Contract purity: pre/post/guard clauses run with effect budget
  `∅`. Any primitive call with a non-empty effect label inside a
  contract is an `EffectViolation`.

**Contracts**
- Preconditions evaluated before dispatch; `ContractViolation`
  on failure.
- Postconditions evaluated after dispatch, with `result` bound
  in the frame; `ContractViolation` on failure.
- Postconditions skipped when the result is `⊥` (refusal).

**Belief dispatch**
- `believe` block evaluates subject, binds `it`, evaluates arms
  top-to-bottom, returns first truthy arm's value.
- Falls through to `otherwise` if no arm matches.

**Inline conditional**
- `if cond then a else b` — short-circuit. Exactly one branch
  evaluates. Unlike guards, both branches are not evaluated
  before selection.

**First-class refusal**
- `⊥` (Bottom) is a value, not an exception.
- Primitives receiving `⊥` as an argument raise
  `BottomPropagationError` rather than a host panic.
- A top-level `⊥` that escapes `main` raises `RefusalError`.

**Recursion limit**
- Default depth 64. `RecursionLimitError` when exceeded.
- The limit is configurable at the interpreter level.

**All eight typed error classes**
- `CodifideError` (base)
- `ParseError`
- `EffectViolation`
- `ContractViolation`
- `DispatchError`
- `RefusalError`
- `RecursionLimitError`
- `PrimitiveError`
- `BottomPropagationError`

**Import resolution**
- Imports resolved through the symbol store at module load, not
  per call site.
- An imported symbol's effect set participates in the transitive
  check the same way a local definition's does.
- A module with imports and no store provided is a hard error at
  load time.

**All primitives in `codifide/runtime/primitives.py`**
- Arithmetic, comparison, logical (pure).
- Collections: `len`, `list`, `head`, `tail`, `reverse`,
  `append`, `contains_item`, `min_of`, `max_of`, `sum`,
  `is_sorted`, `is_permutation`.
- Strings: `contains`, `str`, `upper`, `lower`, `trim`,
  `starts_with`, `ends_with`, `replace`, `split`, `join`.
- Indexed: `slice`, `at`, `char_at`, `indexof`.
- Numeric: `abs`, `min`, `max`, `pow`, `floor`, `ceil`, `round`.
- Confidence: `conf`, `belief`.
- I/O: `io.say` (effect: `io.stdout`).
- Clock: `clock.now` (effect: `clock.read`).
- Model: `vision.classify`, `escalate` (effect: `model.vision`).
- Refusal helpers: `is_bottom`.
- Host bridges: `host_sorted`, `host_image`.

## How the two runtimes coexist

During the port:

- Python is the default runtime. `python3 -m codifide run` uses
  the Python interpreter.
- Rust is opt-in via `--runtime rust` flag (or environment
  variable `CODIFIDE_RUNTIME=rust`).
- The Rust interpreter is not the default until it passes all
  216 Python tests via the conformance bridge described below.

After the port passes all tests:

- Rust becomes the default. `python3 -m codifide run` invokes
  the Rust binary via subprocess.
- Python interpreter remains as the reference implementation
  under `--runtime python`.
- The version bump to `2.0.0` happens at this milestone.

## Conformance surface

The existing test suite in `tests/` is the conformance surface.
The Rust interpreter must pass every test that the Python
interpreter passes. The mechanism:

1. A new `tests/test_rust_interpreter.py` module runs the same
   programs as `tests/test_conformance.py` but invokes the Rust
   binary via subprocess and compares output.
2. The Rust binary exposes a `run` subcommand that accepts a
   `.cod` source file and prints the result to stdout.
3. The conformance bridge is the only new Python test file; all
   other tests remain Python-only until the Rust interpreter is
   the default.

## How the graph-native evaluator relates to the tree-walker

The graph-native parallel evaluator is a second step, not part
of this proposal. The relationship:

- Same semantics, different execution order for pure branches.
- The sequential tree-walker is the reference for the parallel
  evaluator the same way the Python interpreter is the reference
  for the Rust tree-walker.
- Parallelism is not observable from the language's perspective:
  a program that produces the same result sequentially must
  produce the same result in parallel. The effect algebra
  enforces this — two branches that share an effect must
  serialize, so their relative order is observable and must be
  preserved.

The parallel evaluator does not start until the sequential
tree-walker passes all tests. This is the mitigation for the
"porting a moving target" risk: the target is the test suite,
and the test suite is stable.

## Crate structure

The Rust interpreter lives in a new crate:
`crates/codifide-interpreter/`. It depends on
`codifide-canonical` for the AST types and canonical form, and
adds:

- `src/interpreter.rs` — the tree-walking evaluator.
- `src/primitives.rs` — the primitive registry.
- `src/errors.rs` — the eight typed error types.
- `src/value.rs` — `Value`, `Belief`, `Bottom`.
- `src/lib.rs` — public API.
- `src/bin/codifide_run.rs` — the `run` subcommand binary.

The `codifide-canonical` crate is not modified. The AST types
it already defines (`Expr`, `Definition`, `Module`, etc.) are
the shared data model.

## What this proposal does not include

- The graph-native parallel evaluator (second step, separate
  proposal).
- Effect-scoped concurrency model (third step, separate
  proposal).
- Benchmarks (fourth step, after Rust interpreter is the
  default).
- Any change to the canonical form, the primitive surface, or
  the capability manifest.

## Risk and mitigation

**Risk:** The Python interpreter has implicit behaviors the Rust
port must make explicit — Python's arbitrary-precision integers,
its exception model, its dynamic dispatch on `isinstance`.

**Mitigation:** The conformance bridge runs the full test suite
against both runtimes. Any divergence is a test failure, not a
silent semantic drift. The test suite is the authority.

**Risk:** The primitive set is large (49 primitives). Porting
them all before any test passes is a long feedback loop.

**Mitigation:** Port in layers. Start with the evaluator core
(Lit, Ref, Call, Bind, Seq, If, Believe, Bottom, Concat, Attr)
and the pure arithmetic primitives. Get the conformance bridge
running against a partial primitive set. Add primitives until
all tests pass.

## What I'm not yet sure of

Whether the conformance bridge (Python subprocess calling Rust
binary) is the right long-term architecture, or whether a
Python extension module (PyO3) would be better. The subprocess
approach is simpler and avoids a build-system dependency; the
extension approach would let the Rust interpreter be called
directly from Python tests without a subprocess round-trip.
The proposal uses subprocess for now; the architecture can be
revisited after the port passes all tests.

