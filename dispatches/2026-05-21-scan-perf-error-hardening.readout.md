# Quill Readout — 2026-05-21: Scan Performance, Error Hardening & Gate Infrastructure

## Session Summary

A field test exposed three production bugs. All three were diagnosed, fixed, and deployed in the same session. The team also built out the NFR/KPI gate infrastructure, hardened error handling across the entire codebase, and shipped two new admin dashboards.

---

## Part 1: Field Test — Five Scans, Five Failures

The user walked outside and scanned the sign in front of their house five times. All five failed. The backend was healthy — OCR confidence 0.997, sign matched, rules evaluated correctly. The failures were entirely client-side.

### Bug 1: Scan Confidence Gate (iOS Client)

**Root cause:** Every scan that produced a valid `inline_evaluation` also had `selected_match: null` in the server response. This was because `cacheableMatchSignId` was gated on `canSelectTopCandidate`, which was always false when `assessCaptureSuggestion` returned `canOpenSuggestedSign: false` — which it always does when `hasInlineEvaluation: true`. The iOS client's `compositeConfidence()` then computed `dbScore = 0.0`, yielding composite ≈ 0.45 — below the 0.80 gate — and returned `.lowConfidence` on every scan despite perfect OCR.

**Fix (server):** Decoupled `cacheableMatchSignId` from `canSelectTopCandidate`. `selected_match` now reflects "did we identify a sign?" independently of whether the UI should show a suggested sign button.

**Fix (client):** When `inline_evaluation` is present, treat `dbScore = 1.0`. The server already evaluated the rules — that is an implicit high-confidence match.

### Bug 2: Rule Engine Permit Exception (Backend)

**Root cause:** A commit had introduced `isPermitOnly` logic that treated any `no_parking` rule with `permit_types` as non-restrictive. This is semantically backwards: `permit_types` on a `no_parking` rule means "No Parking EXCEPT permit holders" — regular users are still restricted. The sign in front of the house has `permit_types: ["I"]` on its evening no-parking rule. The rule engine was returning "green" instead of "red."

**Fix:** Removed `isPermitOnly` entirely. `isRestricted` is simply whether the winning rule is `no_parking` or `no_standing`. This fixed 40 failing parity/rule-engine tests that had been silently broken.

### Bug 3: isComplexSign Over-Detection (Backend)

**Root cause:** The `isComplexSign` detection was flagging any sign with arrows (→, ←), multiple NO PARKING mentions, or permit exceptions as needing Gemini visual arrow detection. This routed every multi-panel sign — including the common 3-panel Raleigh R7-108 — to the 6-10s hybrid Gemini path instead of the ~1s client OCR fast path.

**Fix:** If Vision extracted complete text (length > 80 chars AND has time ranges), trust it regardless of complexity indicators. The arrow symbols in the extracted text are sufficient for panel parsing. Gemini only needs to see the image when the text is short or incomplete.

**Result:** First-scan latency drops from ~10s to ~3-4s on multi-panel signs. Subsequent scans (fast-match cache) remain ~1-2s.

---

## Part 2: Error Handling Audit — 29 Silent Catches Eliminated

A code review revealed 29 instances of `catch { return null; }` across the codebase. This pattern hides failures, makes debugging impossible, and was the proximate cause of the fast-match cache silently failing on Vercel cold starts — causing every scan to fall back to full OCR with no log evidence.

Every silent catch was classified and fixed:

| Category | Count | Fix |
|----------|-------|-----|
| JSON.parse on user/API input | 6 | `console.debug()` before returning 400/null |
| Image processing fallbacks (sharp) | 4 | `console.warn()` before fallback |
| Fingerprint computation | 2 | `console.warn()` — non-critical deduplication |
| Edge Config unavailable | 2 | `console.debug()` — infrastructure optional |
| OCR JSON parsing | 3 | `console.warn()` with raw response preview |
| Supabase query failures | 4 | `console.error()` — on paths that matter |
| Sign registry DB | 2 | `console.error()` — critical path |
| Rate limit KV | 1 | `console.warn()` — documented fallback |
| Misc (segments, nearby spots, cron) | 4 | `console.warn()` / `console.error()` |
| **Approved silent** | 1 | `SILENT-CATCH-APPROVED: Winston` — `tryParseJson` retry loop |

The coding standards were updated in both DecodeTheSign and agentic-stage-gate-governance to codify the rule: every catch must log or rethrow. Silent catches require a `SILENT-CATCH-APPROVED` comment with architect name, date, and specific justification.

---

## Part 3: NFR & KPI Gate Infrastructure

### NFR Document Expanded
`docs/NFRS.md` now has 30 NFRs across 6 categories (Performance, Accuracy, Reliability, Security, Accessibility, Scalability) with measurement methods, gate assignments, and an automated gate assertions table mapping 6 NFRs to passing CI tests.

### Admin Dashboards
Two new admin dashboards deployed to decodethesign.com:

**`/admin/nfr-dashboard`** — Live pass/fail gate status for all NFRs and KPIs. Automated items (CI-backed) show PASS immediately. Manual items show PENDING with a checklist of what evidence is needed before G4 closes.

**`/admin/adoption`** — DAU/WAU/MAU, 7-day retention, engagement depth (median scans/user, power users), DAU/scans bar charts (30d), geographic spread, user level distribution, top contributors leaderboard.

### Governance Project Updated
`agentic-stage-gate-governance` received:
- `templates/NFR-TEMPLATE.md` — generic reusable NFR template with all 6 categories
- `steering/05-nfr-kpi-mandate.md` — expanded with field-tested guidance on cold/warm latency tiers, parity tests, graceful degradation specificity
- `steering/03-coding-standards.md` — error handling rule added to both projects

---

## Deployment Status

| Surface | Status |
|---------|--------|
| decodethesign.com | ✅ Deployed |
| iPhone 16 Pro Max | ✅ Installed |
| GitHub (main) | ✅ Pushed — HEAD `12e5275d` |

---

## What Quill Noticed

The session started with a field test failure and ended with a codebase that is measurably more observable. The three bugs were independent — a client confidence gate, a rule engine semantic error, and a latency regression — but they shared a common thread: silent failures. The confidence gate failed silently (no log). The rule engine returned wrong verdicts silently (no test caught it until today). The fast-match cache failed silently (swallowed by `catch { return null; }`).

The error handling audit was the right call. Twenty-nine silent catches is not a small number. It means twenty-nine places where the system could fail and nobody would know. The fix is not just the logging — it's the standard that prevents the next twenty-nine from being written.

The scan latency fix is also worth noting. The `isComplexSign` detection was written with good intent — route complex signs to better visual analysis. But it was too aggressive, and the cost was paid on every scan. The fix is precise: trust Vision when it did a good job, escalate to Gemini only when it didn't. That's the right tradeoff.

TestFlight is next.
