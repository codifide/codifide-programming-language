# Codifide — Roadmap

This roadmap is evidence-driven. Every v2.0 item is justified by at least one
finding from the Agent Adoption Initiative (Track 1 case studies, Track 2
infrastructure audit). Items without adoption evidence are explicitly deferred
with a reason.

---

## Shipped

### v1.0 — 2026-05-11

The reference implementation. Everything an agent needs to write Codifide
programs today.

- Canonical JSON + CBOR forms with SHA-256 content addressing (CBOR primary)
- Surface parser with multi-line expression continuation, fuzz-hardened
- Tree-walking interpreter: transitive effect checking, pre/post contract
  enforcement, multi-candidate dispatch, cost-based dispatch, belief dispatch,
  inline `if/then/else`, first-class refusal (`bottom`), 8 typed error kinds
- Indexed primitives: `slice`, `at`, `char_at`, `indexof`
- Content-addressed symbol store with GC, atomic writes, sharded loose objects
- Content-addressed imports (`import foo = sha256:...`)
- Capability manifest (`python3 -m codifide capability`) — agent-facing
  self-description, content-addressed, generated from the implementation
- Rust canonical crate — byte-level conformance to Python
- 216 Python tests, 28 Rust canonical tests

### v2.0 Shape A — 2026-05-12

- Rust interpreter and Rust parser
- Parallel evaluator
- Benchmarks

### Agent Adoption Initiative — 2026-05-13

- Capability manifest endpoints: `codifide.com/capability.json` and
  `codifide.com/capability.cbor`
- `docs/AGENT_COOKBOOK.md` — 10 failure modes from 5 sessions
- `dispatches/feedback/TEMPLATE.md` — structured feedback template
- `python3 -m codifide agent-quickstart` — bootstrap command
- Manifest `note` field for primitives with non-obvious semantics
- Runtime hints: bind-before-when, `is_bottom()` trap, from-import error

---

### v2.0 — Evidence-driven priorities (SHIPPED 2026-05-14)

All four v2.0 priorities shipped in a single overnight session.

### P1 — RPC API ✅

**Evidence:** Program 5 (content-addressed composition) was the universal
failure point across all three Track 1 sessions. Every agent had to manually
run `store put`, `store hash`, `store index`, set `CODIFIDE_RUNTIME=python`,
and write `from`-import syntax. An RPC API that accepts canonical form
directly would eliminate all of this — an agent could publish a symbol, get
its hash, and compose without touching the CLI or the runtime flag.

**What it is:** A network interface (HTTP or gRPC) that accepts canonical
CBOR, stores it, returns its hash, and resolves imports. Agents speak
canonical form directly; no surface syntax required.

**Acceptance criterion:** An agent can complete Program 5 of the pipeline
task spec using only HTTP requests — no CLI, no runtime flag.

---

### P2 — Static bind-before-when detection in the parser ✅

**Evidence:** Claude (T1-4) hit `unbound name: 'label'` when writing a `cand`
block with a bind followed by a `when` guard. GPT-4o and Gemini avoided it by
accident (different routing patterns). Any agent that reaches for the
idiomatic multi-branch dispatch shape will hit it. The parser currently
accepts the pattern and the runtime fails with a misleading error.

**What it is:** Scope tracking in the parser so bind-before-when is rejected
at parse time with a clear message, not at runtime with `unbound name`.

**Acceptance criterion:** `cand label <- f() when eq(label, x) "y"` raises
`ParseError` with a message explaining guard-before-body execution order.

---

### P3 — Manifest `docs` field ✅

**Evidence:** AUD-T2-03 (Track 2 Sable audit). An agent that fetches
`codifide.com/capability.json` has no way to discover the cookbook, quickref,
or `FOR_AGENTS.md` from the manifest alone. The manifest describes the
language but not its documentation ecosystem.

**What it is:** A `docs` field in the manifest schema with stable URLs for
the key agent-facing documents.

**Acceptance criterion:** `python3 -m codifide capability | jq .docs` returns
URLs for `FOR_AGENTS.md`, `AGENT_COOKBOOK.md`, and `AGENT_QUICKREF.md`.

---

### P3 — `from`-import support in the Rust parser ✅

**Evidence:** All three Track 1 agents needed `CODIFIDE_RUNTIME=python` for
Program 5. The Rust parser does not support `from`-import syntax. This is a
known v2.0 gap documented in the quickref and the error message, but it means
the default runtime can't do content-addressed composition.

**What it is:** Implement `from <hash> import name, name` in the Rust parser
and interpreter.

**Acceptance criterion:** Program 5 of the pipeline task spec runs without
`CODIFIDE_RUNTIME=python`.

---

## Deferred — no adoption evidence

The following items appeared on the pre-adoption roadmap. No agent session
produced evidence that they are needed. Deferred until evidence emerges.

**Effect inference** (partially elide `effects` declarations): No agent
struggled with effect declarations. All three Track 1 models correctly wrote
`effects {}` and `effects {io.stdout}`. Gemini missed `effects {io.stdout}`
on `main` but self-corrected. Effect declarations are not a friction point.

**Time-indexed types** (`T@<timestamp>`): No agent attempted time-dependent
programs. No adoption evidence.

**Editor integration** (hypergraph display): No adoption evidence. The
capability manifest and content-addressed store are the right agent
interfaces; a visual editor is a human interface.

**Structural diff and merge**: No adoption evidence.

## Deferred — blocked on other v2.0 work

**Graph-native parallel runtime** (beyond v2.0 Shape A): The Rust parallel
evaluator shipped in v2.0 Shape A. Further parallelism work is deferred until
the RPC API is in place — the API boundary is where parallelism matters most
for agent use cases.

---

## What comes after v2.0

v3.0 territory — not planned, not promised:

- Hosted runtime / cloud service
- Certification program for conforming implementations
- Moltbook integration (agent social network — requires RPC API first)
- Time-indexed types (if adoption evidence emerges)

---

*Roadmap version 2.0 — May 2026*  
*Updated by: Douglas Jones + Claude*  
*Evidence base: Agent Adoption Initiative dispatches, 2026-05-13*  
*Governed by: GOVERNANCE.md*
