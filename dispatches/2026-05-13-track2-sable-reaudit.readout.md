# Track 2 Sable Re-audit — Untested Probes + New Finding

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 2, supplemental audit

---

## What happened

The original Track 2 Sable audit listed four things she did not test. Those
probes were run. Three came back clean. One surfaced a new P2 finding that
the original audit missed entirely.

---

## Probes run

**CBOR bytes byte-identical to local generator:** ✅ MATCH — md5 of
`curl capability.cbor` equals md5 of `python3 -m codifide capability --cbor`.

**Feedback template dispatch-check recognition:** ✅ — a `.readout.md` filed
under `dispatches/feedback/` is correctly excluded by the `feedback_dir_prefix`
check in `dispatch_index.py`. `dispatch-check` exits 0 with a feedback
readout present.

**CORS headers for cross-origin requests:** ✅ — `curl -H "Origin:
https://example.com"` returns `Access-Control-Allow-Origin: *` on both
endpoints.

**Content negotiation:** ✅ — `Accept: text/html` request returns
`application/json; charset=utf-8`. Vercel serves the static file regardless
of Accept header.

---

## New finding — AUD-T2-06 (P2)

**Quickstart claims to demonstrate content addressing but doesn't store anything.**

The quickstart comment says *"every symbol has a stable hash identity"* and
the output prints hashes. But the command used was `store hash` — which
computes hashes without storing. The symbols were never in the store. An agent
following the quickstart and then trying `import classify_greeting =
sha256:...` would get `cannot resolve import` because nothing was stored.

**Probe:** Run `agent-quickstart`. Check `python3 -m codifide store list`
before and after. Store count unchanged — nothing stored.

**Fix applied:** Changed `store hash` to `store put` in `cmd_agent_quickstart`.
Output now reads: `(symbols stored — importable via 'import name = sha256:<hash>')`.

**Verified:** Store count increases after quickstart. Hashes printed are the
stored identities.

---

## Sable's verdict on the original audit

The original audit was not clean. It found five real issues and deferred
four probes. Three of the deferred probes came back clean. One missed a P2
finding. The original audit should have run all four probes before filing.

The pattern: Sable listed what she didn't test, which is correct discipline.
But "what I didn't test" is not a substitute for testing it. The untested
probes should have been run before the audit was filed.
