# DecodeTheSign — Golden Record Authority Requirements

**Date:** 2026-05-21
**Persona:** Quill
**Project:** DecodeTheSign
**Gate:** Requirements / architectural decision

---

## What happened

Douglas stated the architectural principle: a high-confidence sign scan is the
golden record. Data feeds run nightly but support and decorate it. When the two
disagree, the capture wins.

Before locking this in, one flaw was identified and addressed.

---

## The flaw: high OCR confidence ≠ correct sign

High OCR confidence means "we read the text clearly" — not "the sign is correct."
A defaced, vandalized, or partially obscured sign can be read with 0.99 confidence
and produce wrong rules. "Capture wins" cannot be unconditional.

---

## The resolution: split authority by data type

| Field | Authority |
|-------|-----------|
| Parking rules (times, days, activity, arrows) | Capture wins at confidence ≥ 0.95 |
| Sign existence (is_active) | Feed wins — city knows when signs are removed |
| Sign location (lat/lng) | Feed wins — surveyed GIS beats phone GPS |
| Sign identifier | Feed wins |

**Conflict guard:** when a high-confidence capture conflicts with recent feed data
(< 30 days old), queue to `sign_conflicts` for human review rather than
auto-overwriting. Auto-resolve in favor of capture only when no feed data exists
or feed is > 30 days stale.

**Sign replacement scenario:** feed update → conflict queued → feed wins because
capture is older. Old capture marked superseded, not deleted.

---

## What shipped

`steering/08-golden-record-authority.md` — permanent architectural requirement,
auto-included in every session. Committed `b37f9fe5`, pushed to `origin/main`.

Covers:
- Authority table by field type
- Conflict resolution rules
- Vandalism/OCR error guard
- Sign replacement scenario
- Implementation checkpoints (all already implemented)
- What this is NOT ("crowd data always wins")
