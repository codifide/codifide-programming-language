# Codifide Agent Adoption Initiative — Requirements

## Overview

Codifide v1.0 is live and open source. The language is designed for agents, but no real agent has yet adopted it in a production or semi-production context. This initiative closes that gap — from "language exists" to "agents use it."

The goal is not to prove the language is perfect. It is to generate real evidence of what happens when agents encounter Codifide, document every friction point, and use those findings to drive v2.0.

---

## Requirements

### REQ-1: Real External Agent Case Study

**What:** Run the external model experiment that was deferred at v1.0. Hand the Codifide repo to at least two external AI agents (different models, fresh sessions) with only the agent-facing docs as context. Have each agent build a non-trivial working pipeline in Codifide. Document every failure, fix, and success.

**Why:** The v1.0 reviews (GPT-5.4, Gemini 2.5 Pro, Grok) were done before the ergonomics pass. The fresh-agent simulation was a self-simulation by Claude — not an independent test. Real external evidence is the only credible signal.

**Acceptance criteria:**
- At least 2 external model sessions completed
- Each session produces at least 3 working Codifide programs
- Every failure mode is documented with the exact error and the fix
- Results are published as paired Quill/Glyph dispatches
- Sable audits each session for findings the agent missed

**Scope:** The task given to each agent should be a realistic use case — not toy programs. Suggested: build a small content-moderation pipeline using belief dispatch and first-class refusal.

---

### REQ-2: Agent Adoption Infrastructure

**What:** Build the infrastructure that makes Codifide discoverable and usable by agents without human assistance.

**Sub-requirements:**

**REQ-2a: Stable manifest endpoint**
The capability manifest must be accessible at a stable public URL without requiring the agent to clone the repo. Target: `codifide.com/capability.json` and `codifide.com/capability.cbor`.

**REQ-2b: Agent cookbook**
A `docs/AGENT_COOKBOOK.md` that maps common agent intentions to actual Codifide syntax and primitives. Format: intention → pattern → working example. Covers the top 10 failure modes identified in the v1.0 reviews.

**REQ-2c: Feedback dispatch template**
A structured template at `dispatches/feedback/TEMPLATE.md` that any agent can fill in to report observations, failures, and suggestions. Quill/Glyph format. Sable reviews all feedback dispatches.

**REQ-2d: Agent quickstart script**
A single command that a fresh agent can run to verify their environment and write their first Codifide program: `python3 -m codifide agent-quickstart`. Outputs a working `.cod` file and its content hash.

**Acceptance criteria:**
- Manifest accessible at stable URL
- Cookbook covers all failure modes from v1.0 reviews
- Feedback template is used in at least one real agent session
- Quickstart command works in a clean environment

---

### REQ-3: v2.0 Scope Definition Driven by Adoption Findings

**What:** Use the findings from REQ-1 and REQ-2 to define the v2.0 language roadmap. v2.0 items should be prioritized by what agents actually need, not by what was planned before v1.0 shipped.

**Why:** The existing roadmap (effect inference, time-indexed types, Rust interpreter, RPC API) was written before any real agent adoption data existed. Some items may be wrong priorities.

**Acceptance criteria:**
- v2.0 roadmap updated after REQ-1 case study is complete
- Each v2.0 item is justified by at least one finding from the case study or adoption infrastructure work
- Items that are not justified by adoption evidence are explicitly deferred with a reason
- Sable audits the v2.0 roadmap for internal consistency

---

### REQ-4: Governance and Dispatch Discipline

**What:** Every piece of work in this initiative is journaled using the three-persona system.

- **Quill** produces human-readable readouts for every session
- **Glyph** produces paired YAML dispatches
- **Sable** audits every gate transition and every external agent session

**Why:** The dispatch system is the project's memory. An initiative this significant — the first real agent adoption work — must be fully documented.

**Acceptance criteria:**
- Every session in this initiative has a paired Quill/Glyph dispatch before it closes
- Sable files at least one audit per track
- `python3 -m codifide dispatch-check` exits 0 at the end of every session

---

## Out of Scope

- Building a hosted runtime or cloud service (v3.0 territory)
- Marketing or community building beyond the LinkedIn launch
- Changing the canonical form (requires a separate spec-change process per GOVERNANCE.md)
- Certifying any external agent as "Codifide-compatible" (no certification program exists yet)

---

## Success Definition

This initiative is successful when:

1. At least one external agent has built a working non-trivial Codifide program without human assistance
2. The failure modes from that session are documented and addressed
3. The v2.0 roadmap reflects real adoption evidence
4. The dispatch journal is complete and Sable has audited the work

---

*Spec version 1.0 — May 2026*
*Author: Douglas Jones + Claude*
*Governed by: GOVERNANCE.md*
