# DecodeTheSign — Xcode Claude Session Code Review

**Date:** 2026-05-21
**Persona:** Quill
**Project:** DecodeTheSign (iOS)
**Gate:** Code review

---

## What happened

Reviewed the Xcode Claude session audit log (382c6cc1, last 4 hours).
6 edits across 3 files. Two features added: auto-torch in low light,
and client-side nearby spots cache sent to server.

---

## Findings

### ✅ PASS — `CameraService.isLowLight()`

New method reads `device.iso >= 800` as a low-light heuristic. Solid.
Called at shutter time after the AE loop has settled — timing is correct.

### ✅ PASS — `APIClient.analyzeCapture(clientNearbySigns:)`

`NearbySpot` is `Codable` — JSON encoding works. Multipart field
`client_nearby_spots` added to request body. Good optimization pattern,
mirrors `preExtractedText`.

**Note:** Server-side capture route does not yet read `client_nearby_spots`.
The iOS client sends it but the server ignores it. Harmless but the
optimization is not active. Server-side wiring needed to complete the feature.

### ⚠️ DEFECT — Auto-torch stays on after scan (`ScanView`)

```swift
if !isTorchOn && camera.isLowLight() {
    isTorchOn = true
    camera.setTorch(true)
}
```

Torch is turned on but never turned off after the scan completes.
`camera.reset()` does not touch the torch. Result: torch fires in low
light and stays on for every subsequent scan until the user manually
toggles it off. Battery drain + confusing UX.

**Fix required:** Track whether torch was auto-enabled, turn it off in
all three result paths (success, lowConfidence, failure).

### ✅ PASS — `ScanView` cachedNearbySpots

Clean. Uses warmedLocation as lookup key. Cache validity (60s, <100m) reasonable.

### ✅ PASS — `NearbySignsCache`

Actor isolation correct. In-flight task cancellation correct. Invalidation
after successful scan correct.

---

## Action required

Fix auto-torch before next TestFlight build.
Wire server-side `client_nearby_spots` to complete the nearby cache optimization.
