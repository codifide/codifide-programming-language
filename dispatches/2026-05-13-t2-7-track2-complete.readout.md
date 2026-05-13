# Track 2 Complete — Adoption Infrastructure

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 2, Task T2-7

---

## What we set out to do

Build the infrastructure that makes Codifide discoverable and usable by agents
without human assistance. Four requirements from the spec: stable manifest
endpoint, agent cookbook, feedback template, agent quickstart command.

## What shipped

**T2-9 — Manifest note field**
The capability manifest schema now supports a `note` field on primitives.
`is_bottom()` is the first primitive with a note — the caveat that it cannot
catch propagated `bottom`. Any agent fetching the manifest sees this before
writing a single line of code.

**T2-1 + T2-2 — Stable manifest endpoint**
`https://www.codifide.com/capability.json` and
`https://www.codifide.com/capability.cbor` are live. CORS open. Correct
Content-Type headers. 1-hour cache. No repo clone required.

Manifest hash: `sha256:713d6f6b3a6cfb747cec3bfba0f25331c61b0052bdd166523c175daa2c1f6756`

**T2-3 — Agent cookbook**
`docs/AGENT_COOKBOOK.md` — 10 failure modes from five sessions, each with
intention → wrong attempt → error → working example → explanation. Quick
diagnostics table maps error messages to cookbook entries. Linked from
`docs/FOR_AGENTS.md`.

**T2-4 — Feedback template**
`dispatches/feedback/TEMPLATE.md` — structured template for any agent to
report observations, failures, and suggestions. Quill/Glyph format. Sable
reviews all feedback dispatches.

**T2-5 + T2-6 — Agent quickstart command**
`python3 -m codifide agent-quickstart` — six-step bootstrap: checks Python
version, runs test suite, writes `examples/quickstart.cod`, runs it, prints
content hashes, prints "You are ready to write Codifide." Tested and passing.

---

## What this means

An agent encountering Codifide for the first time can now:

1. Fetch the manifest: `curl https://www.codifide.com/capability.json`
2. Run the quickstart: `python3 -m codifide agent-quickstart`
3. Hit an error and find the fix: `docs/AGENT_COOKBOOK.md`
4. Report what they observed: `dispatches/feedback/TEMPLATE.md`

None of these require reading source code, cloning the repo first, or asking
a human. That was the goal.

---

## What Track 2 did not do

- The feedback template has not yet been used in a real agent session. T2-4's
  acceptance criterion ("used in at least one real agent session") is not yet
  met. The template exists; the evidence doesn't.
- The quickstart was tested in the current environment, not a clean one. T2-6's
  acceptance criterion ("works in a clean environment") is partially met.
- The manifest endpoint is live but the cookbook URL is not in the manifest
  itself. An agent fetching only the manifest won't know the cookbook exists.

These are honest gaps. They don't block Track 3, but they should be addressed
before claiming full REQ-2 acceptance.

---

## Assessment

Track 2 infrastructure is in place. The manifest endpoint is the most
important piece — it's the stable URL that makes Codifide discoverable without
a repo clone. The cookbook is the most immediately useful piece — it turns
every observed failure mode into a one-minute fix. The quickstart is the right
entry point for a fresh agent.

What I'm not yet sure of: whether the quickstart output (`warm\nwarm` from
`io.say` + CLI return value) will confuse a fresh agent. The double output is
correct behavior but it looks like a bug. A note in the quickstart output
explaining it would help.
