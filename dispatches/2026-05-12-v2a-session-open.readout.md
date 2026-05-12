# v2-A session open — Rust interpreter port (2026-05-12)

*By Quill.*

v1 shipped on 2026-05-11. 216 Python tests, 28 Rust tests, zero
skipped, every known P0/P1 closed. The canonical form is stable,
the authoring surface has been adversarially probed, and the
language does what it says on the tin.

The user chose Shape A.

## What Shape A is

Shape A is the claim that Codifide is fast enough to actually use.
v1's runtime is a tree-walking interpreter in Python. It is correct.
It is not fast. The seven design principles include "parallelism is
default; sequencing is declared." v1 does not deliver on that. v2-A
does.

The scope, in order:

1. **Rust interpreter port.** The whole evaluator — not just the
   canonical form. Python stays as the spec; Rust becomes the
   production runtime. The two coexist during the port: Python is
   the default until the Rust interpreter passes all tests, then
   Rust becomes the default and Python becomes the reference.

2. **Graph-native parallel evaluator.** After the sequential
   tree-walker port passes all tests, the second step is
   parallelizing at the node level. Independent branches in the
   dataflow graph run concurrently; branches that share an effect
   serialize. The effect algebra already tells us what is safe.

3. **Effect-scoped concurrency model.** Two branches sharing
   `io.stdout` must serialize. Two branches with disjoint effect
   sets can run in parallel. The runtime honors the effect algebra
   at execution time, not just at static-check time.

4. **Benchmarks as first-class citizens.** Every example gets a
   performance fixture. Regressions are regressions.

## What this session does first

Governance requires a proposal + Sable audit + Douglas's approval
before implementation starts on a new capability of this scope.
This session files the proposal. Implementation starts when the
proposal is approved.

The proposal is in
`dispatches/2026-05-12-rust-interpreter-proposal.readout.md` and
its paired YAML. Sable's audit is in
`dispatches/2026-05-12-rust-interpreter-audit.md`.

## Baseline at session open

- Python: 216 passing, 0 skipped.
- Rust canonical: 28 passing.
- Capability manifest:
  `sha256:23fdde779caebc2c471ade0e1c407422d044e2e0f1adc7e59a189325deccd27d`
- Nothing in flight from the previous session.

## What I'm not yet sure of

Whether the sequential tree-walker port will surface semantic
edge cases the Python reference handles implicitly — Python's
dynamic dispatch, its exception model, and its integer semantics
all do work the Rust port will have to do explicitly. The
conformance surface is the test suite; the question is whether
the test suite is complete enough to catch the gaps.

