# Session Close — May 21, 2026 (Session 2)

**Date:** 2026-05-21
**Persona:** Quill
**Type:** Session close

---

## What happened this session

Continued from the Vision OCR hardening session. Douglas asked why `raleigh-feed-87957`
has 13 active rules when it should have 3, and whether the golden record model
was broken.

### Forensic audit of the duplicate rules

Queried all 22 rules (active + inactive) for the sign with timestamps. The
duplication pattern:

- April 22: 9 inactive + 3 active (deactivation ran mid-import or missed rows)
- April 23: 3 more active rules added on top
- May 2: 6 more active rules added on top — deactivation either didn't run or
  missed rows due to a `jurisdiction_id` mismatch

Root cause: `deactivateActiveRulesForSign` is conditional. The crowdsource path
only sets `replaceActiveRules = true` when `shouldRefreshActiveRulesFromSubmission`
returns true — which requires the new submission to have *more panels* than the
existing one. Same-panel-count re-imports insert new rules without deactivating
old ones.

### Design analysis: golden record model

The architecture is correct in intent:
- `sign_locations` = golden record (one row per physical sign)
- `sign_rules` = current truth (active rules only)
- `consumer_sign_submissions` = audit log (every capture, regardless of quality)

The gap: `sign_rules` is being treated as append-only instead of current-state.
Every import path that should *replace* rules is *accumulating* them.

### Recommended fixes (not yet implemented — deferred to next session)

1. **Make deactivation unconditional on re-import.** `replaceActiveRules` should
   default to `true` for any path with a complete new extraction, not just when
   panel count increased.

2. **Add a partial unique index on `sign_rules`** on
   `(sign_id, activity_type, arrow_direction, time_start, time_end, days_of_week)`
   where `is_active = true`. Makes duplicate accumulation physically impossible.

3. **Cleanup migration** for existing duplicates: keep only the most recent
   active rule per logical fingerprint per sign, deactivate the rest.

---

## What was NOT done this session

- No code was written. This was analysis and design.
- The `high_confidence_no_ocr` inline evaluation fix (deferred from earlier today)
  is still outstanding.
- The duplicate rule cleanup migration is still outstanding.

---

## Open items carried forward

| Item | Priority | Notes |
|------|----------|-------|
| `high_confidence_no_ocr` inline evaluation | Critical | `evaluateRulesAtLocation` import is in place, call site not wired |
| `sign_rules` deactivation unconditional | Major | `replaceActiveRules` flag logic needs inversion |
| Partial unique index on `sign_rules` | Major | Prevents future accumulation |
| Duplicate cleanup migration | Major | 13 → 3 active rules on `raleigh-feed-87957` and likely others |
