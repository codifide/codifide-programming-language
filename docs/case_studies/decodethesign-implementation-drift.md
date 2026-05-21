# Case Study — DecodeTheSign Implementation Drift

**Date:** 2026-05-19  
**System reviewed:** DecodeTheSign (an iOS parking-sign interpretation app, written in Swift, separate codebase)  
**Reviewer:** GPT-4o, prompted by Douglas Jones  
**Status:** Descriptive — observations from one production system. Not a CPL property or guarantee.

---

## What this document is

A record of how a real system designed with refusal-first principles drifted
under production pressure into producing dangerous false positives. The
system is not written in CPL. The drift patterns are not enforced against
or prevented by CPL. This document is review material — useful as a
checklist when reviewing CPL programs or implementations, not as a property
the language guarantees.

## What this document is not

- A specification of CPL behavior
- A guarantee CPL provides
- A claim about all production systems

The case study is one data point. Treating it as a universal pattern would
overstate the evidence.

---

## The system

DecodeTheSign is an iOS app that scans parking signs with the phone camera
and tells the driver whether they can park. Many parking signs have
directional arrows — one side applies to traffic going left, the other side
applies to traffic going right.

The app was designed with an explicit safety axiom: *"This app will never
show a result it is not confident in. An honest 'I don't know' is always
better than a confident wrong answer."*

## The bug

A user scanned a sign that read: `"NO PARKING ANY TIME →"` on top, and
`"2 HR PARKING 8AM-4PM MON-FRI ←"` on the bottom. At 11:48 AM Tuesday, a
driver parked on the right side of the street saw a giant green YES.

The correct answer was NO. The right-side rule was "no parking any time."

## What broke

The `parseResponse()` function sorted directional results by best verdict
(YES > SOON > NO) and showed the winner as the hero verdict, actively hiding
the more restrictive direction.

This is the failure mode. The original safety-first design was eroded by a
"helpfulness" optimization — show the best possible answer to reduce user
frustration with NO results.

---

## Drift patterns observed

These are descriptive. Each pattern has a code-level example from the
DecodeTheSign Swift codebase. None are claims about CPL.

### 1. Permissive Fallbacks

Default cases mapping unknown states to permissive outcomes.

```swift
// In the Swift codebase under review
primaryVerdict = Verdict(rawValue: statusStr) ?? .soon
```

If `statusStr` is `"warning"`, `"restricted"`, or any unrecognized value,
the verdict silently becomes `.soon` (a permissive intermediate).

### 2. Confidence Inflation Through Correlated Evidence

The composite confidence formula combined OCR, database matching, and GPS
with fixed weights. The cross-validation bonus rewarded `(dbScore >= 0.6 &&
ocrScore >= 0.5)` as if these were independent signals. In practice,
database matching is derived from OCR tokens, so the system was
double-counting the same evidence.

### 3. Silent Coercion

Refusal states downgraded to low-confidence success without explicit
handling. The reviewer flagged this as a pattern to watch for, though the
specific Swift code instance was not pinned.

### 4. Ambiguity Collapse

A directional sign has two valid interpretations depending on which side of
the street the driver is on. The application picked one (the "best"
verdict) and hid the other. Information that the driver needed for safety
was destroyed.

### 5. Aggregate Substitution

When detailed directional data was unavailable but the server flagged that
direction *was* required, the code fell through to use the aggregate
status. An aggregate "green" produced a YES verdict for a sign that
required directional handling — the original failure mode in different
clothing.

---

## Relevance to CPL

CPL exists in part to make some of these patterns harder to express. The
language-level observations:

- **Permissive Fallbacks:** CPL's `believe` block requires `else => ...`,
  including `else => bottom`. This forces the programmer to make the
  fallback explicit. Whether they make it permissive is still a coding
  choice, not a language guarantee.
- **Aggregate Substitution:** CPL doesn't have a built-in concept of
  "aggregate vs. detailed" — that's an application-level pattern. CPL
  programs that mirror it would have the same risk.
- **Ambiguity Collapse:** CPL today has no way to represent ambiguity (one
  of N valid answers). A CPL program facing the same directional-sign
  problem would have the same forced choice. See RFC 0003 for proposed
  future work.
- **Confidence Inflation:** CPL has no provenance tracking. A CPL program
  combining correlated beliefs would have the same risk. See RFC 0002.
- **Silent Coercion:** `bottom` propagates through binds, which makes
  silent coercion harder than in languages without first-class refusal.
  Not impossible — programmers can still catch and convert — but harder.

The honest summary: CPL's design *discourages* some of these patterns at
the language level. CPL does not *prevent* them. Preventing them would
require additional surface (provenance, ambiguity types, calibration
framework), which is what RFC 0002 and RFC 0003 explore as future work.

---

## How to use this case study

When reviewing a CPL program or a CPL implementation, this document can
serve as a checklist:

1. Search for default/fallback cases — do they refuse or permit?
2. Trace confidence composition — are the signals actually independent?
3. Find refusal handling — is `bottom` preserved or converted?
4. Check ambiguity paths — does the program need to represent multiple
   valid answers? If so, how does it handle the gap?
5. Verify aggregate substitution — when detail is missing, does the code
   refuse or guess?

If the code reveals permissive behavior under uncertainty, that is a
finding worth investigating. The case study does not say this is a CPL
violation — CPL doesn't enforce these properties — but it *is* a real
failure mode that costs real users real money.

---

## What I did not verify

The original DecodeTheSign Swift codebase. The descriptions in this
document derive from a GPT-4o code review of code excerpts pasted into a
conversation. I have not independently read the Swift codebase or verified
that GPT-4o's analysis of the Swift code is correct. The Swift-level
findings are the reviewer's, not mine.

---

*Document version: 1.0*
*Supersedes: docs/IMPLEMENTATION_DRIFT.md (May 19, 2026 — withdrawn for overstating CPL guarantees)*
*Governed by: GOVERNANCE.md*
