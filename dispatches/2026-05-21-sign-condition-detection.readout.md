# DecodeTheSign — Sign Condition Detection

**Date:** 2026-05-21
**Persona:** Quill
**Project:** DecodeTheSign
**Gate:** Feature / automated safety guard

---

## What was built

Gemini now assesses the physical state of every parking sign it reads and returns
a `sign_condition` field alongside the OCR extraction. This closes the vandalism
gap in the golden record authority model.

---

## Sign condition values

| Value | Meaning |
|-------|---------|
| `clean` | Intact, fully legible, no damage or obstruction |
| `damaged` | Bent, torn, holes, or physically broken |
| `graffiti` | Paint, marker, stickers, or other markings over sign text |
| `obscured` | Branch, tape, another sign, or object blocking the sign |
| `faded` | Weathered but readable |

---

## The rule

When `sign_condition` is `damaged`, `graffiti`, or `obscured`:
- The capture is **not eligible** to overwrite feed rules
- `replaceActiveRules` is gated to `false` in `processQueuedConsumerSignSubmission`
- Feed rules remain active — the sign is not in its authoritative state
- The iOS app shows: "⚠️ This sign appears damaged or obscured. Verify before parking."

When `sign_condition` is `clean` or `faded` AND confidence ≥ 0.95:
- Capture wins — it is the golden record
- Feed rules are replaced

---

## No human review queue needed

The condition is detected automatically by Gemini on every scan. There is no
manual review step. The guard is applied inline during `processQueuedConsumerSignSubmission`.

---

## What shipped

- `lib/ocr/extract.ts` — `sign_condition` added to both OCR prompts (fast pass and second pass). `extractSignCondition()` and `isSignConditionEligibleToWin()` exported.
- `app/api/consumer/live/[liveId]/capture/route.ts` — `signCondition` and `signConditionEligible` extracted after OCR. Both returned in the response JSON. `signConditionEligible` passed to `completeConsumerSignSubmission`.
- `lib/consumer-crowdsource-intake.ts` — `signConditionEligible` param added to `completeConsumerSignSubmission`. `SubmissionOcrSnapshot` type extended with `signCondition?`. `replaceActiveRules` gated on `isSignConditionEligibleToWin(extractSignCondition(...))` in `processQueuedConsumerSignSubmission`.
- `ios-native/.../Models/APIModels.swift` — `sign_condition: String?` and `sign_condition_eligible: Bool?` added to `CaptureResponse`.
- `ios-native/.../Models/AppState.swift` — `signCondition: String?` added to `ScanResult`.
- `ios-native/.../Services/ScanResultParser.swift` — `sign_condition` threaded from response into `ScanResult`.
- `ios-native/.../Views/Scan/ResultView.swift` — warning banner shown when `signCondition` is `damaged`, `graffiti`, or `obscured`.
- `.kiro/steering/08-golden-record-authority.md` — updated to reflect automated detection, removed human review language.

Committed `6b35ed9c`, pushed to `origin/main`. Deployed to Vercel production.
