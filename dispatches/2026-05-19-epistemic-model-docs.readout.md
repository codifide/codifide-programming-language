# Epistemic Model Documentation

**Date:** 2026-05-19  
**Persona:** Kiro  
**Gate:** G0 (documentation, no code changes)

---

## What happened

Douglas conducted an adversarial review session with GPT-4o, using the
DecodeTheSign parking sign app as a case study. The review exposed how a
system designed with refusal-first principles can still produce dangerous
false positives through implementation drift — fallback logic, confidence
inflation, aggregate substitution, and silent coercion.

The session produced four documents that formalize CPL's epistemic safety
model and establish guardrails against the same drift patterns in CPL
implementations.

---

## What shipped

### 1. `docs/SEMANTIC_INVARIANTS.md` — The Constitutional Layer

Seven invariants that all CPL implementations must preserve:

- **Refusal Integrity** — unsafe states never silently coerce into conclusions
- **Confidence Provenance** — scores retain source lineage
- **Non-Independence Protection** — correlated evidence cannot inflate certainty
- **Ambiguity Preservation** — ambiguous states remain representable
- **Fail-Closed Semantics** — unknown states refuse rather than degrade
- **Intent Auditability** — intent remains inspectable through all layers
- **Confidence Calibration** — scores are not globally comparable without calibration

This is arguably the most important document in the project. It defines what
CPL *means* — not syntactically, but epistemically.

### 2. `rfcs/0001-formal-semantics-gaps.md` — What We Don't Yet Know

Six areas where CPL's specification is philosophically strong but formally
incomplete:

- Belief semantics (what IS a belief?)
- Confidence algebra (how do beliefs compose?)
- Refusal semantics (complete propagation rules for `bottom`)
- Ambiguity handling (representing underdetermination)
- Evidence provenance (tracking where confidence came from)
- Distributed evaluation (behavior under partial failure)

This RFC is healthy — it explicitly documents what's unresolved rather than
pretending the gaps don't exist.

### 3. `docs/IMPLEMENTATION_DRIFT.md` — The Warning

Five named drift patterns with real-world examples from the parking sign case:

- Permissive Fallbacks
- Confidence Inflation
- Silent Coercion
- Ambiguity Collapse
- Aggregate Substitution

Each pattern includes what it looks like, why it happens, and how CPL's
design mitigates it. This document is a review checklist for any system
built on CPL principles.

### 4. `docs/EPISTEMIC_MODEL.md` — The Design Target

Sketches the five epistemic states CPL should eventually represent:

- Certain(value) — ✅ implemented via `belief` + `believe`
- Ambiguous(possible_values) — ❌ not yet representable
- Refused(reason) — ✅ implemented via `bottom "reason"`
- Contradictory(evidence) — ❌ not yet representable
- Unknown — ⚠️ partially via bare `bottom`

This is the roadmap for CPL's type system evolution.

---

## Connection to existing work

The parking sign classifier (`examples/parking_sign.cod`, shipped 2026-05-17)
already demonstrates CPL's confidence gating and refusal patterns. These new
documents formalize *why* those patterns matter and *what happens when they
erode* — grounded in a real production failure from the same problem domain.

---

## What this means for CPL's trajectory

CPL's opportunity is not "a programming language with confidence scores."
It is "a language/runtime for epistemically safe computation." These documents
establish the formal foundation for that claim.

The strongest concepts in the project — refusal, uncertainty, ambiguity,
provenance, intent, confidence integrity, safe abstention — now have a
constitutional document protecting them from gradual erosion.

---

## Next steps (not yet scheduled)

- Map semantic invariants onto the existing evaluator/runtime code to identify
  where the implementation already satisfies or violates them
- Choose a formal framework for belief semantics (RFC 0001, area 1)
- Design the Ambiguity type (epistemic model gap)
- Add provenance metadata to `belief()` values
- Calibration framework for cross-domain confidence composition
