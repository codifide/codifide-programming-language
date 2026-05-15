# Codifide v4.0 — G1 Requirements

**Date:** 2026-05-14  
**Author:** Douglas Jones + Claude (Harper/Lumen)  
**Status:** G1 — requirements defined, proceeding to implementation

---

## REQ-V4-1: Runtime type enforcement

**Priority:** P1  
**Evidence:** G0 Problem 1. Every case study agent wrote `sig` declarations
that were never checked. The language claims trustworthy contracts but does
not enforce the most basic one.

### Requirements

1. The interpreter checks argument types against `sig` parameter declarations
   at every call boundary.
2. A new typed error `TypeViolation` is raised when a type mismatch is
   detected. It is fatal (consistent with other typed errors).
3. Type checking is best-effort for `Any` — `Any` accepts all values.
4. Type checking covers the declared literal types:
   `Bool`, `Float`, `Int`, `String`, `List`, `Label`, `Number`, `Unit`.
5. `Number` accepts both `Int` and `Float` (it is the supertype).
6. `Label` is a `String` subtype — a `Label` is a `String`, but a bare
   `String` is not a `Label` unless it was produced by a belief-dispatched
   function.
7. Return type checking: the return value is checked against the `sig`
   return type declaration.
8. Effect declarations are already enforced transitively. Type enforcement
   is additive — it does not replace effect enforcement.
9. `Image` and `Clock` are opaque host types; type checking accepts any
   value produced by `host_image()` or `clock.now` respectively.

### Acceptance criteria

- `def f sig (n: Int) -> String effects {} cand str(n)` called with a
  `Float` raises `TypeViolation` with a message naming the parameter,
  expected type, and actual type.
- `def f sig (n: Number) -> String effects {} cand str(n)` called with
  either `Int` or `Float` succeeds.
- `def f sig (n: Any) -> String effects {} cand str(n)` called with any
  value succeeds.
- All 386 existing tests still pass (no regressions from type enforcement
  on well-typed programs).
- New test suite `tests/test_type_enforcement.py` with ≥ 20 tests covering
  all declared types, `Number` supertype, `Any` wildcard, and error message
  shape.

### NFRs

- Type checking adds < 5% overhead to interpreter call dispatch (measured
  on the pipeline task spec programs).
- `TypeViolation` message format: `type error: parameter '<name>' expects
  <Type> but got <actual_type> (<value_repr>)`.

---

## REQ-V4-2: Standard library

**Priority:** P1  
**Evidence:** G0 Problem 2. No real-world agent pipeline can be written
without file I/O, HTTP, JSON, or date arithmetic.

### Requirements

#### V4-2a: File I/O primitives

1. `io.read(path: String) -> String` — read a file by path, return its
   contents as a string. Effect: `io.read`.
2. `io.write(path: String, content: String) -> Unit` — write a string to
   a file. Effect: `io.write`.
3. `io.exists(path: String) -> Bool` — check whether a path exists. Effect:
   `io.read` (read-only filesystem access).
4. Path traversal defense: `io.read` and `io.write` reject paths containing
   `..` with a `PrimitiveError`.
5. Size bound: `io.read` rejects files larger than 16 MiB (consistent with
   the CLI source-read bound).

#### V4-2b: HTTP client primitives

1. `http.get(url: String) -> String` — HTTP GET, return response body as
   string. Effect: `http.fetch`.
2. `http.post(url: String, body: String) -> String` — HTTP POST with string
   body, return response body. Effect: `http.fetch`.
3. Both primitives raise `PrimitiveError` on non-2xx responses, including
   the status code in the message.
4. Timeout: 30 seconds (consistent with existing `store push` timeout).
5. Response size bound: 16 MiB.
6. HTTPS only — `http://` URLs raise `PrimitiveError` with a message
   directing the caller to use HTTPS.

#### V4-2c: JSON primitives

1. `json.parse(s: String) -> Any` — parse a JSON string, return a Codifide
   value. Effect: none (pure).
2. `json.encode(v: Any) -> String` — encode a Codifide value as JSON.
   Effect: none (pure).
3. JSON objects map to Codifide dicts (key-value pairs accessible via
   `at(obj, "key")`). JSON arrays map to Codifide lists. JSON strings,
   numbers, booleans, and null map to their Codifide equivalents.
4. `json.parse` raises `PrimitiveError` on invalid JSON.
5. `json.encode` raises `PrimitiveError` on values that cannot be
   represented in JSON (e.g. `bottom`, `Image`).

#### V4-2d: Date arithmetic primitives

1. `clock.today() -> String` — return today's date as `"YYYY-MM-DD"`.
   Effect: `clock.read`.
2. `clock.parse(s: String) -> Int` — parse a date string `"YYYY-MM-DD"`
   and return a Unix timestamp (seconds since epoch). Effect: none (pure).
3. `clock.add_days(ts: Int, n: Int) -> Int` — add `n` days to a Unix
   timestamp. Effect: none (pure).
4. `clock.format(ts: Int, fmt: String) -> String` — format a Unix timestamp
   using a strftime-style format string. Effect: none (pure).

### Acceptance criteria

- `io.read("/tmp/test.txt")` reads and returns the file contents.
- `io.read("../../etc/passwd")` raises `PrimitiveError` (path traversal).
- `http.get("https://codifide.com/capability.json")` returns the capability
  JSON string (integration test, network required, marked as such).
- `http.get("http://example.com")` raises `PrimitiveError` (HTTPS only).
- `json.parse('{"key": "value"}')` returns a value where
  `at(result, "key")` returns `"value"`.
- `json.encode(list(1, 2, 3))` returns `"[1, 2, 3]"`.
- `clock.today()` returns a string matching `YYYY-MM-DD`.
- All 386 existing tests still pass.
- New test suite `tests/test_stdlib.py` with ≥ 30 tests.

### NFRs

- New effects (`io.read`, `io.write`, `http.fetch`) are declared in the
  capability manifest.
- New primitives are declared in the capability manifest.
- `docs/AGENT_QUICKREF.md` updated with new primitive groups.
- `docs/AGENT_COOKBOOK.md` gains entries for common stdlib patterns.

---

## REQ-V4-3: Public registry — seeded and operated

**Priority:** P2  
**Evidence:** G0 Problem 3. V3-2 shipped the infrastructure; the registry
is empty. The multi-agent protocol story requires content.

### Requirements

1. The five canonical pipeline programs from the case studies are published
   to the public registry at `codifide.com`.
2. `python3 -m codifide store push <hash> --registry https://codifide.com`
   is the documented publish path and works end-to-end.
3. `docs/REGISTRY.md` documents the public registry: what's in it, how to
   publish, how to resolve, hash stability guarantees.
4. The capability manifest gains a `registry` field pointing to the public
   registry URL.
5. `AGENT_COOKBOOK.md` gains an entry for the publish-and-resolve workflow.

### Acceptance criteria

- `python3 -m codifide run pipeline_composed.cod --registry https://codifide.com`
  resolves the pipeline symbols from the public registry without a local store.
- The five canonical symbols are resolvable by their published hashes.
- `docs/REGISTRY.md` exists and is complete.

### NFRs

- This is primarily a documentation and operational task, not a code task.
  The code (V3-2) already exists.

---

## REQ-V4-4: Network-safe server

**Priority:** P3  
**Evidence:** G0 Problem 4. AUD-RPC-02 (P2 Sable finding). The server
cannot be safely exposed over a network without auth and TLS.

### Requirements

1. `python3 -m codifide serve --auth-token <token>` enables bearer token
   authentication. All requests must include `Authorization: Bearer <token>`.
   Requests without a valid token receive `401 Unauthorized`.
2. `python3 -m codifide serve --cert <path> --key <path>` enables TLS.
   When TLS is configured, the server binds to the configured host (not
   just `127.0.0.1`).
3. When neither `--auth-token` nor `--cert` is configured, the server
   continues to bind to `127.0.0.1` only and logs a warning that it is
   not safe for network exposure.
4. `docs/RPC_API.md` updated with auth and TLS documentation.
5. Sable audit of the auth implementation before shipping.

### Acceptance criteria

- A request without a valid token to an auth-enabled server returns 401.
- A request with a valid token succeeds.
- A server started without `--auth-token` on a non-loopback interface
  logs a warning and refuses to start (fail-safe).
- All existing RPC API tests pass with and without auth configured.
- New tests in `tests/test_server.py` covering auth paths.

### NFRs

- The auth token is compared in constant time (timing-safe comparison).
- TLS configuration is documented with a `openssl req` example for
  self-signed certs.

---

## Out of scope for v4.0

- Full static type inference (V4-1 is runtime only)
- Hosted runtime / cloud execution
- Time-indexed types (V3-4, still deferred)
- Editor integration
- Structural diff and merge
- Effect inference

---

## Implementation sequencing

1. **V4-1** (type enforcement) — touches the interpreter call path. Do first
   so all subsequent stdlib work is type-checked from the start.
2. **V4-2** (stdlib) — four independent sub-requirements, can be done in
   any order after V4-1.
3. **V4-3** (public registry) — mostly operational. Can proceed in parallel
   with V4-1/V4-2.
4. **V4-4** (network-safe server) — last, after V4-3 makes the server
   worth exposing.

---

*Spec version 1.0 — May 2026*  
*Author: Douglas Jones + Claude*  
*Governed by: GOVERNANCE.md*
