# DecodeTheSign — Git Commit, Data Reset, Vercel Deploy, iOS Device Deploy

**Date:** 2026-05-21
**Persona:** Quill
**Project:** DecodeTheSign
**Gate:** Fast-track release prep

---

## What happened

Douglas requested a clean slate for testing: commit everything, wipe all
crowdsourced captures, deploy API to Vercel, deploy iOS to device.

---

## What shipped

### Git — commit `1e512d3a`

All session work committed and pushed to `origin/main`:
- VisionService OCR hardening
- ScanView GPS warm-up + location pill + continuous refinement
- capture/route isComplexSign fix + high_confidence_no_ocr inline_evaluation
- consumer-crowdsource-intake replaceActiveRules + crowdsource_submission_count
- cron/cleanup full retention policy
- Migrations: sign_rules dedup/unique index, crowdsource_submission_count column
- Steering: 07-data-model-golden-record.md
- Admin route pre-existing TS error fixes

11 files changed, 621 insertions, 44 deletions.

### Database reset — clean slate

Deleted in FK order:

| Table | Rows deleted |
|-------|-------------|
| `consumer_feedback` | 41 |
| `consumer_capture_audits` | 176 |
| `consumer_sign_submissions` | 176 |
| `ocr_extractions` (crowd images) | 22 |
| `sign_images` (crowd) | 23 |
| `sign_rules` (crowd) | 23 |
| `sign_events` (crowd) | 266 |
| `sign_locations` (crowd `nationwide-us-crowd-*`) | 14 |
| `consumer_contributors` counters | reset to 0 |

Not touched: `raleigh-feed-*` authoritative signs and their rules.

### Vercel — `decodethesign.com` ✅

Production deploy completed in 34s. All API changes live.

### iOS — device `DJ1Z` ✅

Built Debug configuration, installed via `xcrun devicectl`.
Bundle: `com.codifide.decodethesign`

---

## Ready for testing

Database is clean. App on device has all today's fixes. API is live.
