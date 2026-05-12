# Graph-native parallel evaluator — proposal (2026-05-12)

*By Quill. Proposal for Sable audit and Douglas's approval.*

## What this proposes

Add a graph-native parallel evaluator to the Rust interpreter. The
sequential tree-walker remains the default for single-threaded
programs; the parallel evaluator activates automatically when the
static effect analysis determines that sub-expressions are safe to
run concurrently.

This delivers the v2-A design principle: "parallelism is default;
sequencing is declared."

## What can run in parallel

The AST has three sites where sub-expressions have no ordering
dependency between them:

1. **Call arguments.** `list(f(1), f(2), f(3))` — the three
   arguments are independent. If their effect sets are disjoint,
   they can evaluate concurrently.

2. **Concat parts.** `a ++ b ++ c` — the parts are independent.
   Same rule.

3. **Believe arms.** The condition/value pairs in a `believe` block
   are independent of each other (the subject evaluates first,
   sequentially). Arms with disjoint effects can evaluate
   concurrently.

What cannot run in parallel:
- `Seq` steps — ordered by definition; each step may depend on the
  previous.
- `Bind` — the body depends on the bound value.
- `If` — short-circuit; only one branch evaluates.
- Guard evaluation in dispatch — all guards evaluate before
  selection; already sequential.

## Effect constraint

Two parallel tasks that share an effect label must serialize. Two
tasks with disjoint effect sets can run freely. The effect algebra
already encodes this; the runtime just has to honor it.

**Static effect analysis:** `expr_effects(expr, module)` walks the
AST and returns the union of all effect labels reachable from an
expression. This is a conservative over-approximation (it includes
effects from all branches of an `If`, even though only one branch
evaluates). Conservative is correct: it may serialize some
expressions that could theoretically run in parallel, but it never
runs two expressions in parallel when they shouldn't be.

**Parallelism condition for a set of expressions:** all pairs have
disjoint effect sets. If any two expressions share an effect label,
the whole set evaluates sequentially (current behavior).

## EffectTrace under parallelism

The current `EffectTrace` is `&mut EffectTrace` passed through the
call stack — not thread-safe. For parallel evaluation:

1. Each parallel branch gets its own `EffectTrace`.
2. After all branches complete, traces are merged in **declaration
   order** (left-to-right in the source, not by thread completion
   time). This makes `io.stdout` output deterministic.
3. The merged trace is appended to the parent trace.

Merge order is the key correctness property: a program that calls
`io.say("a")` and `io.say("b")` in parallel must always output
`a` then `b` (or `b` then `a` — whichever the source order is),
never interleaved or reordered by thread scheduling.

**Consequence:** programs with `io.stdout` effects in parallel
branches will serialize (because `io.stdout` is a shared effect).
Only programs with disjoint effects — or pure programs — get
parallelism. This is correct and intentional.

## Implementation

**Rayon** for the thread pool. Rayon's `par_iter` / `join` API
maps cleanly onto the parallel-args pattern. No new dependencies
beyond Rayon.

**Parallel path:** when evaluating `Call { fn_, args }`:
1. Compute `expr_effects(arg_i, module)` for each arg.
2. Check all pairs for disjoint effects.
3. If all disjoint: evaluate args in parallel via `rayon::join` /
   `par_iter`, each with its own `EffectTrace`.
4. Merge traces in declaration order.
5. Evaluate the call with the merged args.
6. If any pair shares an effect: sequential (current behavior).

Same logic for `Concat { parts }`.

**Threshold:** only parallelize when there are ≥ 2 args AND the
total estimated work exceeds a threshold. Pure literal args
(`Lit`, `Ref`) are not worth spawning threads for. The threshold
is: at least one arg must contain a `Call` to a user-defined
function or a non-trivial primitive.

## Semantics preservation

The parallel evaluator must produce identical results to the
sequential evaluator for all programs. The conformance bridge
(70 tests) is the verification surface. A new test class
`ParallelSemantics` will run every conformance test with
parallelism forced on and verify results match.

The sequential evaluator remains the reference. If the parallel
evaluator ever disagrees, it is wrong.

## What this does NOT change

- The canonical form. No AST changes.
- The capability manifest. No new primitives or effects.
- The Python reference interpreter. Python stays sequential.
- The `--runtime python` fallback.
- Observable semantics for any program that passes the conformance
  suite.

## Benchmark targets

From the baseline measurements:

| Program           | Rust seq (µs) | Parallel opportunity |
|-------------------|---------------|----------------------|
| fizzbuzz          | 28.8          | 15 independent calls |
| pipeline          | 17.4          | 3 independent calls  |
| sort              | 23.6          | limited              |
| classify          | 5.9           | none (single chain)  |
| balanced_brackets | 98.3          | none (sequential)    |

Expected improvement: fizzbuzz and pipeline. No regression on
classify or balanced_brackets (they fall through to sequential).

## What I'm not yet sure of

Whether Rayon's thread-spawn overhead will eat the gains for small
programs like fizzbuzz (28.8 µs sequential). The threshold heuristic
is the mitigation; the benchmarks will tell us if it's calibrated
right. If parallel is slower than sequential for all current
programs, the threshold should be raised until it isn't.

