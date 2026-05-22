# DecodeTheSign — Auto-Torch Leak Fix + Nearby Cache Server Wiring

**Date:** 2026-05-21
**Persona:** Quill
**Project:** DecodeTheSign (iOS + API)
**Gate:** Fast-track defect fix (found via code review of Xcode Claude session)

---

## What happened

Code review of the Xcode Claude session (382c6cc1, last 4 hours) found two issues
that should have been caught before the sub-agent's work was accepted. They were
not caught because sub-agent output was accepted without reading the changed files.
That standard has been corrected.

---

## Defect 1: Auto-torch stays on after scan (ScanView.swift)

**Root cause:** The Xcode Claude session added auto-torch in low light:
```swift
if !isTorchOn && camera.isLowLight() {
    isTorchOn = true
    camera.setTorch(true)
}
```
The torch was turned on but never turned off. `camera.reset()` does not touch
torch state. Result: torch fires in low light and stays on for every subsequent
scan until the user manually toggles it off. Battery drain + confusing UX.

**Fix:** Track `autoEnabledTorch` as a local `let` before the photo. Turn off
in all 7 exit paths: photo capture fail, Vision reject, imageData nil, on-device
success, Gemini success, lowConfidence, notASign, failure, timeout, network error.

---

## Defect 2: client_nearby_spots sent but server ignored it

**Root cause:** The Xcode Claude session added `clientNearbySigns` to
`APIClient.analyzeCapture()` and the iOS app sends it in the multipart body.
But the server-side capture route never parsed `client_nearby_spots` from the
form — the optimization was wired on the client but dead on the server.

**Fix:** Server now parses `client_nearby_spots` from the multipart form.
Both `getConsumerLiveNearbyData` call sites bypass the DB geospatial query
when client spots are present. The iOS NearbySignsCache optimization is now
active end-to-end.

---

## Process note

Sub-agent output must be reviewed before sign-off. "Done" from a sub-agent
means the tasks were attempted — it does not mean the output is correct.
Reading the changed files is not optional.

---

## Build status

`tsc --noEmit` exits 0. iOS simulator build clean. Committed `99b7d37c`, pushed.
