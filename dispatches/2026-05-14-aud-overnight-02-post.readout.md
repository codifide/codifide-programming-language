# AUD-OVERNIGHT-02 — parallel evaluator import handling: closed

**Date:** 2026-05-14  
**Persona:** Quill  
**Audit:** `dispatches/2026-05-14-aud-overnight-02-parallel-imports.md`

---

## What happened

Sable audited the parallel evaluator's import handling gap (AUD-OVERNIGHT-02).
The gap was documented in the Rust source and the v2.0 CHANGELOG known-limitations
section. This audit was the prerequisite for v3.0 parallel work.

## Key finding

The gap is **currently unreachable by construction.** The `should_parallelize`
threshold requires all args to be direct calls to symbols in `module.symbols`
(the local module's symbol table). Imported symbols live in `resolved_imports`,
not `module.symbols`, so `is_direct_user_call` returns false for them.
`should_parallelize` returns false. The parallel path never fires on
imported-symbol calls.

This means: no program can currently hit the `unknown callable` error through
the parallel path. The gap is latent, not active.

## Severity: P3

Downgraded from "unknown" to P3. Not reachable, deterministic when reachable,
well-documented, fails closed. No security surface.

## Decision: formally accepted, fix deferred to v3.0

The fix is straightforward — clone `resolved_imports` into branch interpreters.
The correct time to apply it is when the threshold is relaxed as part of v3.0
parallel work. Fixing it now would add untestable code.

The v3.0 parallel work spec must include:
1. Pass `resolved_imports` to branch interpreters when threshold is relaxed.
2. Regression test: import a symbol, call it inside `list(...)`, assert correct result.

## Gate: cleared

AUD-OVERNIGHT-02 is formally closed. v3.0 planning may proceed.

