# V3-2 — Remote Symbol Resolution

**Date:** 2026-05-14  
**Persona:** Quill  
**Requirement:** V3-2 from the v3.0 roadmap  
**Design dispatch:** `2026-05-14-v3-2-remote-symbols-design.readout.md`

---

## What shipped

Four pieces, in implementation order:

### 1. `--read-only` flag on `codifide serve`

`python3 -m codifide serve --read-only` disables `POST /symbols` (returns 405).
`GET /symbols/<identity>`, `GET /symbols/<identity>/imports`, and `GET /health`
remain active. Used for public registry deployments where writes are not accepted.

Changes: `codifide/server.py` — `_Handler.read_only` class attribute,
`do_POST` check, `make_server` and `serve` signatures updated.
`codifide/__main__.py` — `--read-only` flag on `p_serve`, `cmd_serve` updated.

### 2. `RemoteStore` class

`codifide/store/remote.py` — new class. Wraps a local `SymbolStore` and falls
back to a remote registry on cache miss. Exposes the same `get`, `has`,
`get_bytes`, `put`, `put_module` interface as `SymbolStore`.

Trust model: hash-verification before caching. A fetch that returns bytes not
matching the requested identity raises `IntegrityError` before the bytes are
stored. The registry cannot forge a symbol without changing its identity.

`codifide/store/__init__.py` — `RemoteStore` and `DEFAULT_REGISTRY` exported.

### 3. `codifide store push <identity> [--registry <url>]`

New CLI subcommand. Reads symbol bytes from the local store, POSTs to the
registry's `POST /symbols` endpoint, verifies the returned identity matches.
Idempotent. Registry URL defaults to `https://codifide.com`.

Changes: `codifide/__main__.py` — `cmd_store_push` function, `p_push` parser.

### 4. `--registry` flag on `codifide run`

`python3 -m codifide run consumer.cod --registry https://codifide.com` enables
remote resolution. When an import identity is not in the local store, it is
fetched from the registry, hash-verified, cached locally, and used. Without
`--registry`, behavior is identical to today (local store only, opt-in).

Changes: `codifide/__main__.py` — `--registry` flag on `p_run`,
`_cmd_run_python` wraps local store in `RemoteStore` when `--registry` is set.

### 5. `docs/RPC_API.md` update

New "Remote symbol resolution (V3-2)" section covering `--read-only`,
`store push`, and `--registry` with the cross-machine workflow example.

---

## Tests

`tests/test_remote_store.py` — 16 new tests across 4 classes:

- `RemoteStoreFetchTests` (7) — fetch-and-cache, local cache hit, get_bytes,
  NotFound, has() against registry, has() for missing, hash-verification logic
- `ReadOnlyServerTests` (3) — POST returns 405, GET still works, health still works
- `StorePushTests` (4) — push publishes, idempotent, missing local fails, invalid identity fails
- `RunRegistryTests` (2) — run resolves import from registry, run without registry fails

### Test count

359 passing, 0 skipped (was 343).

---

## Acceptance criterion: met

```bash
# Machine A
python3 -m codifide store put classify.cod
python3 -m codifide store push sha256:<hash>

# Machine B (no shared filesystem)
python3 -m codifide run consumer.cod --registry https://codifide.com
# → resolves sha256:<hash> from registry, caches locally, runs correctly
```

The `test_run_resolves_import_from_registry` test exercises exactly this
pattern against a local server acting as the registry.

---

## What was not changed

- The Rust runtime — Python CLI handles remote resolution via `--store`
- Auth on the server — reverse proxy concern, out of scope
- The `codifide.com` deployment — infrastructure, not code
- Transitive closure resolution — agents walk `/imports` themselves

---

## Open question resolved

The design dispatch asked whether `RemoteStore` should be the default.
Answer confirmed: no. `--registry` is opt-in. Without it, `codifide run`
is identical to today. Silent network calls on `codifide run` would surprise
agents that expect local-only behavior.

