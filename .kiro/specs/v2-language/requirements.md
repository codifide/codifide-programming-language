# Codifide v2.0 Language Work — Requirements

## Overview

v2.0 language work is driven by the Agent Adoption Initiative findings.
Every requirement here is justified by at least one finding from Track 1
(case studies) or Track 2 (infrastructure audit). Items without adoption
evidence are not in scope.

Evidence base: `dispatches/2026-05-13-track1-summary.*`,
`dispatches/2026-05-13-track2-sable-audit.md`,
`dispatches/2026-05-13-track2-sable-reaudit.*`

---

## REQ-V2-1: RPC API

**Priority:** P1

**Evidence:** Program 5 (content-addressed composition) was the universal
failure point across all three Track 1 sessions (T1-2, T1-3, T1-4). Every
agent had to manually manage the store CLI, set `CODIFIDE_RUNTIME=python`,
and write `from`-import syntax. The friction is in the composition layer,
not the language semantics.

**Requirement:** A network interface (HTTP or gRPC) that accepts canonical
CBOR, stores it, returns its hash, and resolves imports. Agents speak
canonical form directly without surface syntax or CLI.

**Acceptance criteria:**
- An agent can publish a symbol via HTTP POST and receive its SHA-256 hash
- An agent can resolve an import by hash via HTTP GET
- An agent can complete Program 5 of `docs/AGENT_TASK_SPEC.md` using only
  HTTP requests — no CLI, no `CODIFIDE_RUNTIME=python`
- The API accepts canonical CBOR (primary) and canonical JSON (secondary)
- The API is documented in `docs/RPC_API.md`

---

## REQ-V2-2: Static bind-before-when detection

**Priority:** P2

**Evidence:** Claude (T1-4) hit `unbound name: 'label'` when writing a `cand`
block with a bind followed by a `when` guard. The pattern is syntactically
accepted by the parser and fails at runtime with a misleading error. GPT-4o
and Gemini avoided it by accident. Any agent reaching for idiomatic
multi-branch dispatch will hit it.

**Requirement:** The parser detects bind-before-when statically and raises
`ParseError` with a message explaining guard-before-body execution order.

**Acceptance criteria:**
- `cand label <- f() when eq(label, x) "y"` raises `ParseError` (not
  `unbound name` at runtime)
- Error message names the fix: move bind into body, use `if/then/else`
- Existing programs with correct bind placement are unaffected
- The runtime hint added in post-T1-4 fixes can be removed once the parser
  catches it statically

---

## REQ-V2-3: `from`-import in Rust parser

**Priority:** P3

**Evidence:** All three Track 1 agents needed `CODIFIDE_RUNTIME=python` for
Program 5. The Rust parser does not support `from <hash> import name` syntax.
This means the default runtime cannot do content-addressed composition.

**Requirement:** Implement `from <hash> import name, name` in the Rust parser
and interpreter, with store resolution.

**Acceptance criteria:**
- Program 5 of `docs/AGENT_TASK_SPEC.md` runs without `CODIFIDE_RUNTIME=python`
- Byte-level conformance with Python runtime on all existing test programs
- The `CODIFIDE_RUNTIME=python` note in `docs/AGENT_QUICKREF.md` can be removed

---

## REQ-V2-4: Manifest `docs` field

**Priority:** P3

**Evidence:** AUD-T2-03 (Track 2 Sable audit). An agent fetching
`codifide.com/capability.json` cannot discover the cookbook, quickref, or
`FOR_AGENTS.md` from the manifest alone.

**Requirement:** Add a `docs` field to the capability manifest schema with
stable URLs for key agent-facing documents.

**Acceptance criteria:**
- `python3 -m codifide capability | jq .docs` returns URLs for
  `FOR_AGENTS.md`, `AGENT_COOKBOOK.md`, and `AGENT_QUICKREF.md`
- The manifest drift test catches changes to the `docs` field
- `docs/CAPABILITY.md` documents the `docs` field schema

---

## Out of scope for v2.0

- Effect inference — no adoption evidence
- Time-indexed types — no adoption evidence
- Editor integration — no adoption evidence
- Structural diff and merge — no adoption evidence
- Hosted runtime / cloud service — v3.0 territory
- Certification program — v3.0 territory

---

*Spec version 1.0 — May 2026*  
*Author: Douglas Jones + Claude*  
*Governed by: GOVERNANCE.md*
