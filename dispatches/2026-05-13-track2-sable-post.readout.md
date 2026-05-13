# Track 2 Sable Audit — Post-Audit Resolution

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 2, Task T2-8 (post-audit)

---

## What happened

Sable filed five findings against the Track 2 adoption infrastructure.
Two applied immediately. Three deferred.

---

## Applied fixes

**AUD-T2-01 (P2) — Quickstart fails on stale dispatch index.**
`agent-quickstart` now regenerates the dispatch index before running the
test suite. The drift test no longer fires on a stale index in an active
development session.

**AUD-T2-02 (P2) — Quickstart double-output unexplained.**
Output line now reads: `Ran quickstart.cod → 'warm' (io.say prints + CLI
echoes return value)`. The double output is explained inline.

**AUD-T2-05 (P1 → P2) — CBOR endpoint unverifiable without decoder.**
`docs/FOR_AGENTS.md` now includes the stable public URLs for both endpoints
and explains that the CBOR form can be decoded with any RFC 8949 decoder or
with `python3 -m codifide capability --cbor`. Downgraded to P2 since the
JSON form is the human-verifiable alternative.

---

## Deferred findings

**AUD-T2-03 (P3)** — Cookbook URL not in manifest. Deferred: requires a
manifest schema amendment (`docs` field). Tracked for a future pass.

**AUD-T2-04 (P3)** — Feedback template not yet used in a real session.
Not a code fix — will be resolved when the next external agent session
uses the template.

---

## 289 tests passing, 0 regressions.
