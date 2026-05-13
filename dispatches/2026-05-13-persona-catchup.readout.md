# Persona Catch-up Sections Updated

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — pre-T1-2 preparation

---

## What happened

The catch-up sections in all three persona briefs were stale. They
described the project at v0/v0.1-dev — 19 passing tests, no CBOR, no
store, no Rust interpreter. The project is now at v1.0 (Python, shipped
2026-05-11) and v2.0 (Rust interpreter + parser, shipped 2026-05-12),
with 289 passing tests and a public GitHub repo.

This matters because the catch-up sections are what orient a persona
when invoked. Stale catch-up means wrong baseline — a Quill readout
written against v0 facts would misrepresent the project's actual state.

## What was updated

**Quill (`personas/quill.md`):**
- Replaced the v0 feature list with the full v1.0 + v2.0 shipped state
- Added the active initiative (Agent Adoption) as the current context
- Updated the honest-assessment paragraph: "working prototype" → "complete,
  tested, public v1.0 language"
- Preserved the role definition, voice, integrity rules, and signature move
  unchanged

**Glyph (`personas/glyph.md`):**
- Replaced the v0 test count and template reference with current facts
- Added the capability manifest hash, current test count, dispatch journal
  pointer, and most recent dispatch as the shape reference
- Added the active initiative state (T1-1 complete, T1-2 next)
- Added the dispatch discipline reminder (pairs required, dispatch-check)
- Preserved the role definition, form schema, integrity rules, and
  signature move unchanged

**Sable (`personas/sable.md`):**
- Replaced the v0.1-dev description with the full current surface
- Added the complete prior audit history with finding counts and resolution
  status
- Added known coverage gaps: conformance suite, Rust interpreter (no audit
  yet), parallel evaluator, agent-facing docs
- Added the active surface to audit next: `AGENT_TASK_SPEC.md`, Rust
  interpreter, any new interpreter surfaces
- Preserved the role definition, voice, integrity rules, severity scale,
  and signature move unchanged

## Assessment

The persona briefs are now accurate. The role definitions, voice, and
integrity rules were solid and needed no changes — those are timeless.
Only the catch-up sections were wrong, and they are now right.

What I'm not yet sure of: whether the Glyph dispatch schema in
`personas/glyph.md` needs updating to reflect the CBOR wire form being
available now. The schema still says "YAML for human spot-checkability;
the canonical wire form will be CBOR once the Codifide canonical store
exists." The store exists. That sentence may be ready to update.
