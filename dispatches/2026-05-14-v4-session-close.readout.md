# Session Close — v4.0

**Date:** 2026-05-14  
**Persona:** Quill

---

## Session summary

Started from the question: "Is this language actually usable in the wild?"
The honest answer identified four gaps. All four became v4.0 requirements.
Three shipped in this session.

**Shipped:**
- V4-1: Runtime type enforcement (TypeViolation, 20 tests)
- V4-2: Standard library — file I/O, HTTP, JSON, date arithmetic (44 tests)
- V4-3: Public registry documentation (docs/REGISTRY.md)
- G0 + G1 specs for v4.0 (.kiro/specs/v4-language/)
- publicsite-rules.md: version sync rules added
- 01-governance-gates.md: G5 publicsite checklist tightened
- 04-adversarial-review.md: Sable publicsite sync checklist (PS-1 through PS-6)
- dispatch-check: publicsite sync checks wired in (PS-1, PS-3)
- publicsite updated to v4.0 (capability files, version stat, announcement section)

**Deferred:**
- V4-4: Network-safe server — no adoption evidence

**Test count:** 450 passing, 0 skipped.

**dispatch-check:** exits 0.

## What I'm not yet sure of

Whether the session produced enough adoption signal to justify a v5.0 roadmap,
or whether the right next step is to let v4.0 run in the wild and gather evidence.
