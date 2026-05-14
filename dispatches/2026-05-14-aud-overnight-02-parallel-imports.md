# Sable audit — AUD-OVERNIGHT-02: parallel evaluator import handling

*By Sable. Gate: severity rating and fix/accept decision before v3.0 parallel work begins.*  
*Date: 2026-05-14*

---

## Scope

The parallel evaluator in `crates/codifide-interpreter/src/interpreter.rs`
(`eval_parallel_exprs`) creates branch interpreters with `resolved_imports:
HashMap::new()`. This means imported symbols are not available inside parallel
branches. The gap is documented in the source with a `// Note:` comment and
tracked as AUD-OVERNIGHT-02. This audit rates the severity, characterises the
failure mode, and decides: fix before v3.0 or formally accept as a known
limitation.

---

## The gap — exact location

`interpreter.rs`, `eval_parallel_exprs`, inside the `rayon::scope` closure:

```rust
let mut branch_interp = Interpreter {
    module,
    max_depth,
    depth: current_depth,
    prims: build_default_registry(),
    trace: EffectTrace::fresh(),
    // Note: resolved_imports is not passed to branch interpreters.
    // Imported symbols are not available in parallel branches.
    // This is a known limitation (AUD-OVERNIGHT-02). If a parallel
    // branch calls an imported symbol, it will fail with
    // unknown_callable. Fix: pass resolved_imports here when the
    // parallel evaluator gains full import support.
    resolved_imports: HashMap::new(),
};
```

The Python interpreter has no parallel evaluator, so this gap is Rust-only.

---

## Failure mode

A program that:
1. Imports a symbol by content hash (`import f = sha256:...`), AND
2. Calls that symbol inside a `list(...)` or `++` expression that the
   parallel evaluator decides to parallelize

will fail at runtime with:

```
runtime error: unknown callable: "f"
```

The error is deterministic — it fires every time the parallel path is taken,
not intermittently. The sequential fallback path (which fires when
`should_parallelize` returns false) would succeed, because the sequential
`call()` method checks `self.resolved_imports` correctly.

---

## Severity assessment

### Is the parallel path currently reachable with imports?

The `should_parallelize` threshold requires **all args to be direct `Call`
nodes to user-defined functions** (`is_direct_user_call`). A user-defined
function is one found in `module.symbols` — the local module's symbol table.
Imported symbols are not in `module.symbols`; they are in `resolved_imports`.

Therefore: `is_direct_user_call` returns `false` for a call to an imported
symbol. `should_parallelize` returns `false`. The parallel path is **never
taken** when any arg is a call to an imported symbol.

This is the key finding. The gap is real but currently unreachable by
construction: the threshold that gates parallelism also excludes the case
that would expose the gap.

### Severity: P3 (low)

- **Not reachable today.** The threshold check prevents the parallel path
  from firing on imported-symbol calls. No program can currently hit this
  error through normal use.
- **Deterministic when reachable.** If the threshold were relaxed (e.g., to
  support imported-symbol parallelism in v3.0), the failure would be
  immediate and obvious — not a data race or intermittent failure.
- **Well-documented.** The source comment names the limitation and the fix
  path. The CHANGELOG v2.0 known-limitations section documents it. This
  audit was scheduled before v3.0 parallel work begins.
- **No security surface.** The gap cannot be exploited to bypass effect
  checks or access unintended symbols — it fails closed (unknown callable
  error), not open.

Downgrade from the initial "unknown severity" to **P3**. It is a latent
gap, not an active defect.

---

## Fix path

When v3.0 parallel work begins and the threshold is relaxed to support
imported-symbol calls in parallel branches, the fix is:

```rust
let mut branch_interp = Interpreter {
    module,
    max_depth,
    depth: current_depth,
    prims: build_default_registry(),
    trace: EffectTrace::fresh(),
    resolved_imports: resolved_imports.clone(),  // pass parent's imports
};
```

`resolved_imports` is a `HashMap<String, Definition>`. `Definition` derives
`Clone`. The clone cost is proportional to the number of imports — for the
current pipeline programs (3 imports), negligible. For programs with large
import sets, a shared `Arc<HashMap<...>>` would be preferable to avoid
repeated cloning.

The `eval_parallel_exprs` method signature would need to accept
`resolved_imports` as a parameter (or `Interpreter` would need to expose it
as a field accessible to the closure). The `rayon::scope` closure already
transmits `module` as a raw pointer; `resolved_imports` can be transmitted
the same way (it is immutable during parallel evaluation).

**Prerequisite:** before relaxing the threshold, add a regression test that:
1. Publishes a symbol to the store
2. Writes a module that imports it and calls it inside `list(...)`
3. Asserts the result is correct (not `unknown callable`)

This test will fail before the fix and pass after it, pinning the behavior.

---

## Effect check interaction

One subtlety: the transitive effect check (`check_transitive_effects`) runs
on the local module only. It does not walk into imported definitions. This
means a parallel branch that calls an imported effectful function would not
be caught by the static check — it would be caught at runtime by the effect
budget check in `call_with_vals`. This is the same behavior as the sequential
path. No new risk introduced by the fix.

---

## Decision

**Formally accept as P3 — no fix required before v3.0 planning.**

Rationale:
- The gap is unreachable by construction under the current threshold.
- The fix is straightforward and well-understood.
- The correct time to apply the fix is when the threshold is relaxed as
  part of v3.0 parallel work — not before, because fixing it now would
  add code that is never exercised and cannot be tested.
- The regression test described above should be written as part of the
  v3.0 parallel work spec, not now.

**Action item for v3.0 spec:** include "pass `resolved_imports` to branch
interpreters" and the regression test as explicit requirements when the
parallel evaluator threshold is relaxed.

---

## Summary

| Item | Finding |
|---|---|
| Gap location | `eval_parallel_exprs`, branch interpreter construction |
| Failure mode | `unknown callable` when imported symbol called in parallel branch |
| Currently reachable | No — threshold excludes imported-symbol calls |
| Severity | P3 (latent, not active) |
| Fix complexity | Low — clone `resolved_imports` into branch interpreter |
| Fix timing | At v3.0 threshold relaxation, not before |
| Decision | Formally accepted as P3; fix deferred to v3.0 parallel work |

