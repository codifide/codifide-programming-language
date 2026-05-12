# Sable audit — parallel evaluator proposal (2026-05-12)

*By Sable. Gate: proposal review before implementation starts.*

## Scope

The proposal in
`dispatches/2026-05-12-parallel-evaluator-proposal.readout.md`
proposes adding a graph-native parallel evaluator to the Rust
interpreter. This audit probes for correctness, safety, and
semantic-preservation risks.

---

## Findings

### PE-1 (P1) — EffectTrace merge order must be enforced, not assumed

**Finding.** The proposal says traces are merged "in declaration
order." But Rayon's parallel execution does not guarantee completion
order. If the merge step uses the order in which threads finish
rather than the order in which args were declared, `io.stdout`
output will be non-deterministic.

**Evidence.** Rayon's `par_iter` collects results in input order
when using `collect()`, but `join` returns results in the order
the closures complete. The proposal does not specify which Rayon
API is used.

**Recommendation.** Use `rayon::iter::IndexedParallelIterator`
(e.g., `par_iter().enumerate().collect::<Vec<_>>()`) which
preserves input order in the output. Explicitly document that
the merge step iterates the collected results in index order,
not completion order. Add a test that verifies `io.say` output
order is preserved under parallel evaluation.

**Disposition.** Blocking on implementation note. The proposal
should specify the Rayon API and the merge order guarantee.

---

### PE-2 (P2) — Conservative effect analysis may miss dynamic dispatch

**Finding.** The proposal's `expr_effects` is a static
over-approximation. For a `Call` to a user-defined function, it
includes all effects declared in that function's signature. This
is correct for direct calls. But for a `Call` to a function that
dispatches to different candidates with different effect sets, the
static analysis uses the declared signature (which is the union of
all candidates' effects), not the runtime-selected candidate's
effects. This is conservative and correct — it may serialize
expressions that could theoretically run in parallel — but it
should be documented explicitly.

**Recommendation.** Document in the implementation that
`expr_effects` uses declared signature effects, not runtime-
selected candidate effects. This is the correct conservative
choice; note it so future maintainers don't "optimize" it to
use runtime effects (which would be unsound).

**Disposition.** Non-blocking. Documentation note.

---

### PE-3 (P1) — Recursion depth counter is not thread-safe

**Finding.** The `Interpreter` struct has a `depth: usize` field
that is incremented/decremented on every function call. Under
parallel evaluation, multiple threads would share the same
`Interpreter` — or each thread would have its own interpreter
with its own depth counter. The proposal does not specify which.

If threads share one interpreter, `depth` is a data race.
If each thread has its own interpreter, the depth counters are
independent and a program could exceed the global recursion limit
by spawning threads.

**Evidence.** `Interpreter::push_depth` and `pop_depth` mutate
`self.depth`. The parallel path must either (a) give each thread
its own interpreter with its own depth counter, or (b) use an
atomic for the shared counter.

**Recommendation.** Each parallel branch gets its own
`Interpreter` instance with its own depth counter, initialized
to the parent's current depth. This preserves the recursion
limit semantics: a parallel branch that recurses deeply still
hits the limit. The parent's depth counter is not affected by
parallel branches (they are independent call stacks).

**Disposition.** Blocking on implementation note. The proposal
must specify how depth is handled under parallelism.

---

### PE-4 (P2) — Threshold heuristic is unspecified

**Finding.** The proposal says "only parallelize when there are
≥ 2 args AND the total estimated work exceeds a threshold" but
does not define the threshold. An unspecified threshold means
the implementation can choose anything, including "always
parallelize" (which would be wrong for trivial expressions) or
"never parallelize" (which would make the feature a no-op).

**Recommendation.** Define the threshold concretely in the
implementation: parallelize a set of args if and only if at
least one arg contains a `Call` to a user-defined function.
Pure expressions (`Lit`, `Ref`, `Attr` on a local, `Concat`
of literals) are not worth spawning threads for. This is
measurable and testable.

**Disposition.** Non-blocking. Implementation should document
the chosen threshold.

---

### PE-5 (P3) — Believe arms parallelism is lower priority

**Finding.** The proposal includes `Believe` arms as a
parallelism site. In practice, `believe` blocks are used for
confidence dispatch — the arms are condition/value pairs where
the condition is typically a pure comparison (`ge(conf(it), 0.9)`)
and the value is a simple expression. The parallelism gain is
likely negligible and the implementation complexity is non-trivial
(the subject must evaluate first, then arms can parallelize, but
the first truthy arm wins — which requires careful handling).

**Recommendation.** Defer `Believe` arm parallelism to a
follow-up. Focus the initial implementation on `Call` args and
`Concat` parts, which are the high-value sites identified in
the benchmark analysis.

**Disposition.** Non-blocking. Scope reduction recommendation.

---

## Summary

| ID   | Severity | Status                                    |
|------|----------|-------------------------------------------|
| PE-1 | P1       | Blocking — merge order must be enforced   |
| PE-2 | P2       | Non-blocking — documentation note         |
| PE-3 | P1       | Blocking — depth counter under threads    |
| PE-4 | P2       | Non-blocking — threshold must be defined  |
| PE-5 | P3       | Non-blocking — defer Believe parallelism  |

Two blocking findings (PE-1, PE-3). Both are implementation
constraints, not design flaws. Address them in the implementation.

## Gate decision

**Conditional pass.** The proposal is sound in design. The two
blocking findings are implementation constraints that must be
honored:

- PE-1: use indexed parallel collection to preserve declaration
  order in trace merge.
- PE-3: each parallel branch gets its own `Interpreter` instance
  initialized with the parent's current depth.

Implementation may start under Douglas's approval with these
constraints in force.

