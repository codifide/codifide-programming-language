# Sable Audit — v2.0 Roadmap

**Date:** 2026-05-13  
**Persona:** Sable  
**Scope:** `docs/ROADMAP.md`, `.kiro/specs/v2-language/`  
**Initiative:** Agent Adoption — Track 3, Task T3-5

---

## Audit scope

The v2.0 roadmap and the v2-language spec were written in one pass based on
adoption findings. This audit checks internal consistency, evidence claims,
and whether the acceptance criteria are testable.

---

## Findings

### AUD-T3-01 (P2) — REQ-V2-1 acceptance criterion is not independently verifiable

**What:** The RPC API acceptance criterion says "an agent can complete Program
5 of `docs/AGENT_TASK_SPEC.md` using only HTTP requests." But
`AGENT_TASK_SPEC.md` was written for CLI-based sessions. It does not describe
an HTTP-based workflow. An agent following the spec cannot verify the RPC API
criterion without a separate HTTP task spec.

**Fix:** When V2-1-1 (`docs/RPC_API.md`) is written, add an HTTP-based
variant of Program 5 to the task spec, or write a separate
`docs/AGENT_TASK_SPEC_RPC.md`. The acceptance criterion should reference a
concrete, runnable test.

**Severity:** P2 — the criterion is correct in intent but not independently
verifiable as written.

---

### AUD-T3-02 (P2) — REQ-V2-2 defers removal of the runtime hint

**What:** The tasks list says "remove runtime hint (now redundant with static
detection)" as V2-2-4. But the runtime hint was added specifically because
the parser doesn't catch bind-before-when. If V2-2 ships, the hint becomes
redundant. If V2-2 is deferred or partially shipped (Python parser only, not
Rust), the hint is still needed for the Rust runtime.

**Fix:** V2-2-4 should be conditional: remove the runtime hint only after
both Python and Rust parsers catch bind-before-when statically (V2-2-2 and
V2-2-5 both complete). The tasks list should reflect this dependency.

**Severity:** P2 — removing the hint prematurely would regress the Rust
runtime user experience.

---

### AUD-T3-03 (P3) — "Deferred" section mixes two categories

**What:** The roadmap's deferred section lists items with "no adoption
evidence" alongside "graph-native parallel runtime (beyond v2.0 Shape A)"
which has a different reason — it's deferred until the RPC API is in place,
not because of missing evidence. These are different kinds of deferrals.

**Fix:** Split the deferred section into two: "No adoption evidence" and
"Blocked on other v2.0 work." The distinction matters for prioritization in
future sessions.

**Severity:** P3 — cosmetic, but the distinction is real.

---

### AUD-T3-04 (P3) — v2.0 spec has no design document

**What:** `.kiro/specs/v2-language/` has `requirements.md` and `tasks.md`
but no `design.md`. The RPC API in particular needs a design dispatch before
implementation begins — endpoint shape, auth model, error responses, and
whether it's a separate service or a CLI extension are all open questions.

**Fix:** V2-1-2 (design dispatch) is already in the tasks list. This finding
confirms it should be the first task executed, not deferred.

**Severity:** P3 — the spec is incomplete but the gap is acknowledged.

---

## What I did not test

- Whether the four v2.0 acceptance criteria are achievable with the current
  codebase as a starting point. No implementation work was probed.
- Whether the Rust parser's architecture supports scope tracking for
  bind-before-when detection without a major refactor.
- Whether the RPC API design (separate service vs CLI extension) has
  implications for the content-addressed store's concurrency model.

---

## Overall assessment

The roadmap is internally consistent and evidence-justified. The four
priorities are the right four. The deferred items are correctly deferred.
The two P2 findings are fixable in the task list without changing the
requirements. The roadmap is ready to execute against.
