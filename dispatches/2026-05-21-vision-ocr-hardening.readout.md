# DecodeTheSign — Vision OCR Hardening & Scan Consistency Fixes

**Date:** 2026-05-21
**Persona:** Quill
**Project:** DecodeTheSign (iOS)
**Gate:** Fast-track field-defect response (no interpreter changes)

---

## What happened

Douglas went outside and took several captures of the same sign in front of his
house. Results were inconsistent — some returned wrong verdicts, some returned
"unable to read the sign." He thumbs-downed the wrong ones. The feedback data
was in the database. We audited it.

---

## What the data showed

Three `wrong` feedback rows from today (20:10–20:14 UTC), all against
`sign_id: "unknown"`, all with `ocr_confidence: 0.5`. The capture audit records
revealed the root causes:

**Apple Vision OCR garble on `2HR`:**
- Capture 1: `"ANB EWIL CHR Z PARKING 8AM - 4PM MON: FRI..."` — complete garbage
- Capture 2: `"NO PARKING ANY TIME SHR PARKING 8AM - 4PM MON FRI..."` — `SHR` for `2HR`
- Capture 3: `"NO PARKING ANY TIME CHR PARKING 8AM - 4PM MON FRI..."` — `CHR` for `2HR`

Direct cause: `usesLanguageCorrection = true` in `VisionService`. Language
correction is designed for prose — it "fixes" `2HR` (not a real word) into
`SHR`/`CHR`/`Z`. Sign text is not prose.

**GPS position mismatch (14–18m reported, user was <5 feet away):**
The location snapshot at shutter time used whatever `currentLocation` was cached
— which could be a stale fix from before the user walked to the sign. The server
scored the nearby sign as `medium` confidence at 14–18m and blocked the result.

**Multi-panel sign routed through cheap parser:**
The sign is a 3-panel sign (`NO PARKING ANY TIME →` / `2HR PARKING 8AM-4PM ←` /
`NO PARKING 4PM-12AM EXCEPT BY I PERMIT`). The `isComplexSign` check had a
short-circuit: any text longer than 80 chars with time ranges was treated as
simple. Vision smashes multi-panel signs into one blob and strips arrow glyphs,
so the cheap single-panel parser got the whole thing, produced one panel with
`arrow: null`, and the rule engine couldn't determine direction.

---

## What shipped

### `VisionService.swift`

1. **`usesLanguageCorrection = false`** — direct fix for `2HR → SHR/CHR/Z`.
   Language correction corrupts sign-specific tokens. Disabled permanently.

2. **`isTextReliable` field on `PreScreenResult`** — Vision now scores its own
   output. Fails the gate when:
   - Average observation confidence < 0.6
   - Any single token confidence < 0.4
   - Known garble patterns present: `SHR`, `CHR`, `ZHR`, `ANB`, `EWIL`, `PERNIT`
   - Letter/digit confusion before `PARKING` (e.g. `Z PARKING`, `S PARKING`)

### `ScanView.swift`

3. **`preExtractedText` gated on `isTextReliable`** — when Vision garbles the
   text, `nil` is sent instead. The server receives the image and runs Gemini
   directly. No more garbage-in-garbage-out through the cheap parser.

4. **On-device inference gated on `isTextReliable`** — Apple Intelligence also
   skips garbled text. No point running the 600ms on-device path on `SHR PARKING`.

5. **GPS accuracy gate at shutter time** — locations with
   `horizontalAccuracy > 20m` are treated as `nil`. The server falls back to
   OCR-only mode rather than matching the wrong sign 15m away. A fresh GPS fix
   while standing still is typically 3–8m.

### `capture/route.ts`

6. **`isComplexSign` detection fixed** — removed the `length > 80 && hasTimeRanges`
   short-circuit that was suppressing the complex-sign flag. Multi-panel
   indicators (`NO PARKING ANY TIME` + any other rule, `≥2 NO PARKING`,
   `\d+HR + NO PARKING`, `EXCEPT BY PERMIT`, arrow glyphs) now always route to
   Gemini regardless of text length. Single-rule signs with complete text still
   use the fast path.

7. **`evaluateRulesAtLocation` imported** — groundwork for the
   `high_confidence_no_ocr` path to return a real `inline_evaluation` (the path
   that skips OCR entirely when GPS confidence is very high). That path currently
   returns no `inline_evaluation`, causing `ScanResultParser` to return `.failure`.
   Full fix deferred to next session — import is in place.

---

## Build status

Clean build on iPhone 17 Pro simulator (iOS 26.5). 9 pre-existing warnings,
0 new warnings, 0 errors.

---

## What I'm not yet sure of

The `high_confidence_no_ocr` path (Bug 1 from the earlier analysis) still needs
its full fix: fetch the sign's rules via `evaluateRulesAtLocation` and include
the result as `inline_evaluation` before returning. The import is in place but
the call site wasn't wired up this session. That's the next thing to do.

The duplicate rules on `raleigh-feed-87957` (13 active rules, 4 copies of each)
also need a cleanup migration. The rule engine produces the correct answer despite
the duplicates, but it's noise and the `verification_state` is `stale`.
