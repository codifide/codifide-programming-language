# DecodeTheSign — GPS Warm-Up, Location Pill, Continuous Refinement

**Date:** 2026-05-21
**Persona:** Quill
**Project:** DecodeTheSign (iOS)
**Gate:** Fast-track field-defect response

---

## What happened

Field testing showed GPS coordinates sent at capture time were 14–18m off even
when the user was standing 5 feet from the sign. Root cause: iOS caches the last
known location and returns it immediately — the scan screen was snapshotting a
stale fix from before the user walked to the sign.

Three iterations to get the behavior right:

1. Force a fresh GPS fix when the scan screen opens
2. Show "Verifying location..." every time (not conditionally)
3. 2-second budget then fall back to OCR-only — don't block the user
4. Keep refining in the background the whole time the screen is open

---

## What shipped

### `ScanView.swift`

**`warmedLocation: CLLocation?`** — new `@State` property. Stores the best GPS
fix obtained since the scan screen opened. Preferred over `location.currentLocation`
at shutter time.

**`locationStatus: LocationStatus` enum** — `.verifying` / `.uncertain` / `.ready`.
Drives the location pill without a boolean flag.

**`warmUpGPS()`** — called concurrently with camera setup in `.task`. Polls for
a fresh fix with `horizontalAccuracy ≤ 15m` and `timestamp < 10s old`. Budget:
2 seconds (10 polls × 200ms). Two outcomes:
- Good fix arrives → `warmedLocation` set, pill fades out silently (`.ready`)
- Budget exhausted → pill shows "Location uncertain" (yellow, `location.slash.fill`)
  for 1.5 seconds, then fades. `warmedLocation` stays nil. Server falls back to
  OCR-only — sign is still read, just not matched to the database record.

**Location pill** — appears every time the scan screen opens, above the spacer,
below the top controls bar. Matches the `.ultraThinMaterial` capsule style of
the existing hint pill. Hidden during active analysis.

**Continuous refinement** — `onChange(of: location.currentLocation)` now upgrades
`warmedLocation` whenever a more accurate fix arrives (accuracy improves, fix is
< 30s old). GPS keeps updating the whole time the screen is open. If the user
spends 10 seconds framing the shot, they get a 10-second-refined fix at shutter
time.

**Shutter snapshot** — prefers `warmedLocation ?? location.currentLocation`, both
gated at `horizontalAccuracy ≤ 20m`. Stale cached positions (> 20m) are treated
as nil.

---

## Design rationale

GPS only matters for matching the sign in the database. OCR reads the sign
regardless. Waiting more than 2 seconds for GPS when the user wants an answer
is the wrong tradeoff. The 2-second budget is the blocking gate; continuous
refinement handles the rest without any user friction.

---

## Build status

Clean build on iPhone 17 Pro simulator (iOS 26.5). All warnings pre-existing.
