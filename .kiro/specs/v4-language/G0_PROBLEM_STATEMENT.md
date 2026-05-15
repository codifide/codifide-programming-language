# Codifide v4.0 — G0 Problem Statement

**Date:** 2026-05-14  
**Author:** Douglas Jones + Claude (Aegis/Harper)  
**Status:** G0 — approved, proceeding to G1

---

## Why v4.0?

The gap analysis from the "is this usable in the wild?" question identified
four structural gaps between Codifide as a research prototype and Codifide
as a usable tool. Each gap is a concrete, fixable problem. None requires
rethinking the language design.

---

## Problem 1 — `sig` declarations are decorative, not enforced

**What breaks without this:** An agent can declare `sig (n: Int) -> String`
and pass a `Float` or a `List`. The runtime either silently coerces, fails
at the primitive level with a confusing error, or produces wrong output.
The type system is a lie. Agents that trust it will be misled.

**Evidence:** Every case study agent wrote `sig` declarations. None of them
were checked. The language claims to be designed for agents who need
trustworthy contracts — but the most basic contract (type) is not enforced.

**Scope:** Runtime type checking at call boundaries. Not full static type
inference. Check argument types against `sig` declarations when types are
known. Raise a typed `TypeViolation` error on mismatch.

**Risk:** Medium. Touches the interpreter call path. Existing programs that
accidentally pass wrong types will now fail loudly instead of silently.
That is the correct behavior.

---

## Problem 2 — No standard library

**What breaks without this:** Agents cannot write programs that read files,
make HTTP requests, parse JSON, or do date arithmetic. Every real-world
agent pipeline needs at least one of these. The current primitive set covers
string manipulation and arithmetic but nothing that touches the outside world
beyond `io.say` and `clock.now`.

**Evidence:** The "usable in the wild" assessment identified this as a
hard blocker for real-world use. The content-moderation pipeline task spec
(the canonical test) uses only string primitives — it was designed to avoid
this gap, not to demonstrate the language is complete.

**Scope:** Four new effect groups:
- `io.read` — read a file by path, return string
- `http.get` / `http.post` — HTTP client primitives
- `json.parse` / `json.encode` — JSON round-trip
- `clock.date` — structured date arithmetic beyond `clock.now.hm`

**Risk:** Medium. New effect declarations, new primitives, new error kinds.
Does not touch existing primitives or the canonical form for existing programs.

---

## Problem 3 — No operated public registry

**What breaks without this:** V3-2 shipped remote symbol resolution
infrastructure, but the registry at `codifide.com/symbols/<hash>` is empty.
Two agents cannot exchange symbols without out-of-band coordination because
there is nowhere to publish to. The multi-agent protocol story is
infrastructure without content.

**Evidence:** V3-2 acceptance criterion was "agent on machine B resolves a
symbol published by agent on machine A." That works mechanically but requires
both agents to be running their own servers. A public registry with real
symbols in it is the missing piece.

**Scope:** Operate the public registry endpoint. Seed it with the canonical
pipeline task spec symbols (the five programs from the case studies). Document
the publish workflow. Add `codifide store push --registry https://codifide.com`
as the canonical publish path.

**Risk:** Low for the code (already exists). Medium for operations (requires
a running server, storage, and uptime commitment).

---

## Problem 4 — Server is 127.0.0.1 only

**What breaks without this:** The RPC server cannot be used for multi-machine
agent coordination without a reverse proxy, TLS, and auth — none of which are
documented or provided. The V3-2 remote registry works around this by using
the public endpoint, but any team wanting to run a private registry is on
their own.

**Evidence:** The Sable audit of V2-1 flagged AUD-RPC-02 (no socket timeout,
slow-loris risk) as P2. The server was explicitly documented as "local-only,
trusted caller." That is the right call for v2.0 but not for v4.0 where
multi-machine use is the goal.

**Scope:** Add an `--auth-token` flag for bearer token authentication. Add
TLS support via `--cert` / `--key` flags (or document the reverse proxy
pattern). Remove the "not safe to expose over a network" warning when auth
is configured. Update `docs/RPC_API.md`.

**Risk:** Medium-high. Security-sensitive. Requires Sentinel review and
Sable audit before shipping.

---

## Prioritization

| ID | Problem | Priority | Risk | Dependency |
|----|---------|----------|------|------------|
| V4-1 | Runtime type enforcement | P1 | Medium | None |
| V4-2 | Standard library | P1 | Medium | None |
| V4-3 | Public registry (operated) | P2 | Low/Medium | V3-2 (shipped) |
| V4-4 | Network-safe server | P3 | Medium-High | V4-3 |

V4-1 and V4-2 are independent and can be implemented in parallel.
V4-3 is mostly operational, not code. V4-4 depends on V4-3 being
useful first.

---

## What is explicitly out of scope for v4.0

- **Full static type inference** — V4-1 is runtime checking only. Static
  inference requires a type system design that is not yet specified.
- **Hosted runtime / cloud execution** — no adoption evidence.
- **Time-indexed types (V3-4)** — still deferred, still no evidence.
- **Editor integration** — still deferred.
- **Structural diff and merge** — still deferred.

---

## G0 decision

**Approved.** All four problems are real, bounded, and worth solving.
Evidence is direct (case study findings, Sable audit findings, gap analysis).
Scope is honest. Proceeding to G1.

*Aegis sign-off: approved 2026-05-14*
