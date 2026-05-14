# v2.0 A-Team Governance Review

**Date:** 2026-05-14  
**Persona:** Quill  
**Scope:** Post-overnight governance review — Axiom, Lumen, Relay, Sable passes on v2.0 work

---

## What happened

The overnight session shipped all four v2.0 requirements but skipped the
governance review steps. This dispatch records the A-Team review and the
fixes applied before the B-Team package is sent.

---

## Axiom findings (agent ergonomics)

**AX-01 (applied):** The Program 5 HTTP workflow in `docs/RPC_API.md` only
showed two symbols (`classify_content`, `route_message`) but the pipeline
requires three (`moderate` too). An agent following the example literally
would hit `unknown callable: 'moderate'`. Fixed: workflow now shows all
three symbols with a note on the transitive dependency pattern.

**AX-02 (applied):** The workflow assumed `jq` is installed. Added a Python
alternative for environments without it.

**AX-03 (applied):** The `--store` flag note in AGENT_QUICKREF didn't mention
the default store path (`~/.codifide/store`). Fixed.

**AX-04 (observation):** The bind-before-when error message is clear.
First-attempt success — no friction.

---

## Lumen findings (spec consistency)

**LU-01 (applied):** `docs/RPC_API.md` footer still said "Next: V2-1-3
(implement POST /symbols)" — stale. Updated to "Implemented v0.1 — May 2026".

**LU-02 (applied):** The 409 entry in the endpoint section was inconsistent
with the error table (409 not listed there). Clarified: 409 never occurs due
to idempotent writes; removed the ambiguity.

**LU-03 (applied):** The `/imports` endpoint field named `imports` but the
scope is one level only. Added explicit note: "The field is named `imports`
(not `direct_imports`) for brevity, but the scope is always one level."

**LU-04 (observation):** CAPABILITY.md docs field key order is alphabetical
in the manifest but not specified in the schema. Not a bug — JSON object
key order is not semantically significant. No fix needed.

---

## Relay findings (onboarding funnel)

**RE-01 (deferred):** `docs/AGENT_COOKBOOK.md` failure mode #1
(content-addressed composition) still describes the old CLI workflow. Needs
updating to show the HTTP workflow. Deferred — cookbook update is a separate
task, not a gate blocker.

**RE-02 (observation):** Time-to-first-working-program estimate: Programs 1–4
unchanged (~8 min). Program 5 via HTTP: ~15 min if agent reads RPC_API.md
carefully. Better than before but not yet under 5 minutes for Program 5.

---

## Sable findings (new surfaces)

**AUD-OVERNIGHT-01 (applied):** `invoke_defn_owned` unsafe lifetime extension
lacked a safety comment explaining why `drop(boxed)` must come after
`invoke_defn_inner`. Added explicit comment.

**AUD-OVERNIGHT-02 (applied):** Parallel evaluator branch interpreters don't
carry resolved imports. Added a comment documenting this as a known limitation
with a clear fix path.

**AUD-OVERNIGHT-03 (applied):** `resolve_imports_from_store` silently skipped
missing symbols. Now fails fast with a clear error message and `process::exit(1)`.

**AUD-OVERNIGHT-04 (applied):** `settimeout` on the listening socket doesn't
bound per-request read time. Added a comment documenting this limitation
honestly rather than giving false confidence.

---

## What I'm not yet sure of

Whether the B-Team will find anything the A-Team missed. The transitive
dependency gap (AX-01) is the most likely target — it's a real usability
hole that an adversarial reviewer would probe.
