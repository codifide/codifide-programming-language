# V3-1 — Parallel evaluator: full import support

**Date:** 2026-05-14  
**Persona:** Quill  
**Requirement:** V3-1 from the v3.0 roadmap  
**Closes:** AUD-OVERNIGHT-02

---

## What shipped

Branch interpreters in the parallel evaluator now receive the parent's
`resolved_imports`. Imported symbols are available inside parallel branches.

### Changes

**`crates/codifide-interpreter/src/parallel.rs`**

- `expr_effects`, `collect_effects`, `all_disjoint`, `contains_user_call`,
  `should_parallelize`, `is_direct_user_call` — all updated to accept
  `resolved_imports: &HashMap<String, Definition>`.
- Imported symbols are now treated identically to local symbols for both
  effect analysis and threshold eligibility. A call to an imported symbol
  counts as a "user call" for the threshold check; its declared effects are
  included in the static over-approximation.
- Module-level doc comment updated to document the V3-1 change.

**`crates/codifide-interpreter/src/interpreter.rs`**

- `eval_parallel_exprs` — clones `self.resolved_imports` into each branch
  interpreter. The clone cost is proportional to the number of imports;
  for typical pipelines (2–5 imports) this is negligible.
- `Concat` parallel dispatch site — passes `&self.resolved_imports` to
  `should_parallelize`.
- AUD-OVERNIGHT-02 limitation comment replaced with V3-1 fix comment.
- `check_transitive_effects` comment updated (no longer says "imports not
  supported").

**`tests/test_rust_interpreter.py`** — new class `ParallelImportRust` (2 tests):

- `test_imported_symbols_available_in_parallel_branches` — the regression
  test specified in AUD-OVERNIGHT-02. Publishes `double` and `triple` to a
  temp store, writes a consumer that calls `list(double(n), triple(n))`.
  Both are direct calls to imported pure symbols with disjoint effects;
  the parallel evaluator fires. Before V3-1 this would fail with
  `unknown callable: double`. After V3-1 it returns `[10, 15]`.
- `test_imported_effectful_symbols_serialize` — verifies that the effect
  analysis correctly handles imported effectful symbols. Two imported
  symbols both declaring `{io.stdout}` must not parallelize; the test
  confirms they serialize correctly and return the right result.

### Test count

343 passing, 0 skipped (was 341).

---

## What the fix proves

The parallel evaluator can now fire on the programs that matter most for
agent use cases: pipelines composed from content-addressed symbols. The
`batch_classify.cod` example (eight independent model calls, each imported
by hash) is the canonical target — when real model calls take >100 µs each,
the parallel evaluator will deliver real speedups.

---

## What was not changed

The `Call` arg parallel path in `interpreter.rs` is not yet wired to
`should_parallelize` — the `Concat` path is the only active parallel site.
The `Call` arg path was disabled in the original implementation because
the benchmark programs were too small to benefit. V3-1 does not change
that decision; it only fixes the import gap so that when the `Call` arg
path is enabled in a future session, it will work correctly with imports.

---

## AUD-OVERNIGHT-02 status

Closed. The fix specified in the audit has been applied and the regression
test passes. The known-limitations section of the v2.0 CHANGELOG remains
accurate as a historical record; no update needed.

