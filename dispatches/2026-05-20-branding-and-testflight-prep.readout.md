# Quill Readout — 2026-05-20: Branding Unification & TestFlight Prep

## Session Summary

Two parallel workstreams converged today: brand consistency across all surfaces, and iOS app hardening for TestFlight submission.

## Workstream 1: Brand Unification (Kiro)

Unified "decode the sign" branding across codifide.com, decodethesign.com, and the iOS native app.

### Brand Identity Established
- **Name**: "decode the sign" (lowercase, monospace/code-style)
- **Tagline**: "parking, interpreted"
- **Logo**: Hexagonal frame (purple→teal gradient) with parking sign "P" and scan lines
- **Works on dark and light backgrounds**

### codifide.com (publicsite)
- Rewrote DecodeTheSign project card: accurate feature list, removed unimplemented claims (ARKit overlay, Apple Wallet, multi-city sync)
- Removed screenshots from the card (live on decodethesign.com instead)
- Updated glossary references (4 entries)
- Fixed CSP errors: created `/api/pypi-stats` server-side proxy to avoid CORS blocks from pypistats.org
- Removed dead `/symbols` GET calls from stats.js

### decodethesign.com
- Redesigned homepage to match codifide.com card style: clean, feature-focused, no decorative fluff
- Removed Codifide logo from header (stays in footer as "Brought to you by")
- Updated all pages: coverage, support, privacy, terms, track, consumer/live, spot layout
- Coverage page now shows Raleigh NC as only live city with "coming soon" list
- Generated proper favicons from the hexagonal logo mark (16x16, 32x32, 180x180, .ico, SVG)
- Committed the wordmark SVG (was untracked, causing broken image on production)
- Added 10 fresh app screenshots to homepage

### iOS Native (Strings.swift)
- App name: "decode the sign"
- Tagline: "parking, interpreted"
- Pitch: "Point your camera at any parking sign. Get YES or NO in seconds."
- About mission body updated

## Workstream 2: iOS TestFlight Prep (Xcode Claude)

Parallel session in Xcode/Claude hardened the native app for TestFlight submission.

### App Shortcuts (Siri)
- Moved `AppShortcutsProvider` from Swift Package to main app target (required for Xcode metadata extraction)
- Four shortcuts registered: Scan a Sign, Find My Car, Parking Status, End Session
- Proper `.applicationName` phrase tokens for Siri discovery

### Auth & Permissions Flow
- Integrated `AuthService.shared` into ContentView
- Deferred location permission request to after onboarding completion (not on first screen)
- Returning users get location immediately; new users see it after onboarding context

### Navigation & UX
- Added "OpenScanTab" notification handler for deep-link and shortcut routing
- Updated nav wordmark to match brand: "decode " (blue) + "the sign" (navy), "parking, interpreted" subtitle
- Simplified AppIntentsService (25 insertions, 66 deletions — cleaner intent definitions)

### Build Configuration
- Added `aps-environment` to Debug.entitlements
- Updated project.pbxproj with new file references
- Added Info.plist for proper app configuration
- Regenerated AppIcon.png (55KB, down from 227KB)

## Content Accuracy Audit

Removed claims for unimplemented features:
- ❌ ARKit real-time verdict overlay (AR/ directory is empty)
- ❌ Apple Wallet parking sessions (aspirational)
- ❌ Multi-city data sync (Chicago, NYC, SF — not live)
- ❌ Street cleaning schedules (cron exists but not user-facing)
- ❌ MapKit color-coded nearby spots (not implemented)

Retained claims for implemented features:
- ✅ AI sign reading (OCR + Gemini)
- ✅ YES/NO/SOON verdict with countdown
- ✅ Session tracking with Live Activity
- ✅ Find My Car compass navigation
- ✅ Siri App Intents
- ✅ Home Screen Widget
- ✅ Core ML arrow detection
- ✅ Directional sign awareness
- ✅ Conservative low-confidence gating

## Deployment Status

| Surface | Status | Method |
|---------|--------|--------|
| codifide.com | ✅ Live | Vercel direct deploy |
| decodethesign.com | ✅ Live | Vercel direct deploy |
| iOS app | 🔜 TestFlight tomorrow | Xcode Archive → App Store Connect |

## Tomorrow's Plan

TestFlight submission. The iOS app has:
- Proper entitlements (push, Sign in with Apple)
- App Shortcuts in the correct target
- Clean permission flow
- Updated branding throughout
- Feature flags hiding unfinished features (Find Spot, smart street map)
