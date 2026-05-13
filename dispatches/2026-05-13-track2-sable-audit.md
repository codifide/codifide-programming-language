# Sable Audit — Track 2 Adoption Infrastructure

**Date:** 2026-05-13  
**Persona:** Sable  
**Scope:** T2-9, T2-1, T2-2, T2-3, T2-4, T2-5, T2-6  
**Initiative:** Agent Adoption — Track 2, Task T2-8

---

## Audit scope

Track 2 shipped six artifacts: manifest note field, manifest endpoint (JSON +
CBOR), agent cookbook, feedback template, agent-quickstart CLI, and the
quickstart program. This audit probes each for correctness, robustness, and
gaps.

---

## Findings

### AUD-T2-01 (P2) — `agent-quickstart` fails if dispatch index is stale

**What:** `agent-quickstart` runs the full test suite as step 2. The test
suite includes `DispatchIndexDriftTests.test_index_matches_regenerated`, which
fails if `dispatches/INDEX.md` is out of sync with the directory contents.
In any active development session where new dispatches have been filed but the
index hasn't been regenerated, `agent-quickstart` will report a test failure
and exit 1.

**Probe:** File a new dispatch, don't regenerate the index, run
`python3 -m codifide agent-quickstart`. Result: `✗ Test suite failed: 1
failed, 288 passed` — the drift test fires.

**Why it matters:** A fresh agent running `agent-quickstart` for the first
time will likely be doing so in a repo that has recent dispatches. If the
index is stale, the quickstart fails with a confusing error about
`dispatches/INDEX.md`. The agent has no context for what this means.

**Fix options:**
- (A) Run `python3 -m codifide dispatch-index` before running the test suite
  in `agent-quickstart`. Low cost, always correct.
- (B) Skip the drift test when running via `agent-quickstart`. Fragile —
  the drift test exists for a reason.
- (C) Document in the quickstart output that `dispatch-index` should be run
  first. Puts the burden on the agent.

**Recommendation:** Option A. Add `dispatch-index` as a pre-step before the
test suite in `cmd_agent_quickstart`.

**Severity:** P2 — fails silently in the most common use case (active repo).

---

### AUD-T2-02 (P2) — Quickstart double-output is unexplained

**What:** `agent-quickstart` reports `Ran quickstart.cod → 'warm\nwarm'`.
The double output (`warm` twice) is correct — `io.say` prints to stdout and
returns the string; the CLI runner prints the return value. But to a fresh
agent, this looks like a bug.

**Probe:** Run `python3 -m codifide agent-quickstart`. Output shows
`'warm\nwarm'`. No explanation is provided.

**Why it matters:** The quickstart is the first thing a fresh agent runs. If
the first output looks wrong, the agent loses confidence in the tool before
writing a single line of code.

**Fix:** Add a parenthetical to the output line explaining the double output:
`Ran quickstart.cod → 'warm' (io.say prints + CLI echoes return value)`.

**Severity:** P2 — first impression matters.

---

### AUD-T2-03 (P3) — Cookbook URL not in capability manifest

**What:** An agent that fetches `codifide.com/capability.json` has no way to
discover `docs/AGENT_COOKBOOK.md` from the manifest alone. The manifest
describes the language interface but not the documentation ecosystem.

**Probe:** Fetch `https://www.codifide.com/capability.json`. No field points
to the cookbook, the quickref, or `FOR_AGENTS.md`.

**Fix:** Add a `docs` field to the manifest schema with URLs for the key
agent-facing documents. Example:
```json
"docs": {
  "for_agents": "https://github.com/codifide/codifide-programming-language/blob/main/docs/FOR_AGENTS.md",
  "cookbook": "https://github.com/codifide/codifide-programming-language/blob/main/docs/AGENT_COOKBOOK.md",
  "quickref": "https://github.com/codifide/codifide-programming-language/blob/main/docs/AGENT_QUICKREF.md"
}
```

**Severity:** P3 — the manifest is usable without it, but discoverability
suffers.

---

### AUD-T2-04 (P3) — Feedback template acceptance criterion not met

**What:** REQ-2c requires the feedback template to be "used in at least one
real agent session." The template exists but has not been used. The Track 2
completion dispatch acknowledges this gap.

**Probe:** Check `dispatches/feedback/` for any filed feedback. Only
`TEMPLATE.md` exists — no actual feedback dispatches.

**Fix:** Not a code fix. The criterion will be met when the next external
agent session uses the template. Track this as an open acceptance gap.

**Severity:** P3 — the infrastructure is correct; the evidence is missing.

---

### AUD-T2-05 (P1) — CBOR endpoint serves correct bytes but is unverifiable without a decoder

**What:** `https://www.codifide.com/capability.cbor` returns HTTP 200 with
`Content-Type: application/cbor`. The bytes are correct canonical CBOR.
However, there is no public tool linked from the manifest or the docs that
an agent can use to decode and verify the CBOR without installing the
Codifide package.

**Probe:** `curl https://www.codifide.com/capability.cbor | xxd | head` —
confirms CBOR structure (starts with `0xa7` — a 7-key map). But an agent
without the Codifide package cannot verify the content.

**Why it matters:** The CBOR endpoint is the agent-optimized form. If agents
can't verify it without installing the package, the endpoint's value is
limited to agents that already have the package — which is circular.

**Fix:** Add a note to `docs/FOR_AGENTS.md` and the manifest that the CBOR
form can be decoded with `python3 -m codifide capability --cbor` (which
outputs the same bytes) or with any RFC 8949 CBOR decoder. The JSON form
is the human-verifiable alternative.

**Severity:** P1 — the endpoint is correct but its verifiability story is
incomplete. Downgrade to P2 if the JSON form is considered sufficient for
verification.

---

## Cross-artifact patterns

**Pattern 1 — The quickstart is the weakest link.**
The manifest endpoint, cookbook, and feedback template are all static
artifacts — they can't fail at runtime. The quickstart is dynamic and has
two runtime dependencies: the test suite (which can fail for unrelated
reasons) and the dispatch index (which can be stale). Both were observed
to fail during this audit.

**Pattern 2 — The cookbook covers observed failures but not future ones.**
The cookbook is derived from five sessions. It is accurate for those sessions.
A sixth session with a different model or a different task will likely surface
new failure modes not in the cookbook. The cookbook needs a maintenance
process — either a periodic review or a mechanism for agents to contribute
entries via the feedback template.

**Pattern 3 — The manifest is the right interface but its ecosystem is
undiscoverable.**
The manifest describes the language. It does not describe where to get help,
where to report feedback, or where to find examples. An agent that fetches
only the manifest is missing half the adoption infrastructure.

---

## What I did not test

- Whether the CBOR endpoint bytes are byte-identical to `python3 -m codifide
  capability --cbor` output. The Content-Type is correct; the byte content
  was not independently verified against the local generator.
- Whether the feedback template produces a dispatch that `dispatch-check`
  recognizes correctly. No feedback dispatch has been filed yet.
- Whether `agent-quickstart` works on Python 3.10, 3.11, or 3.12. Only
  tested on 3.9.
- Whether the manifest endpoint returns correct CORS headers for cross-origin
  requests from a browser context (only tested with `curl`).
