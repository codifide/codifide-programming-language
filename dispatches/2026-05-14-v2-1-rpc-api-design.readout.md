# RPC API — Design Dispatch (V2-1-1, V2-1-2)

**Date:** 2026-05-14  
**Persona:** Quill  
**Tasks:** V2-1-1 (write `docs/RPC_API.md`), V2-1-2 (design dispatch)

---

## What happened

The RPC API design is complete. `docs/RPC_API.md` is written and the four
open questions from the last session are resolved.

---

## The four decisions

**HTTP, not gRPC.** Every agent speaks HTTP. gRPC requires a protobuf schema
and a generated client. The canonical form is already JSON and CBOR — HTTP
maps directly onto it with no translation layer. This was the obvious call
once stated plainly.

**CLI extension, not separate service.** `python3 -m codifide serve` starts
a local HTTP server backed by the existing `SymbolStore`. The store already
handles atomic writes, integrity checks, and GC. A separate service would
require agents to manage a deployment dependency. A CLI extension starts with
one command.

**No auth in v2.0.** The server binds to `127.0.0.1` only. An agent running
`codifide serve` owns the process. API keys add friction with no security
benefit against a local attacker. Production guidance is documented; the
implementation doesn't pretend the problem doesn't exist.

**CBOR primary, JSON secondary.** Matches the store's existing wire format.
No new encoding logic needed.

---

## What the API looks like

Three endpoints:

- `POST /symbols` — publish a symbol, get its hash back
- `GET /symbols/{identity}` — retrieve a symbol by hash
- `GET /symbols/{identity}/imports` — resolve the import graph
- `GET /health` — liveness check

The Program 5 workflow via HTTP is documented in `docs/RPC_API.md` with a
working curl example. An agent can complete it without touching the CLI store
subcommands or `CODIFIDE_RUNTIME=python`.

---

## What's next

V2-1-3: implement `POST /symbols`. The implementation is `codifide/server.py`
using Python's built-in `http.server` — no new dependencies. Then V2-1-4
(`GET /symbols/{identity}`), V2-1-5 (`GET /symbols/{identity}/imports`), and
V2-1-6 (agent completes Program 5 via HTTP only).

---

## What I'm not yet sure of

Whether `http.server` handles concurrent POSTs correctly under the store's
atomic-write semantics, or whether we need `ThreadingHTTPServer`. The store
is safe for concurrent writes; the question is whether the server layer
serializes them unnecessarily. Tessa will catch this in the test pass.

