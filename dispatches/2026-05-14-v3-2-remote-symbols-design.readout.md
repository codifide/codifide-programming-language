# V3-2 Design — Remote Symbol Resolution

**Date:** 2026-05-14  
**Persona:** Quill  
**Requirement:** V3-2 from the v3.0 roadmap  
**Status:** Design dispatch — not yet implemented

---

## What V3-2 is

An agent on machine B resolves a symbol published by agent on machine A
using only the content identity (`sha256:<hex>`). No out-of-band coordination.
No shared filesystem. The hash-verification path (already in the store) makes
trust automatic: a server cannot return bytes that don't match the requested
identity without the client detecting it.

---

## What already exists

The RPC API (V2-1) proved the local HTTP pattern:

- `POST /symbols` — publish a symbol, get its hash
- `GET /symbols/<identity>` — retrieve a symbol by hash
- `GET /symbols/<identity>/imports` — resolve one level of imports
- `GET /health` — liveness check

The server binds to `127.0.0.1` only. The store's hash-verified read/write
is already in place. The Rust runtime already accepts `--store <path>` and
resolves imports from the filesystem.

V3-2 extends this in three directions:

1. A **public registry** at `codifide.com/symbols/<identity>` — read-only,
   no auth, serves canonical CBOR for any published symbol.
2. A **push command** (`codifide store push`) — publishes a local symbol to
   the public registry via HTTP.
3. A **remote store** in the Python runtime — when a local store misses an
   identity, it fetches from the public registry and caches locally.

---

## Design

### 1. Public registry

The public registry is the existing RPC server, deployed at
`codifide.com` with two changes:

- **Bind to `0.0.0.0`** (or the deployment's public interface) instead of
  `127.0.0.1`. The `--host` flag already exists in the `serve` command;
  the deployment just passes `--host 0.0.0.0`.
- **Read-only mode** — the public registry accepts `GET` only. `POST /symbols`
  is disabled (returns 405). Agents publish to their local server; the push
  command (below) handles the transfer.

No new server code is needed. The existing server gains a `--read-only` flag
that disables `POST /symbols` and `do_POST`.

**URL scheme:** `https://codifide.com/symbols/<identity>`

This is the same path as the local server. An agent that knows the base URL
can resolve any identity against any server — local or remote — with the same
code path.

---

### 2. Push command

```bash
python3 -m codifide store push <identity> [--registry https://codifide.com]
```

Reads the symbol from the local store, POSTs it to the registry's
`POST /symbols` endpoint, verifies the returned identity matches. Idempotent:
a second push of the same symbol returns 200 with the existing identity.

The registry URL defaults to `https://codifide.com`. Agents running private
registries pass `--registry https://my-registry.example.com`.

**Implementation:** a new `push` subcommand in `codifide/__main__.py` that:
1. Reads the symbol bytes from the local store (`store.get_bytes(identity)`)
2. POSTs to `<registry>/symbols` with `Content-Type: application/cbor`
3. Asserts the returned `identity` matches the local identity
4. Prints the identity on success

No new dependencies — `urllib.request` is sufficient for a single POST.

---

### 3. Remote store (fetch-and-cache)

The Python runtime's `_ResolvedImports.from_module` currently requires a
local `SymbolStore`. V3-2 adds a `RemoteStore` wrapper that:

1. Checks the local store first (cache hit — no network)
2. On miss, fetches from the registry via `GET /symbols/<identity>`
3. Verifies the returned bytes hash to the requested identity
4. Writes to the local store (cache the result)
5. Returns the parsed object

```python
class RemoteStore:
    """A SymbolStore that falls back to a remote registry on cache miss."""

    def __init__(self, local: SymbolStore, registry: str = "https://codifide.com"):
        self.local = local
        self.registry = registry.rstrip("/")

    def get(self, identity: str) -> dict:
        try:
            return self.local.get(identity)
        except NotFound:
            pass
        # Fetch from registry.
        url = f"{self.registry}/symbols/{identity}"
        data = self._fetch(url, identity)
        # Cache locally.
        self.local._write_atomic(identity, data, suffix=".cbor")
        return self.local.get(identity)

    def has(self, identity: str) -> bool:
        if self.local.has(identity):
            return True
        # HEAD check against registry.
        ...

    def _fetch(self, url: str, identity: str) -> bytes:
        import urllib.request
        req = urllib.request.Request(url, headers={"Accept": "application/cbor"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise StoreError(f"remote symbol exceeds 16 MiB: {identity}")
        # Hash-verify before caching.
        import hashlib
        observed = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if observed != identity:
            raise IntegrityError(expected=identity, actual=observed)
        return data
```

The `run()` entry point gains a `registry` parameter. When set, it wraps the
local store in a `RemoteStore` before resolving imports.

The Rust runtime does not need to change for V3-2. The Python CLI resolves
imports (fetching from the registry if needed) and passes the resolved
`Definition` objects to the Rust binary via the existing `--store` path.

---

### 4. CLI integration

```bash
# Publish to local server (existing)
python3 -m codifide store put classify.cod

# Push to public registry (new)
python3 -m codifide store push sha256:<hash>

# Run with remote resolution (new --registry flag)
python3 -m codifide run pipeline_composed.cod --registry https://codifide.com
```

The `--registry` flag on `run` enables remote resolution. Without it,
behavior is identical to today (local store only).

---

## Trust model

**Hash-verification is the trust mechanism.** An agent that fetches
`https://codifide.com/symbols/sha256:<hash>` and receives bytes that don't
hash to `sha256:<hash>` rejects them with `IntegrityError`. The registry
cannot lie about a symbol's content without changing its identity. No PKI,
no signatures, no trust anchors beyond the hash itself.

This is the same property the local store already provides. V3-2 extends it
over the network.

**What the registry can do:** return 404 (symbol not found), return 503
(unavailable), or return bytes that fail the hash check (rejected by the
client). It cannot return a different symbol under the same identity.

**What the registry cannot do:** forge a symbol. The hash is the identity.

---

## Scope boundaries

**In scope for V3-2:**
- `--read-only` flag on `codifide serve`
- `codifide store push <identity> [--registry <url>]`
- `RemoteStore` class in `codifide/store/`
- `--registry` flag on `codifide run`
- Tests for push, remote fetch, hash-verification rejection
- `docs/RPC_API.md` update with remote resolution section

**Out of scope for V3-2:**
- The actual `codifide.com` deployment (infrastructure, not code)
- Auth on the public registry (reverse proxy concern)
- Rate limiting (reverse proxy concern)
- Rust runtime remote resolution (Python CLI handles it via `--store`)
- Transitive closure resolution (the `/imports` endpoint already exists;
  agents walk it themselves)

---

## Acceptance criterion (from roadmap)

Agent on machine B resolves a symbol published by agent on machine A using
only the content identity. Concretely:

```bash
# Machine A
python3 -m codifide store put classify.cod
python3 -m codifide store push sha256:<hash>

# Machine B (no shared filesystem)
python3 -m codifide run consumer.cod --registry https://codifide.com
# → resolves sha256:<hash> from registry, caches locally, runs correctly
```

---

## Implementation order

1. `--read-only` flag on `serve` (trivial — one flag, one `if` in `do_POST`)
2. `RemoteStore` class + tests
3. `codifide store push` command + tests
4. `--registry` flag on `run` + integration test
5. `docs/RPC_API.md` update

Estimated scope: one session. The `RemoteStore` is the only non-trivial
piece; the rest is plumbing.

---

## Open questions

**Q1: Should `RemoteStore` be the default when a registry is reachable?**

No. Opt-in via `--registry` is the right default. Silent network calls
on `codifide run` would surprise agents that expect local-only behavior.
The flag makes the network dependency explicit.

**Q2: Should the push command require the symbol to be in the local store?**

Yes. `codifide store push <identity>` reads from the local store. An agent
that wants to push a symbol it hasn't stored locally must `store put` first.
This keeps the push command simple and the local store as the single source
of truth.

**Q3: Should the registry accept writes (POST /symbols) from the public?**

No for the initial deployment. The public registry is read-only. Agents
push via their local server + `store push`. This avoids store exhaustion
and spam without requiring auth. If a write-enabled public registry is
needed later, it's a separate design decision.

**Q4: What happens when the registry is unreachable?**

`RemoteStore._fetch` raises `StoreError` with a clear message. The `run`
command surfaces it as a runtime error. No silent fallback to a different
symbol — fail loudly.

