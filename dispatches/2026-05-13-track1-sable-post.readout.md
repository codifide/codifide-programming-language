# Track 1 Sable Audit — Post-Audit Resolution

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 1, Task T1-6 (post-audit)

---

## What happened

Sable filed seven findings across the three case study sessions. Two were
applied immediately. Five are tracked for future work.

---

## Applied fixes

**AUD-T1-03 (P1) — Rust parser from-import error message misleads.**
The error previously said: *"use `import <name> = sha256:<hex>` for direct
identity binding."* That suggestion doesn't solve the transitive dependency
problem — it just moves the failure one step later. Fixed: the error now says
to use `CODIFIDE_RUNTIME=python` and explains that individual imports don't
carry transitive dependencies.

**AUD-T1-05 (P3) — `main_refuse` test name misleading after spec fix.**
Renamed to `main_uncertain` in `docs/AGENT_TASK_SPEC.md`. Expected output
updated to `"uncertain"` (not `RefusalError`).

**AUD-T1-06 (P3) — No agent tested the escalate-to-human path.**
Added a third test message requirement to Program 3 in the task spec — one
that produces `"uncertain"` and routes to `"escalate-to-human"`.

---

## Deferred findings

**AUD-T1-01 (P2)** — `is_bottom` manifest entry has no caveat. Deferred:
requires a manifest schema change or a new `docs/CAPABILITY.md` caution
section. Tracked for Track 2 (adoption infrastructure).

**AUD-T1-02 (P2)** — Bind-before-when has no static detection. Deferred:
requires parser scope tracking, which is a non-trivial change. Tracked for
v2.0 roadmap.

**AUD-T1-04 (P3)** — `belief(...)` return type not enforced. Deferred:
design question — enforcement would break existing programs. Needs a dispatch
before any change. Tracked for v2.0 roadmap.

**AUD-T1-07 (P2/P0)** — `bottom`-adjacent primitive audit. No new P0 findings.
`is_bottom()` documentation gap is the only issue (see AUD-T1-01).

---

## 289 tests passing, 0 regressions.
