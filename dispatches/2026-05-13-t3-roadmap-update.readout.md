# Track 3 — v2.0 Roadmap Update

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 3, Tasks T3-1 through T3-4

---

## What happened

The v2.0 roadmap has been rewritten from scratch based on adoption evidence.
The old roadmap was written before any real agent adoption data existed. The
new one is justified item by item.

## What changed

**`docs/ROADMAP.md`** — complete rewrite:
- Shipped section: v1.0, v2.0 Shape A, and Agent Adoption Initiative all
  documented accurately
- v2.0 priorities: four items, each with evidence citation and acceptance
  criterion
- Deferred section: five items from the old roadmap explicitly deferred with
  reasons — no adoption evidence for any of them
- v3.0 territory: Moltbook integration, hosted runtime, certification

**`.kiro/specs/v2-language/`** — new spec opened:
- `requirements.md`: four requirements, each justified by adoption findings
- `tasks.md`: implementation tasks for each requirement

## The four v2.0 priorities

**P1 — RPC API.** The composition story is broken without it. Every agent
hit Program 5 friction. The fix is not more documentation — it's removing
the CLI layer entirely for agent-to-agent composition.

**P2 — Static bind-before-when detection.** One of three models hit it.
The other two avoided it by accident. The parser should catch it, not the
runtime.

**P3 — `from`-import in Rust parser.** The default runtime can't do
content-addressed composition. That's a significant gap for the language's
core value proposition.

**P3 — Manifest `docs` field.** Discoverability gap. An agent with only
the manifest can't find the cookbook.

## What was explicitly deferred

Effect inference, time-indexed types, editor integration, structural diff,
graph-native parallel runtime (beyond what shipped in v2.0 Shape A). None
of these have adoption evidence. The old roadmap listed them as priorities;
the new one doesn't.

## Assessment

The roadmap is now honest. It reflects what agents actually need, not what
was planned before any agent used the language. The RPC API is the right
P1 — it's the only item that would have prevented a failure across all three
Track 1 sessions.

What I'm not yet sure of: whether the RPC API should be a separate service
or an extension of the existing CLI. The design dispatch (V2-1-2) will
settle that.
