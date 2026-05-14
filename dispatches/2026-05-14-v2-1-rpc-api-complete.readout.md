# RPC API Complete — V2-1 Gate (V2-1-7)

**Date:** 2026-05-14  
**Persona:** Quill  
**Tasks:** V2-1-6 (acceptance test), V2-1-7 (this dispatch)

---

## What happened

The RPC API is complete. All six V2-1 tasks are done. The acceptance
criterion is met.

---

## The acceptance criterion

REQ-V2-1 required: "An agent can complete Program 5 of
`docs/AGENT_TASK_SPEC.md` using only HTTP requests — no CLI, no
`CODIFIDE_RUNTIME=python`."

`tests/test_rpc_program5.py` proves this. Eight tests, all passing:

- Store starts empty — no CLI pre-seeding
- `classify_content`, `moderate`, and `route_message` published via
  `POST /symbols` (canonical CBOR)
- All three retrieved via `GET /symbols/<id>` and verified
- `pipeline_composed.cod` written using the HTTP-returned hashes
- All three routing paths verified: blocked, approved, escalate-to-human
- `/imports` endpoint shows no missing dependencies
- Idempotent publish confirmed

---

## One thing learned during V2-1-6

The transitive dependency problem is real and structural. `route_message`
calls `moderate`, which calls `classify_content`. When `route_message` is
stored as a single-symbol unit, its dependency on `moderate` is not
carried with it. The composed program must import all three symbols
explicitly.

This is not a bug — it is the correct behavior for a content-addressed
store. Each symbol is an independent unit. The composed program declares
its full dependency graph in its imports table. The `/imports` endpoint
makes this graph inspectable.

What this means for agents: Program 5 requires importing the full
transitive closure, not just the top-level symbol. The `AGENT_COOKBOOK.md`
entry on content-addressed composition should be updated to reflect this.
Relay owns that update.

---

## What's next

V2-1-8: Sable audits the RPC API surface. Then V2-2 (static
bind-before-when detection).

---

## What I'm not yet sure of

Whether the `/imports` endpoint should resolve transitively (returning
the full closure) or just one level deep (as currently implemented).
The current behavior is one level. For the Program 5 use case, one level
is sufficient because the agent constructs the composed program manually.
A future RPC client that wants to auto-resolve the full graph would need
transitive resolution. Deferred to V2-1-8 for Sable to flag if she
considers it a gap.
