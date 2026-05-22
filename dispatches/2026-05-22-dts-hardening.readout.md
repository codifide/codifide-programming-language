# Dispatch — DecodeTheSign Hardening Pass — 2026-05-22

## Summary

Addressed all four gaps identified in the post-deploy analysis: rule engine cache invalidation, iOS NearbySignsCache bug + tests, and dependency vulnerabilities.

## Changes

### 1. Rule Engine Cache Invalidation

**Problem:** The in-memory `ruleEvaluationCache` in `lib/rule-engine.ts` had no invalidation on admin rule writes. An admin editing a sign's rules would see the old verdict served for up to 5 minutes.

**Fix:** Added `invalidateSignCache(signId)` — evicts only the affected sign's cache entries by prefix-matching keys. Wired into all 5 rule-writing endpoints:
- `POST /api/admin/signs/[signId]/rules` — new rule
- `PATCH /api/admin/signs/[signId]/rules/[ruleId]` — edit rule
- `DELETE /api/admin/signs/[signId]/rules/[ruleId]` — deactivate rule
- `POST /api/admin/signs/[signId]/rules/apply-template` — template assignment
- `POST /api/admin/ocr/review/assign-rules` — all 4 code paths (template, understanding, multi-panel, flat fallback)

Also fixed a syntax error in `assign-rules/route.ts` introduced by a previous edit (doubled `if` condition).

Updated `tests/e2e/founder-journey.test.ts` to include `invalidateSignCache: vi.fn()` in the rule-engine mock — same pattern as the `ocr/extract` mock fix from the prior session.

### 2. iOS NearbySignsCache Bug Fix

**Problem:** `NearbySignsCache.invalidate()` called `try? await Task.sleep(nanoseconds:)` inside a non-async function. This is a compile error in Swift 5.9+ (actors require `async` context for `await`).

**Fix:** Removed the invalid sleep. The correct behavior is to cancel the in-flight task and immediately clear state — there is no reason to wait for the task to finish before clearing the cache.

### 3. iOS NearbySignsCache Unit Tests

Added `NearbySignsCacheTests.swift` with 10 tests covering:
- Returns nil when cache is empty
- Returns signs within the 60s freshness window
- Returns nil when cache is stale (>60s)
- Returns nil exactly at the 60s boundary
- Returns signs when query location is within 100m
- Returns nil when query location is >100m away
- Returns nil when cached signs array is empty
- `invalidate()` clears the cache
- `invalidate()` is idempotent
- Cache is usable again after invalidate + re-inject

Added `_injectForTesting()` to `NearbySignsCache` and made `init()` public to support test isolation without network calls.

### 4. Dependency Vulnerabilities

- Removed `uuid` direct dependency — unused (all UUID generation uses `node:crypto`'s `randomUUID`). This resolves the moderate CVE for uuid <11.1.1.
- `npm audit fix` resolved `ws` moderate vuln (indirect dep).
- `brace-expansion` resolved as part of the same fix pass.
- Local `npm audit`: 0 vulnerabilities.

## Test Results

- 1007 passing, 0 failing, 6 skipped
- Build clean
- Deployed to production: https://decodethesign.com

## Commit

`051c0c24` — fix: rule engine cache invalidation on admin rule writes + iOS NearbySignsCache fixes
