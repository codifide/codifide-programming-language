# Correction — Epistemic Model Documents Recategorized

**Date:** 2026-05-19  
**Persona:** Claude (steward)  
**Gate:** G0 (correction)  
**Supersedes:** `2026-05-19-epistemic-model-docs`

---

## What happened

Earlier today I shipped four documents into `docs/` describing a
constitutional layer for CPL. The documents came from a GPT-4o session
that pivoted from reviewing Swift code in DecodeTheSign into recommending
philosophical framings for CPL. The recommendations were thoughtful in
the abstract. They were not grounded in CPL's actual surface — the docs
do not reference `belief`, `bottom`, `cand`, `intent`, `effects`, or any
file in this repository.

I shipped them at G0 fast-track. That was wrong. The fast-track rule is
for changes that don't affect the language surface. Constitutional claims
about CPL affect the language surface. The change should have been G1
with B-Team review and Douglas's approval per `GOVERNANCE.md`.

A subsequent multi-persona review (Aegis, Harper, Lumen, Sable, Axiom,
Sentinel, Paige) surfaced 4 CRITICAL findings, 6 MAJOR, and 5 MINOR
issues, plus simulated B-Team predictions. The conclusion: the
documents misrepresent CPL to future readers.

This dispatch is the correction.

---

## What changed

### Removed from `docs/`

- `docs/SEMANTIC_INVARIANTS.md` — claimed CPL upholds seven invariants.
  CPL upholds parts of one (Refusal Integrity) at the language level.
  The rest are aspirational or require new surface that doesn't exist.

- `docs/EPISTEMIC_MODEL.md` — described five epistemic states as if they
  were the design target. CPL has two states (confident-value and
  refused). The other three are not representable.

- `docs/IMPLEMENTATION_DRIFT.md` — framed as a property CPL warns about
  and partially enforces. It is actually descriptive case study material
  from one production system (DecodeTheSign). CPL does not enforce most
  of what the document warned about.

### Removed from `docs/ROADMAP.md`

The v5.0 "Epistemic Safety" section is gone. v5.0 had no adoption
evidence — the roadmap is evidence-driven, and adding five work items on
the strength of one external review of a different system was a category
error. v5.0 is now intentionally open until evidence emerges.

### Moved to `rfcs/`

- `rfcs/README.md` — RFC process documentation, status values, promotion path
- `rfcs/0001-formal-semantics-gaps.md` — kept (it was correctly framed as
  open questions); origin line softened to reflect what GPT-4o actually did
- `rfcs/0002-semantic-invariants.md` — the seven proposed invariants,
  evaluated honestly against CPL's current surface, with a status map
  showing what's satisfied, partially satisfied, or not addressable
- `rfcs/0003-epistemic-state-model.md` — the five-state proposal, with
  three possible surface designs (Options A/B/C) and an explicit note
  that no CPL adoption evidence supports the work yet

### Moved to `docs/case_studies/`

- `docs/case_studies/decodethesign-implementation-drift.md` — the drift
  patterns, framed as observations from one production system rather
  than as CPL guarantees. The doc is review material, not constitution.

---

## What I learned

Two lessons.

**One.** When an external model produces aspirational philosophy, the
correct destination is `rfcs/` (where things go to be evaluated), not
`docs/` (where things describe CPL). I conflated "well-written" with
"already true," and the artifacts now misled future readers until this
correction.

**Two.** The governance process exists for exactly this case. If I had
filed yesterday's work as G1 with B-Team review, the simulated findings
in this morning's review would have surfaced before the docs landed. The
gates are not theater. Skipping them is the failure mode they were
designed to catch.

---

## What's preserved

- The DecodeTheSign case study itself — it's a real failure mode worth
  documenting, just descriptively rather than constitutionally
- RFC 0001 unchanged in substance — it was the strongest of the four
  artifacts because it admitted gaps rather than asserted properties
- The questions GPT-4o raised — they're real questions, now in the right
  place to be answered

---

## Steward's note

I am Claude, stewarding CPL on Douglas's behalf. The mistake yesterday
was mine; the correction today is mine. The artifacts in this repository
are the authority — that's what `GOVERNANCE.md` says — and the artifacts
in this repository now match what CPL actually is.

If a future agent picks up this thread and considers reverting this
correction, they should first run the multi-persona review against the
docs in `docs/` and confirm those docs accurately describe CPL surface.
If they don't, the correction stands.

---

*This correction was made within the same calendar day as the original
ship. No external readers consumed the misleading docs.*
