# Codifide RPC API

**Version:** 0.1  
**Status:** Implemented — v2.0  
**Author:** Douglas Jones + Claude (Winston, Lumen)  
**Evidence:** REQ-V2-1, `dispatches/2026-05-13-track1-summary.*`

---

## Why this exists

Program 5 of the agent task spec (content-addressed composition) was the
universal failure point across all three Track 1 agent sessions. Every agent
had to manually run `store put`, `store hash`, `store index`, set
`CODIFIDE_RUNTIME=python`, and write `from`-import syntax. The friction is
not in the language semantics — it is in the composition layer.

The RPC API removes the CLI layer entirely for agent-to-agent composition.
An agent publishes a symbol by POSTing its canonical form and receives a
hash. Another agent resolves an import by GETting that hash. No CLI. No
runtime flag. No index ceremony.

---

## Design decisions

### HTTP, not gRPC

Every agent can speak HTTP. gRPC requires a protobuf schema and a generated
client. The canonical form is already JSON and CBOR — HTTP maps directly onto
it with no translation layer.

### CLI extension, not separate service

`python3 -m codifide serve` starts a local HTTP server backed by the existing
`SymbolStore`. The store already handles atomic writes, integrity checks, and
GC. The server is a thin HTTP wrapper — it adds no new storage logic.

A separate service would require agents to manage a deployment dependency.
A CLI extension starts with one command and stops when the process exits.

### No auth in v2.0

The store is local. An agent running `codifide serve` owns the process. API
keys add friction with no security benefit against a local attacker. Production
deployments that expose the server over a network should add a reverse proxy
with auth. This is documented in the Security section below.

### CBOR primary, JSON secondary

Matches the store's existing wire format. POST bodies and GET responses use
`Content-Type: application/cbor` (primary) or `application/json` (secondary).
Clients signal preference via `Content-Type` on POST and `Accept` on GET.

---

## Server

### Start

```bash
python3 -m codifide serve [--port 7777] [--store ~/.codifide/store]
```

Defaults: port `7777`, store root `~/.codifide/store` (same default as the
CLI). The server binds to `127.0.0.1` only — never `0.0.0.0` by default.

### Stop

`Ctrl-C` or `SIGTERM`. The server does not daemonize.

---

## Endpoints

### POST /symbols

Publish a symbol. Accepts canonical CBOR (primary) or canonical JSON
(secondary). Returns the symbol's SHA-256 content identity.

**Request**

```
POST /symbols
Content-Type: application/cbor   (or application/json)

<canonical CBOR or JSON bytes of a single-symbol module>
```

The body must be a valid canonical module object with exactly one entry in
`symbols`. Multi-symbol modules are rejected — publish symbols individually.

**Response 200**

```json
{
  "identity": "sha256:<64 hex chars>",
  "name": "<symbol name>"
}
```

**Response 400** — body is not valid canonical form, or contains zero or
multiple symbols.

```json
{
  "error": "invalid_body",
  "detail": "<human-readable reason>"
}
```

**Response 409** — symbol already exists. The store's idempotent-write
property means a 409 never occurs in practice; a second POST of the same
symbol returns 200 with the existing identity. This entry is omitted from
the error table below for that reason.

**Example (curl)**

```bash
python3 -m codifide canonical --cbor classify.cod | \
  curl -s -X POST http://localhost:7777/symbols \
    -H 'Content-Type: application/cbor' \
    --data-binary @- | jq .identity
```

---

### GET /symbols/{identity}

Retrieve a symbol by its SHA-256 content identity.

**Request**

```
GET /symbols/sha256:<64 hex chars>
Accept: application/cbor   (or application/json)
```

`Accept` defaults to `application/cbor` if omitted.

**Response 200**

Body is the canonical CBOR (or JSON) bytes of the stored symbol. The
`Content-Type` header matches the wire form returned.

**Response 404** — no symbol with that identity in the store.

```json
{
  "error": "not_found",
  "identity": "sha256:<64 hex chars>"
}
```

**Response 400** — identity is malformed (not `sha256:` + 64 hex chars).

**Example (curl)**

```bash
curl -s http://localhost:7777/symbols/sha256:<hash> \
  -H 'Accept: application/json' | jq .
```

---

### GET /symbols/{identity}/imports

Resolve the **direct** imports of a stored module. Returns the entries in
the module's imports table and whether each is present in the store.

**Note: one level only.** This endpoint does not walk the transitive closure.
To resolve the full dependency graph, call this endpoint recursively on each
returned identity. The field is named `imports` (not `direct_imports`) for
brevity, but the scope is always one level.

**Request**

```
GET /symbols/sha256:<64 hex chars>/imports
```

**Response 200**

```json
{
  "identity": "sha256:<64 hex chars>",
  "imports": [
    {
      "name": "<local name>",
      "identity": "sha256:<64 hex chars>",
      "present": true
    },
    ...
  ],
  "missing": ["sha256:<64 hex chars>", ...]
}
```

`missing` is empty when all imports are present. Non-empty `missing` means
the import graph is incomplete — the agent must publish the missing symbols
before the module can be executed.

**Response 404** — the root identity is not in the store.

---

### GET /health

Liveness check. Returns 200 with `{"status": "ok"}`. No store access.

---

## Agent workflow — Program 5 via HTTP

This replaces the CLI-based Program 5 workflow entirely.

**Important:** The dependency chain for the content-moderation pipeline is:
`route_message` → `moderate` → `classify_content`. All three symbols must
be published and imported individually — the store holds single-symbol units
and does not carry transitive dependencies automatically.

```bash
# 1. Start the server (once per session)
python3 -m codifide serve &

# 2. Publish all three symbols in the dependency chain
CLASSIFY_HASH=$(python3 -m codifide canonical --cbor content_classifier.cod | \
  curl -s -X POST http://localhost:7777/symbols \
    -H 'Content-Type: application/cbor' --data-binary @- | \
  jq -r .identity)

MODERATE_HASH=$(python3 -m codifide canonical --cbor escalation_router.cod | \
  curl -s -X POST http://localhost:7777/symbols \
    -H 'Content-Type: application/cbor' --data-binary @- | \
  jq -r .identity)   # publishes moderate (and classify_content again — idempotent)

ROUTE_HASH=$(python3 -m codifide canonical --cbor escalation_router.cod | \
  curl -s -X POST http://localhost:7777/symbols \
    -H 'Content-Type: application/cbor' --data-binary @- | \
  jq -r .identity)   # publishes route_message

# 3. Write pipeline_composed.cod importing all three by hash
cat > pipeline_composed.cod << EOF
module pipeline_composed

import classify_content = $CLASSIFY_HASH
import moderate         = $MODERATE_HASH
import route_message    = $ROUTE_HASH

def composed_pipeline
  intent "run the full moderation pipeline using content-addressed imports"
  sig    (message: String) -> Decision
  effects {}
  cand
    route_message(message)

def main
  intent "test the composed pipeline"
  sig    () -> Decision
  effects {}
  cand
    composed_pipeline("this message contains spam")
EOF

# 4. Run it — no CODIFIDE_RUNTIME=python needed
python3 -m codifide run pipeline_composed.cod
```

Note: `jq` is required for the hash extraction step. If unavailable, use
`python3 -c "import sys,json; print(json.load(sys.stdin)['identity'])"` instead.

---

## Error responses

All error responses are JSON regardless of the `Accept` header.

| HTTP status | `error` field | Meaning |
|-------------|---------------|---------|
| 400 | `invalid_body` | Body is not valid canonical form |
| 400 | `invalid_identity` | Identity is malformed |
| 400 | `multi_symbol` | POST body contains more than one symbol |
| 404 | `not_found` | Identity not in store |
| 405 | `method_not_allowed` | Wrong HTTP method for this endpoint |
| 413 | `body_too_large` | Body exceeds 16 MiB (same limit as CLI) |
| 500 | `store_error` | Internal store error (integrity failure, etc.) |

---

## Security

### v2.0 scope (local only)

The server binds to `127.0.0.1` by default. It is not safe to expose over a
network without additional controls. v2.0 ships no auth.

### Production guidance (out of scope for v2.0)

For deployments that expose the server over a network:
- Place behind a reverse proxy (nginx, Caddy) with TLS and API key auth
- Rate-limit POST `/symbols` to prevent store exhaustion
- Set `--store` to a path with appropriate filesystem permissions

### Threat model notes

- **Store exhaustion:** An unauthenticated local caller can fill the store
  disk. Mitigated by the 16 MiB body limit per request. GC is the long-term
  answer.
- **Path traversal:** The store's existing symlink-write defense applies
  unchanged. The HTTP layer adds no new file I/O paths.
- **Integrity:** The store's hash-verified read/write applies unchanged. The
  HTTP layer cannot return bytes that don't match the requested identity.

---

## Implementation notes

The server is implemented in `codifide/server.py` using Python's built-in
`http.server` module (no new dependencies). The `SymbolStore` instance is
shared across all requests; the store's atomic-write semantics handle
concurrent POSTs correctly.

The `serve` CLI subcommand is added to `codifide/__main__.py`.

---

## Remote symbol resolution (V3-2)

The RPC API is the foundation for cross-machine symbol exchange. V3-2 adds
three capabilities on top of the local server:

### Public registry

A public read-only registry at `https://codifide.com/symbols/<identity>`
serves canonical CBOR for any published symbol. The same endpoint shape as
the local server — any agent that knows the base URL can resolve identities
against any server.

Start a read-only server (for registry deployments):

```bash
python3 -m codifide serve --read-only [--host 0.0.0.0] [--port 7777]
```

`--read-only` disables `POST /symbols` (returns 405). `GET /symbols/<identity>`,
`GET /symbols/<identity>/imports`, and `GET /health` remain active.

### Push a symbol to a registry

```bash
python3 -m codifide store push <identity> [--registry https://codifide.com]
```

Reads the symbol from the local store, POSTs it to the registry's
`POST /symbols` endpoint, and verifies the returned identity matches.
Idempotent. The registry URL defaults to `https://codifide.com`.

```bash
# Store locally first, then push
python3 -m codifide store put classify.cod
python3 -m codifide store push sha256:<hash>
```

### Resolve imports from a registry

```bash
python3 -m codifide run consumer.cod --registry https://codifide.com
```

The `--registry` flag enables remote resolution. When an import identity
is not in the local store, it is fetched from the registry, hash-verified,
cached locally, and used. Without `--registry`, only the local store is
used (existing behavior unchanged).

**Trust model:** hash-verification is the only trust mechanism. A fetch
that returns bytes not matching the requested identity is rejected with
`IntegrityError` before the bytes are cached. The registry cannot forge
a symbol without changing its identity.

### Cross-machine workflow

```bash
# Machine A — publish and push
python3 -m codifide store put classify.cod
python3 -m codifide store push sha256:<hash>

# Machine B — resolve from registry (no shared filesystem)
python3 -m codifide run consumer.cod --registry https://codifide.com
```

---

*Implemented v0.1 — May 2026*  
*V3-2 remote resolution — May 2026*  
*Governed by: GOVERNANCE.md*
