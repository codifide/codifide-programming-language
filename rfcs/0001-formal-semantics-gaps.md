# RFC 0001 — Formal Semantics Gaps in CPL

**Status:** Open  
**Author:** Douglas Jones  
**Date:** 2026-05-19  
**Origin:** Discussion with GPT-4o that surfaced the question of whether CPL's semantics are formal enough to support safe composition. The questions in this RFC are open regardless of where they came from — they apply to CPL as written today.

---

## Problem

The Codifide Programming Language specification expresses strong epistemic goals
— refusal-first semantics, confidence-gated dispatch, first-class uncertainty —
but lacks fully formalized semantics for several critical areas. Without formal
definitions, implementations will diverge, and the safety properties CPL claims
to guarantee cannot be verified.

This RFC documents the known gaps and establishes a path toward formal
specification sufficient to prevent unsafe implementation drift.

---

## Key Missing Areas

### 1. Belief Semantics

**Current state:** `belief(value, confidence)` wraps a value with a float.
`conf(x)` reads it. `believe` dispatches on threshold comparisons.

**What's missing:**
- What is a belief formally? Is it a probability, a fuzzy logic membership, or
  an evidence aggregation score?
- What are the composition rules when beliefs interact?
- Can beliefs be nested? What does `belief(belief(x, 0.9), 0.8)` mean?
- Is confidence monotonically decreasing through composition, or can it
  increase?

**Risk without formalization:** Different implementations interpret confidence
differently, making cross-system composition unsafe.

---

### 2. Confidence Algebra

**Current state:** Confidence is a float between 0.0 and 1.0. Comparison
operators (`ge`, `lt`) gate on it. No composition rules exist.

**What's missing:**
- How confidence composes across function call boundaries
- Whether confidence is monotonic or bounded under composition
- Whether correlation between evidence sources invalidates additive composition
- Rules for confidence under branching (if both branches have confidence, what
  confidence does the result carry?)
- Whether `bottom` has a confidence (is it 0.0, or is it categorically
  different from low confidence?)

**Risk without formalization:** Systems that compose beliefs from multiple
sources will produce numerically precise but epistemically meaningless scores.

---

### 3. Refusal Semantics (`bottom`)

**Current state:** `bottom` is first-class. It propagates through binds.
`RefusalError` is raised when it escapes unhandled. `bottom "reason"` carries
a diagnostic string.

**What's missing:**
- Complete propagation rules (what happens when `bottom` enters a list? a
  conditional? a contract?)
- Catchability semantics (can `bottom` be caught? should it be? under what
  conditions?)
- Short-circuit behavior (does `list(bottom, f())` evaluate `f()`?)
- Type-level guarantees (can a function's signature promise it never returns
  `bottom`?)
- Relationship between `bottom` and effects (does refusing count as an effect?)

**Risk without formalization:** Inconsistent propagation behavior across
implementations. Accidental catching of `bottom` that should have propagated.

---

### 4. Ambiguity Handling

**Current state:** The language has `bottom` (refusal) and confidence scores.
There is no explicit representation of ambiguity or contradiction.

**What's missing:**
- Formal distinction between unknown, ambiguous, and contradictory states
- Representation requirements for each
- Whether ambiguity is a value, a type, or a control flow mechanism
- How ambiguity interacts with `believe` dispatch
- Whether contradictory evidence should be representable (two sources disagree)

**Risk without formalization:** Ambiguous states get forced into either
certainty or refusal, destroying information.

---

### 5. Evidence Provenance

**Current state:** `belief(value, confidence)` carries a score but no source
information. There is no mechanism to track where confidence came from.

**What's missing:**
- Dependency tracking (which inputs contributed to this belief?)
- Source reliability weighting (is this source historically accurate?)
- Confidence lineage (how was this score computed?)
- Staleness detection (when was the evidence gathered? is it still valid?)
- Independence verification (are these two pieces of evidence actually
  independent?)

**Risk without formalization:** Confidence inflation through correlated
evidence. Stale data producing unjustified certainty.

---

### 6. Distributed Evaluation

**Current state:** The parallel evaluator runs independent branches
concurrently. Remote symbol resolution fetches symbols across machines.

**What's missing:**
- Behavior under partial failure (one branch refuses, another succeeds)
- Async composition of beliefs (how do you combine results that arrive at
  different times with different confidence levels?)
- Timeout semantics (is a timeout equivalent to `bottom`? to low confidence?
  to something else?)
- Consistency guarantees when evidence sources are eventually consistent

**Risk without formalization:** Distributed systems built on CPL will have
undefined behavior under partial failure, which is the most common operating
condition for distributed systems.

---

## Goal

Establish a formal semantic foundation sufficient to:

1. Prevent unsafe implementation drift between reference and alternative
   implementations
2. Enable machine-checkable verification of safety properties
3. Provide clear answers when implementation questions arise
4. Support safe composition of beliefs across system boundaries

---

## Proposed Path

1. **Immediate:** Document the invariants that must hold regardless of
   formalization approach (see `docs/SEMANTIC_INVARIANTS.md`)
2. **Near-term:** Choose a formal framework for belief semantics (Dempster-
   Shafer, probabilistic, or evidence-based) and specify composition rules
3. **Medium-term:** Formalize `bottom` propagation as a complete algebra
4. **Long-term:** Machine-checkable intent contracts and confidence calibration

---

## Open Questions

- Should CPL adopt an existing formal framework (e.g., Dempster-Shafer theory
  of evidence) or define its own?
- Is confidence best modeled as a single scalar, an interval, or a
  distribution?
- Should provenance be a runtime property (carrying metadata) or a type-level
  property (statically checked)?
- How much formalization is needed before v5.0 ships?

---

*RFC version: 1.0 — May 2026*
*Governed by: GOVERNANCE.md*
