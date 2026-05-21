# RFC 0002 — Proposed Semantic Invariants

**Status:** Draft  
**Author:** Douglas Jones (with material from a GPT-4o session, May 2026)  
**Date:** 2026-05-19  
**Origin:** GPT-4o review session that pivoted from a DecodeTheSign Swift code review into recommendations for CPL. The session was not given (or did not consume) CPL's specification or implementation. This RFC carries the recommendations into the project's review process, where they can be evaluated against CPL's actual surface.

---

## Summary

This RFC proposes seven invariants that CPL implementations should preserve.
The invariants are aspirational — most are not yet enforced by the language
or the runtime. The proposal is to evaluate which of them CPL already upholds,
which are reachable with current surface, and which require new mechanisms.

This document is **not** the language's constitution. It is a proposal that,
if accepted, would inform future spec work.

---

## Proposed Invariants

### 1. Refusal Integrity

> Unsafe states must never silently coerce into executable conclusions.

**CPL surface today:** Partial. `bottom` is first-class. `believe` blocks
require an `else => ...` arm. `RefusalError` is raised when `bottom` escapes
unhandled. So at the language level, refusal cannot be silently dropped at
binding boundaries.

**Gap:** The invariant is about programs that would silently coerce refusal
into success at the application layer. CPL the language can be used to
preserve refusal, but it cannot prevent a programmer from explicitly
handling `bottom` and returning a permissive value. That's a coding
discipline issue, not a language enforcement issue, unless we add new
mechanisms (e.g., a `nocoerce` annotation).

---

### 2. Confidence Provenance

> Confidence values must retain source lineage and dependency relationships.

**CPL surface today:** Not satisfied. `belief(value, confidence)` carries a
float. There is no source attribution and no dependency tracking.

**Gap:** Adopting this invariant requires new surface. Options to evaluate:
- Extend `belief()` to take a third argument (provenance metadata)
- Add a separate `provenance(belief, source)` primitive
- Make provenance a parser-level annotation on `belief()` calls

None of these are scheduled. They would be v5+ work conditional on adoption
evidence.

---

### 3. Non-Independence Protection

> Dependent evidence must not increase certainty as if independent.

**CPL surface today:** Not addressable. CPL has no mechanism to model
dependency between beliefs because beliefs don't carry source identity.

**Gap:** Depends on Invariant 2 being implemented first.

---

### 4. Ambiguity Preservation

> Ambiguous states must remain representable and distinguishable from refusal.

**CPL surface today:** Not satisfied. CPL has confident-value (`belief(...)`)
and refusal (`bottom`). It does not have a representation for "one of these
N values, cannot determine which."

**Gap:** Adopting this invariant requires either a new type/primitive or a
convention for encoding ambiguity in existing `belief()` shapes (e.g.,
`belief([a, b], 0.5)` as ambiguity, vs. `belief(a, 0.5)` as low confidence —
which is an overload of meaning that would need careful spec work).

---

### 5. Fail-Closed Semantics

> Unknown or malformed semantic states must refuse rather than downgrade.

**CPL surface today:** Mostly satisfied. The interpreter raises typed errors
for malformed input (`ParseError`, `EffectViolation`, `BottomPropagationError`).
The language has no concept of "downgrade" because it has no fallback
behavior at the runtime level.

**Gap:** This invariant is more about programs and implementations built on
CPL than about CPL itself. Useful as a review checklist; not a property the
language enforces.

---

### 6. Intent Auditability

> Intent declarations must remain inspectable and eventually machine-checkable.

**CPL surface today:** Partially satisfied. `intent` is mandatory on every
definition. It survives canonical-form serialization. It is preserved
through content addressing.

**Gap:** Intent strings are not yet machine-checkable. The "machine-checkable"
half of the invariant is aspirational. Inspectability already holds.

---

### 7. Confidence Calibration

> Confidence values are not globally meaningful unless explicitly calibrated.

**CPL surface today:** Not addressed. CPL treats confidence as a bare float.
There is no calibration framework, no domain typing, no comparison guard
between heterogeneous confidence sources.

**Gap:** Adopting this invariant requires new surface. Not scheduled.

---

## Status Map

| Invariant | CPL today | Gap |
|---|---|---|
| 1. Refusal Integrity | Partial (language level) | Application-layer is programmer discipline |
| 2. Confidence Provenance | Not satisfied | Needs new surface |
| 3. Non-Independence Protection | Not addressable | Depends on #2 |
| 4. Ambiguity Preservation | Not satisfied | Needs new type or convention |
| 5. Fail-Closed Semantics | Mostly satisfied (at runtime) | Is review material, not enforcement |
| 6. Intent Auditability | Partially satisfied | Machine-checkability is future work |
| 7. Confidence Calibration | Not addressed | Needs new surface |

---

## Open Questions

1. Should any of these invariants be promoted to specification immediately?
   Refusal Integrity (#1) at the language level already holds — the spec
   could state this property explicitly and add conformance tests. The
   others would commit the project to surface work without adoption evidence.

2. Is it valuable to publish this RFC as a "we know we don't fully satisfy
   these" document, or does that mislead readers about CPL's current
   guarantees? The discipline question.

3. Is "Confidence Provenance" the right name for what's wanted, or is it
   really "Evidence Lineage"? Provenance has a specific meaning in data
   systems that may or may not transfer.

4. Do these belong in a single RFC, or should they be split into seven
   separate RFCs that can be accepted/rejected independently?

---

## Decision

Pending. This RFC is filed for review.

---

*RFC version: 1.0 (draft)*
*Supersedes: docs/SEMANTIC_INVARIANTS.md (May 19, 2026 — withdrawn for being premature)*
*Governed by: GOVERNANCE.md*
