# RFC 0003 — Epistemic State Model

**Status:** Draft  
**Author:** Douglas Jones (with material from a GPT-4o session, May 2026)  
**Date:** 2026-05-19

---

## Summary

This RFC proposes that CPL eventually distinguish five epistemic states
where it currently distinguishes two. The five states are:

- **Certain(value)** — confident, value-bearing
- **Ambiguous(possible_values)** — multiple valid answers, cannot disambiguate
- **Refused(reason)** — deliberate abstention with cause
- **Contradictory(evidence)** — conflicting evidence sources
- **Unknown** — no evidence, no judgment yet rendered

CPL today represents only **Certain** (via `belief(value, confidence)`) and
**Refused** (via `bottom "reason"`). The other three are not representable.

---

## Motivation

The DecodeTheSign case study (a parking-sign interpretation app) demonstrated
a real-world failure mode where directional signs have two valid
interpretations depending on the driver's position. The application had to
either pick one (creating false positives) or refuse entirely (creating
false negatives that frustrated users). Neither is correct — the truthful
representation is "the answer is YES if you're on the left, NO if you're on
the right, and I can't tell which side you're on."

CPL today has no way to express this. The application either invents
single-answer logic (which the case study showed is dangerous) or refuses
(which loses information).

---

## Mapping to Current Surface

| State | CPL today | Notes |
|---|---|---|
| Certain(value) | `belief(value, conf)` where conf clears the gate | Implemented |
| Ambiguous(possible_values) | Not representable | Workaround: programmers return a list, but the type system doesn't distinguish "list value" from "ambiguous result" |
| Refused(reason) | `bottom "reason"` | Implemented as of v3.0 |
| Contradictory(evidence) | Not representable | Workaround: refuse, losing the contradiction signal |
| Unknown | `bottom` (without reason) | Conflated with Refused |

---

## Possible Surface Designs

This RFC does not commit to any particular design. Three sketches:

### Option A — New primitives

Add primitives that produce each epistemic state:

```
ambiguous([a, b, c])           # returns Ambiguous
contradictory(evidence_list)    # returns Contradictory
unknown                         # returns Unknown
```

`believe` blocks would gain new arms to dispatch on these.

**Cost:** Significant new surface. New primitives, new dispatch arms, new
runtime behavior. Likely v5+ work.

### Option B — Type tags on `belief()`

Extend `belief()` to take an optional state tag:

```
belief(value, conf, "ambiguous")
belief(value, conf, "contradictory")
```

Default tag is "certain." `bottom` continues to mean refused.

**Cost:** Smaller. Reuses existing surface. But may overload `belief()` past
its readable limit.

### Option C — Distinct types in canonical form

Add new canonical-form node kinds for each epistemic state. Surface syntax
follows.

**Cost:** Largest. Touches the spec, both interpreters, the canonical crate,
the conformance tests, and the capability manifest.

---

## Adoption Evidence

Currently zero adoption evidence from CPL agent sessions. The motivation
comes from:

1. The DecodeTheSign case study (Swift, not CPL)
2. A hypothetical "what should the type system eventually distinguish"
   discussion with GPT-4o

Both are arguments for the *idea*. Neither is evidence that an agent writing
CPL programs hit this limitation and was blocked by it. Per the project's
adoption-evidence rule, this RFC is not yet eligible for promotion to spec
work.

**Trigger condition:** An agent session producing a CPL program that
demonstrably needs Ambiguous, Contradictory, or distinct Unknown
representation, where the workaround in current CPL is unsatisfactory.

---

## Open Questions

1. Is the five-state model the right factoring, or are some of these
   collapsible? (E.g., is Unknown really distinct from "refused for lack of
   evidence"?)

2. If we adopt Option A, B, or C, what happens to existing programs? `bottom`
   has been in the language since v1.0 and split into `bottom` / `bottom
   "reason"` in v3.0. Adding new states is a third refinement of the same
   surface area.

3. Does the language need first-class representation, or is it sufficient
   for *libraries* to provide these abstractions on top of `belief` and
   `bottom`?

---

## Decision

Pending. This RFC is filed for future review when adoption evidence emerges.

---

*RFC version: 1.0 (draft)*
*Supersedes: docs/EPISTEMIC_MODEL.md (May 19, 2026 — withdrawn for being premature)*
*Governed by: GOVERNANCE.md*
