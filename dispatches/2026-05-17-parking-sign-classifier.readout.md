# Parking Sign Confidence Classifier — Example Program

**Date:** 2026-05-17  
**Persona:** Quill  
**Gate:** Fast-track G0/G1/G4 (< 1 day, no interpreter changes, example program only)

---

## What happened

Douglas asked what would be a good candidate to write in Codifide, given the
projects in the workspace. The answer was a parking sign confidence classifier
inspired by DecodeTheSign — the iOS app that interprets confusing parking signs
and refuses to guess when confidence is low.

The program was written, tested, and runs correctly on the first attempt (after
one cost-ordering fix for sign type priority).

---

## What shipped

`examples/parking_sign.cod` — a 140-line Codifide program that demonstrates:

1. **Belief dispatch** — `gate_ocr` uses `belief()` and `believe` to gate on
   OCR confidence. Above 0.85: proceed. Between 0.70–0.85: flag as low
   confidence. Below 0.70: refuse with `bottom`.

2. **Cost-based multi-candidate dispatch** — `classify_sign_type` has six
   candidates ordered by specificity. Street cleaning (cost 1) beats the
   generic time-restricted pattern (cost 10) even though both match signs
   containing "AM"/"PM".

3. **First-class refusal** — Two refusal paths: `gate_ocr` refuses below
   0.70 confidence, and `verdict_for_unknown` refuses on unrecognized sign
   types. Both use `bottom "reason"` with explanatory strings.

4. **Contracts** — Preconditions validate confidence range (0.0–1.0) and
   non-empty text. The runtime enforces these at every call boundary.

5. **Pure functions throughout** — Every function declares `effects {}`.
   No I/O, no model calls. The sign text arrives pre-extracted (simulating
   the OCR-to-rule-engine handoff in DecodeTheSign's architecture).

6. **Parallel evaluator opportunity** — The `main` function's `list()`
   call contains eight independent sign analyses with no shared state.

---

## Test results

```
$ python3 -m codifide run examples/parking_sign.cod
['NO', 'YES', 'NO', 'NO', 'CONDITIONAL', 'UNKNOWN', True, True]
```

| Input | Confidence | Result | Explanation |
|-------|-----------|--------|-------------|
| "NO PARKING ANY TIME" | 0.95 | NO | Clear prohibition |
| "2 HR PARKING 8AM-6PM EXCEPT SUNDAY" | 0.88 | YES | Metered — you can park |
| "PERMIT PARKING ONLY ZONE 4" | 0.92 | NO | Need permit |
| "NO STOPPING 7AM-9AM MON-FRI" | 0.91 | NO | Clear prohibition |
| "STREET CLEANING TUESDAY 8AM-10AM" | 0.87 | CONDITIONAL | Time-dependent |
| "FREE PARKING ALL DAY" | — | UNKNOWN | No recognized pattern |
| "blurry text" | 0.45 | ⊥ (bottom) | Refused — confidence too low |
| "maybe no parking?" | 0.72 | ⊥ (bottom) | Refused — low confidence path |

Full test suite: 461 passed, 0 skipped, no regressions.

---

## Design decision: cost ordering

The first attempt used intuitive costs (no parking = 1, time-restricted = 5,
cleaning = 15). This caused "STREET CLEANING TUESDAY 8AM-10AM" to match
`TIME_RESTRICTED` (cost 5, matches "AM") before `STREET_CLEANING` (cost 15).

The fix: order by specificity, not by intuition. More distinctive keywords
get lower costs. The broad "contains AM or PM" pattern gets cost 10 — it's
the catch-all for time-based signs that don't match a more specific category.

This is the Codifide idiom working as designed: cost annotations let you
express "prefer the more specific match" without complex guard logic.

---

## Connection to DecodeTheSign

The program models the same decision architecture as DecodeTheSign's rule
engine:
- OCR confidence gating (FR-001 acceptance criterion 5: refuse below threshold)
- Sign type classification (FR-002: evaluate rules by type)
- Conservative refusal (the app's core philosophy: never guess)

The difference: DecodeTheSign's real engine is time-aware (evaluates against
current time, handles midnight-wrapping windows, 30-minute SOON threshold).
This Codifide version is a static classifier — it demonstrates the confidence
and dispatch patterns without the clock dependency.

---

## What I'm not yet sure of

Whether the `else if` chaining in `interpret_sign` is the most idiomatic
Codifide pattern. An alternative would be six separate candidates on
`interpret_sign` itself, each guarded by `eq(classify_sign_type(text), "X")`.
That would be more graph-native but would call `classify_sign_type` six times
(once per guard). The current approach calls it once and branches. Both are
valid; the language doesn't yet have a "match" construct that would make this
cleaner.
