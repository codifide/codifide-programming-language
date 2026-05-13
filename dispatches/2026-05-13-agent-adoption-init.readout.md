# Agent Adoption Initiative — Opening Dispatch

**Date:** 2026-05-13
**Session:** Agent adoption initiative kickoff
**Persona:** Quill

## What this is

Codifide v1.0 shipped on 2026-05-11 and went public on 2026-05-13. The language is designed for agents. No real agent has yet adopted it in a non-trivial context. This dispatch opens the initiative to close that gap.

## What was decided

Three tracks:

**Track 1 — Real external agent case study**
Run the external model experiment deferred at v1.0. At least two models (GPT-4o, Gemini 2.5 Pro) in fresh sessions, given only the agent-facing docs and the capability manifest. Task: build a content-moderation pipeline using belief dispatch and first-class refusal. Document every failure and fix as paired dispatches. Sable audits each session.

**Track 2 — Adoption infrastructure**
- Stable manifest endpoint at `codifide.com/capability.json`
- `docs/AGENT_COOKBOOK.md` — top 10 failure modes mapped to correct forms
- Feedback dispatch template for agents to file observations
- `python3 -m codifide agent-quickstart` CLI command

**Track 3 — v2.0 roadmap driven by adoption findings**
The existing roadmap was written before any real adoption data. v2.0 priorities will be set after Track 1 findings are in.

## Spec location

`.kiro/specs/agent-adoption/` — requirements, design, tasks.

## Governance

Every session in this initiative produces paired Quill/Glyph dispatches. Sable audits at each track boundary. `dispatch-check` runs at every session close.

## Status

Initiative open. Track 1 is the first priority.
