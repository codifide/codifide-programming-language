# DecodeTheSign — Golden Record Enforcement, Retention Policy, Crowdsource Rollup

**Date:** 2026-05-21
**Persona:** Quill
**Project:** DecodeTheSign
**Gate:** Fast-track architectural hardening

---

## What happened

Douglas directed that the MDM golden record model must be enforced permanently
and that old data must not accumulate in tables beyond defined retention windows.
Crowdsourced scan submissions should roll up into durable totals for the awards
system but raw history should not be kept beyond 7 days.

Three pre-existing TypeScript errors were also found and fixed — they were not
caused by this session's work but were present in the codebase. Skipping them
was called out as unacceptable. Fixed.

---

## What shipped

### Steering — `07-data-model-golden-record.md` (new)

Permanent architectural rule document. Defines:
- Table roles: golden record (`sign_locations`), current truth (`sign_rules`),
  audit logs (`consumer_sign_submissions`, `consumer_capture_audits`, `sign_events`),
  trust signals (`consumer_feedback`), awards record (`consumer_contributors`)
- The invariant: `sign_rules` is a current-state table, not append-only. Deactivation
  is unconditional when OCR confidence ≥ 0.95.
- Retention windows: submissions 7d, capture audits 30d, sign events 30d,
  feedback 90d, inactive rules 30d, active rules permanent.
- Rollup-before-purge pattern documented.

### Migration `20260521000002_crowdsource_submission_count.sql`

- Adds `crowdsource_submission_count integer NOT NULL DEFAULT 0` to
  `consumer_contributors`
- Backfills from existing `consumer_sign_submissions` rows
- Creates `increment_contributor_submission_count(p_device_id text)` RPC —
  atomic upsert-or-increment so first-time anonymous contributors get a row
  created automatically

### `lib/consumer-crowdsource-intake.ts`

- `completeConsumerSignSubmission` accepts optional `contributorHash` param
- On every successful completion (not failed/duplicate), fires a background
  increment to `consumer_contributors.crowdsource_submission_count`
- Fire-and-forget with `SILENT-CATCH-APPROVED` — failure logs a warning but
  does not block the capture response
- `replaceActiveRules` logic simplified: now `true` whenever
  `ocrSnapshot.confidence >= AUTO_VALIDATED_OCR_CONFIDENCE` and the sign
  already has active rules. Removed the `shouldRefreshActiveRulesFromSubmission`
  panel-count comparison that was causing duplicate rule accumulation.

### `app/api/consumer/live/[liveId]/capture/route.ts`

- All four `completeConsumerSignSubmission` call sites pass `contributorHash`

### `app/api/cron/cleanup/route.ts`

Fully rewritten. Now enforces all retention windows:

| Task | Retention |
|------|-----------|
| `consumer_sign_submissions` | 7 days |
| `consumer_capture_audits` | 30 days |
| `sign_events` | 30 days |
| `consumer_feedback` | 90 days |
| `sign_rules` (inactive) | 30 days |
| `spot_sessions` (expired) | immediate |
| `location_shares` (expired) | immediate |

### Pre-existing TypeScript errors fixed (zero tolerance)

Three files had broken `const` declarations — the variable name was present in
usage but the `const x =` assignment line had been dropped, leaving dangling
ternary expressions:

1. `app/api/admin/upstream-reports/export/route.ts` — missing `const reportIds =`
2. `app/api/admin/conflicts/[id]/resolve/route.ts` — missing `const actionKey =`
3. `app/api/admin/upstream-reports/[id]/promote/route.ts` — missing `const nextStatus =`

All three fixed. `tsc --noEmit` exits 0.

---

## Standard set

Pre-existing errors are not "unrelated to our changes." If `tsc` exits non-zero,
fix everything until it exits 0. No exceptions.
