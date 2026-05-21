# Pure-Call Memoization — Runtime Optimization

**Date:** 2026-05-17  
**Persona:** Quill  
**Gate:** G4 (Build and Verify) — interpreter change, HIGH risk classification

---

## What happened

Douglas identified that the `else if` chain in the parking sign classifier was
inelegant. Three options were proposed: (1) bind-then-dispatch with existing
candidates, (2) a `match` expression (new language surface), (3) pure-call
memoization so the graph-native pattern (multiple candidates each calling the
same function in their guard) becomes free.

Douglas chose Option 3. The language is young — invest in the runtime, not
new syntax.

---

## What shipped

**Pure-call memoization in the interpreter** (`codifide/runtime/interpreter.py`):

The interpreter now caches results of pure function calls within a single
top-level evaluation. A function with `effects {}` called with the same
arguments returns the cached result instead of re-evaluating.

### Implementation

- Added `_memo: Dict[tuple, Any]` to the `Interpreter` class
- Cache cleared at the start of each `invoke()` call (isolation between evaluations)
- Before evaluating a pure function, check `(fn_name, normalized_args)` in the cache
- After evaluation, store the result in the cache
- `_memo_key()` normalizes Codifide Values/Beliefs/Bottoms into hashable tuples
- Returns `None` for unhashable arguments (graceful degradation — skips caching)

### Safety guarantees

1. **Only pure functions are cached.** `defn.signature.effects == frozenset()` is the gate. The transitive effect check already guarantees a pure function cannot call an effectful one.
2. **Cache is evaluation-scoped.** Cleared at each `invoke()`. No stale results across calls.
3. **Bottom values are cached.** A function that refuses caches the refusal — consistent behavior.
4. **Unhashable args degrade gracefully.** If `_memo_key` can't build a key, the call proceeds without caching.

### What this enables

The parking sign classifier was refactored from:
```codifide
# Old: else-if chain (not graph-native)
sign_type <- classify_sign_type(gated)
if eq(sign_type, "NO_PARKING") then ...
else if eq(sign_type, "TIME_RESTRICTED") then ...
```

To:
```codifide
# New: each candidate calls classify in its guard (graph-native)
cand
  intent "no parking — clear prohibition"
  cost   10
  when   and(ne(gate_ocr(text, confidence), "LOW_CONFIDENCE"), eq(classify_sign_type(...), "NO_PARKING"))
  verdict_for_no_parking(...)
```

Each candidate is independent. Each has its own intent. The runtime evaluates
all guards (they're pure), and `classify_sign_type` is computed once regardless
of how many guards call it.

---

## Test results

13 new tests in `tests/test_pure_memo.py`:
- `MemoKeyTests` (7 tests): key construction, normalization, edge cases
- `PureMemoizationTests` (6 tests): end-to-end memoization behavior

Performance verification: `fib(20)` completes in 1ms (would be ~21,891 calls without memoization, 21 with).

Full suite: **474 tests passing**, 0 skipped, 0 regressions.

---

## Risk assessment

This is a HIGH-risk change (interpreter semantics). Mitigations:

1. **All 461 existing tests pass unchanged.** The memoization is invisible to correct programs.
2. **Only pure functions are affected.** Effectful functions are never cached.
3. **Cache isolation.** Each `invoke()` starts fresh — no cross-evaluation contamination.
4. **Graceful degradation.** Unhashable arguments skip caching entirely.
5. **The optimization is semantically transparent.** A pure function with the same inputs must produce the same output — that's what "pure" means. Caching doesn't change behavior, only performance.

---

## What I'm not yet sure of

Whether the Rust interpreter should implement the same memoization. The Python
reference is authoritative for semantics, and since memoization doesn't change
observable behavior, the Rust runtime could omit it without conformance issues.
But if the Rust runtime is used for performance-sensitive workloads, it would
benefit from the same optimization. Decision deferred until the Rust interpreter
is feature-complete.
