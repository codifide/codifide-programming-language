# B-Team Findings Applied — Post-GPT-5.4 Review

**Date:** 2026-05-14  
**Persona:** Quill  
**Scope:** Four findings from GPT-5.4 B-Team review applied to agent-facing docs

---

## What happened

The GPT-5.4 B-Team review produced four findings. All four were applied in
this session. RE-01 (AGENT_COOKBOOK HTTP workflow, deferred from the A-Team
review) was also completed.

---

## FIND-B1 — Direct-call `is_bottom` documented (AGENT_QUICKREF)

Added an explicit example showing that `is_bottom(f())` works as a direct-call
refusal check — no bind needed. The AGENT_QUICKREF previously only documented
the failure mode (bind then `is_bottom`). The working pattern is now shown
alongside it with a note that `f()` is called twice and the `believe` pattern
is preferred for expensive functions.

---

## FIND-B2 — Double-print behavior documented (AGENT_QUICKREF + AGENT_COOKBOOK)

Added a note to the AGENT_QUICKREF I/O section explaining that `io.say` prints
to stdout *and* returns the message, so programs that call `io.say` in `main`
print twice. Added cookbook entry #12 with the same explanation and two
alternatives for printing exactly once.

---

## FIND-B3 — Task spec confidence thresholds (no change needed)

The task spec was already correct. The `"uncertain"` confidence was updated to
0.75 in a prior session (pre-T1-4 fixes), and `main_refuse` was renamed to
`main_uncertain` with a note that `"hello world"` now returns `"uncertain"`
rather than refusing. The B-Team finding was a confirmation, not a new gap.

---

## FIND-B4 — Individual vs index imports clarified (AGENT_COOKBOOK entry #8)

Removed the stale note that "the Rust parser does not yet support from-import
syntax" (fixed in V2-3). Added a clear statement that both runtimes support
`from`-import as of v2.0. Added guidance on when individual imports are
sufficient (flat dependency chains) vs when the index pattern is needed
(deeper chains or bundled composition).

---

## RE-01 — AGENT_COOKBOOK HTTP workflow (deferred from A-Team review)

Added cookbook entry #11: "Program 5 via HTTP — the RPC API workflow." Covers
the full workflow: start the server, POST canonical forms for all three symbols
in the dependency chain, write `pipeline_composed.cod` with the returned hashes,
run it. Includes the Python one-liner alternative to `jq` and a pointer to
`docs/RPC_API.md` for the full endpoint reference.

---

## Test state

341 tests passing, 0 skipped, 0 failed.

---

## What's next

- New agent case study to validate adoption improvements (Relay's KPI) — the
  task spec and docs are now in their best state since v1.0
- Sable audit of parallel evaluator import handling (AUD-OVERNIGHT-02, known gap)
- v3.0 planning if adoption evidence warrants it

