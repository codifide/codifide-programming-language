# Sable Audit — RPC API (V2-1-8)

**Date:** 2026-05-14  
**Persona:** Sable  
**Scope:** `codifide/server.py`, `docs/RPC_API.md`, `python3 -m codifide serve` CLI subcommand  
**Initiative:** REQ-V2-1, Task V2-1-8

---

## Audit scope

The RPC API server is a new attack surface. This audit checks:
- Sandboxing: can a caller escape the store root via the HTTP layer?
- Denial of service: can a caller exhaust resources?
- Error surface: do typed errors stay typed, or do host exceptions leak?
- Spec/implementation agreement: does the server behave as `docs/RPC_API.md` says?
- Coverage gaps: what did the tests not exercise?

---

## Findings

### AUD-RPC-01 (P2) — Negative Content-Length not rejected

**What:** `_read_body` parses `Content-Length` with `int(length_str)`. A
negative value (e.g. `Content-Length: -1`) passes the `> _MAX_BODY_BYTES`
check and then calls `handler.rfile.read(-1)`, which reads until EOF on
most Python socket implementations — effectively an unbounded read.

**Probe:**
```python
req = urllib.request.Request(url, data=b"x", method="POST",
    headers={"Content-Type": "application/cbor", "Content-Length": "-1"})
# On CPython 3.9, urllib raises before sending the negative header,
# but a raw socket client can send it.
```

**Fix:** Add `if length < 0: return None` after parsing the integer.

**Severity:** P2 — exploitable only by a raw socket client (urllib refuses
to send negative Content-Length), but the defense should be explicit.

---

### AUD-RPC-02 (P2) — No timeout on socket reads

**What:** `_read_body` calls `handler.rfile.read(length)` with no timeout.
A slow client that sends one byte per second for a 16 MiB body holds a
server thread for ~4.7 hours. With `ThreadingHTTPServer`, this exhausts
the thread pool under sustained slow-loris attack.

**Fix:** Set a socket timeout on the server. `http.server.HTTPServer`
inherits from `socketserver.TCPServer`; the socket timeout can be set
after `make_server` returns:
```python
server.socket.settimeout(30)  # 30 seconds per request
```

**Severity:** P2 — local-only server, so the attacker must be local. Still
worth fixing before any network exposure.

---

### AUD-RPC-03 (P3) — `hashlib` imported but unused in server.py

**What:** `import hashlib` appears at the top of `server.py` but is never
called. The hash computation happens inside the store layer.

**Fix:** Remove the unused import.

**Severity:** P3 — cosmetic, but unused imports are noise and can mislead
readers into thinking the server does its own hashing.

---

### AUD-RPC-04 (P3) — `/imports` resolves one level only; not documented

**What:** `GET /symbols/<id>/imports` returns the direct imports of the
stored module, not the transitive closure. The spec (`docs/RPC_API.md`)
says "resolve the import graph" which implies transitive resolution, but
the implementation is one level. An agent that calls `/imports` on a
composed module and sees `"missing": []` may incorrectly conclude the
full dependency graph is present.

**Fix:** Either (a) implement transitive resolution, or (b) rename the
endpoint to `/direct-imports` and update the spec to say "direct imports
only." Option (b) is cheaper and more honest.

**Severity:** P3 — the acceptance test passes because the test explicitly
publishes all three symbols. A naive agent relying on `/imports` to
discover missing deps would be misled.

---

### AUD-RPC-05 (P3) — `os` and `threading` imported but unused in server.py

**What:** `import os` and `import threading` appear at the top of
`server.py` but are never called directly (threading is used indirectly
via `ThreadingHTTPServer`).

**Fix:** Remove `import os`. Keep `import threading` only if it's needed
for type annotations or explicit use; otherwise remove it too.

**Severity:** P3 — cosmetic.

---

## What I did not test

- Whether `ThreadingHTTPServer` correctly handles a client that connects
  and then never sends data (connection timeout, not read timeout).
- Whether the store's symlink-write defense is exercised through the HTTP
  layer (it is inherited from the store, but no HTTP-layer test plants a
  symlink and POSTs to it).
- Whether the server correctly handles HTTP/1.0 clients (no
  `Connection: keep-alive`).
- Whether the `--host 0.0.0.0` flag (if a user overrides the default)
  produces a warning.

---

## Overall assessment

The server is sound for its stated scope (local-only, trusted caller).
Two P2 findings should be fixed before any network exposure is
documented or enabled. The P3 findings are cosmetic or documentation
gaps. The acceptance criterion is met. The audit recommends fixing
AUD-RPC-01 and AUD-RPC-02 before V2-1 is considered fully closed.
