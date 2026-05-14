# Session State — 2026-05-14 (overnight run)

## What was completed

The entire v2.0 roadmap was completed in a single overnight autonomous session.

---

## REQ-V2-1: RPC API — Complete

**New files:**
- `codifide/server.py` — ThreadingHTTPServer over SymbolStore
- `tests/test_server.py` — 29 tests (28 original + 1 Sable fix)
- `tests/test_rpc_program5.py` — 8 acceptance tests
- `docs/RPC_API.md` — endpoint spec, design decisions, security notes

**CLI:** `python3 -m codifide serve [--port 7777] [--store <path>]`

**Endpoints:**
- `POST /symbols` — publish a symbol, get its hash
- `GET /symbols/<id>` — retrieve by hash (CBOR or JSON)
- `GET /symbols/<id>/imports` — resolve direct imports
- `GET /health` — liveness check
- `HEAD /symbols/<id>` — existence check

**Sable audit findings applied:**
- AUD-RPC-01: negative Content-Length now returns None
- AUD-RPC-02: 30-second socket timeout added
- AUD-RPC-03/05: unused imports removed
- AUD-RPC-04: `/imports` documented as direct-only

**Key finding:** Transitive dependency problem is structural. All symbols
in the dependency chain must be published and imported individually.

---

## REQ-V2-2: Static Bind-Before-When Detection — Complete

**Changed files:**
- `codifide/parser/parser.py` — `_parse_candidate` raises ParseError
- `crates/codifide-interpreter/src/parser/mod.rs` — same detection
- `codifide/runtime/interpreter.py` — runtime hints removed
- `tests/test_bind_before_when.py` — 12 regression tests

**Error message:**
```
ParseError: bind-before-when: the `when` guard on line N executes before
the candidate body, but 'label' (line M) is bound in the body with `<-`
and will not exist yet. Fix: move the bind into the body and use
`if/then/else` to route on the result instead of a `when` guard.
```

---

## REQ-V2-3: From-Import in Rust Parser — Complete

**Changed files:**
- `crates/codifide-interpreter/src/parser/mod.rs` — `parse_with_store`
- `crates/codifide-interpreter/src/interpreter.rs` — `run_with_imports`,
  `resolved_imports` field, `invoke_defn_owned`
- `crates/codifide-interpreter/src/bin/codifide_run.rs` — `--store` flag,
  `resolve_imports_from_store`
- `crates/codifide-interpreter/src/lib.rs` — exports `parse_with_store`,
  `run_with_imports`
- `codifide/__main__.py` — passes `--store` to Rust binary
- `docs/AGENT_QUICKREF.md` — CODIFIDE_RUNTIME=python note updated
- `tests/test_rust_interpreter.py` — `FromImportRust` class (2 tests)

**Known limitation:** Parallel evaluator branch interpreters don't carry
resolved imports. Imported symbols not available in parallel branches.

---

## REQ-V2-4: Manifest Docs Field — Complete

**Changed files:**
- `codifide/capability.py` — `_docs()` function, `docs` field in manifest
- `docs/CAPABILITY.md` — docs field schema documented
- `docs/capability-0.1.json` — regenerated
- `publicsite/capability.json` — updated
- `publicsite/capability.cbor` — updated
- `tests/test_capability.py` — `test_docs_field_has_required_keys`

**New manifest hash:**
`sha256:42d73647ba8de29a7d219bf2218bad0a42dc2a11d7878cac12ee931be2a1a185`

**Docs field:**
```json
{
  "for_agents":      "https://codifide.com/docs/FOR_AGENTS.md",
  "quickref":        "https://codifide.com/docs/AGENT_QUICKREF.md",
  "cookbook":        "https://codifide.com/docs/AGENT_COOKBOOK.md",
  "capability":      "https://codifide.com/capability.json",
  "capability_cbor": "https://codifide.com/capability.cbor"
}
```

---

## Test state

341 tests passing, 0 skipped, 0 failed.

---

## Dispatch state

`python3 -m codifide dispatch-check` exits 0. All pairs complete.

---

## Next session

1. **Publicsite Vercel deployment** — push publicsite repo, trigger deploy
2. **ROADMAP.md** — already updated to mark v2.0 as shipped
3. **New agent case study** — run a fresh agent through the pipeline task
   spec to validate adoption improvements (Relay's KPI)
4. **Sable audit** — parallel evaluator import handling (known gap)

---

## Key files changed this session

| File | Change |
|------|--------|
| `codifide/server.py` | New — RPC API server |
| `codifide/capability.py` | docs field added |
| `codifide/parser/parser.py` | bind-before-when detection |
| `codifide/runtime/interpreter.py` | runtime hints removed |
| `codifide/__main__.py` | serve subcommand, --store to Rust |
| `crates/codifide-interpreter/src/parser/mod.rs` | parse_with_store, bind-before-when |
| `crates/codifide-interpreter/src/interpreter.rs` | run_with_imports, resolved_imports |
| `crates/codifide-interpreter/src/bin/codifide_run.rs` | --store flag |
| `docs/RPC_API.md` | New — RPC API spec |
| `docs/CAPABILITY.md` | docs field schema |
| `docs/capability-0.1.json` | Regenerated |
| `docs/AGENT_QUICKREF.md` | CODIFIDE_RUNTIME note updated |
| `docs/ROADMAP.md` | v2.0 marked shipped |
| `publicsite/capability.json` | Updated |
| `publicsite/capability.cbor` | Updated |
| `tests/test_server.py` | 29 server tests |
| `tests/test_rpc_program5.py` | 8 acceptance tests |
| `tests/test_bind_before_when.py` | 12 regression tests |
| `tests/test_capability.py` | docs field test |
| `tests/test_rust_interpreter.py` | FromImportRust class |
