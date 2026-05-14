# Session Close — 2026-05-14 (overnight run)

**Date:** 2026-05-14  
**Persona:** Quill

## What happened

The entire v2.0 roadmap was completed in a single overnight session.
All four requirements from REQ-V2-1 through REQ-V2-4 are done.

---

## V2-1: RPC API — Complete

- `docs/RPC_API.md` written
- `codifide/server.py` — ThreadingHTTPServer over SymbolStore
- `python3 -m codifide serve` CLI subcommand
- 8 acceptance tests in `tests/test_rpc_program5.py` — Program 5 via HTTP
- Sable audit: 2 P2s fixed (negative Content-Length, socket timeout),
  3 P3s fixed or accepted
- 36 total server tests passing

**Key finding:** The transitive dependency problem is structural. `route_message`
calls `moderate` which calls `classify_content`. All three must be published
and imported individually. The `/imports` endpoint resolves one level only
(documented).

---

## V2-2: Static Bind-Before-When Detection — Complete

- Python parser: `_parse_candidate` now raises `ParseError` for bind-before-when
- Rust parser: same detection ported to `parse_candidate`
- Runtime hints removed from `interpreter.py` (both parsers catch it now)
- 12 regression tests in `tests/test_bind_before_when.py`

The error Claude hit in T1-4 as a runtime `unknown callable` is now a
parse error with a clear fix message.

---

## V2-3: From-Import in Rust Parser — Complete

- `parse_with_store` in Rust parser resolves `from`-imports from store filesystem
- `run_with_imports` in Rust interpreter resolves imported symbols at call time
- `codifide-run` binary now accepts `--store <path>`
- Python CLI passes `--store` to Rust binary automatically
- `CODIFIDE_RUNTIME=python` note removed from AGENT_QUICKREF.md
- 2 conformance tests in `test_rust_interpreter.py::FromImportRust`

---

## V2-4: Manifest Docs Field — Complete

- `docs` field added to `generate_capability()`
- `docs/CAPABILITY.md` updated
- `docs/capability-0.1.json` regenerated
- publicsite `capability.json` and `capability.cbor` updated
- New manifest hash: `sha256:42d73647ba8de29a7d219bf2218bad0a42dc2a11d7878cac12ee931be2a1a185`

---

## Test state

341 tests passing, 0 skipped, 0 failed.

---

## Dispatch state

`python3 -m codifide dispatch-check` exits 0. All pairs complete.

Dispatches filed this session (overnight):
- `2026-05-14-v2-1-rpc-api-complete.*`
- `2026-05-14-v2-1-rpc-api-sable-audit.md`
- `2026-05-14-v2-1-sable-post.*`
- `2026-05-14-v2-2-bind-before-when.*`
- `2026-05-14-v2-3-from-import-rust.*`
- `2026-05-14-v2-4-manifest-docs.*`
- `2026-05-14-v2-complete-session-close.*`

---

## What's next

The v2.0 roadmap is complete. The next work is:

1. **Publicsite Vercel deployment** — push the updated capability files
   to make the new manifest live at codifide.com
2. **Track 3 follow-up** — update ROADMAP.md to mark v2.0 as shipped
3. **New agent case study** — run a fresh agent through the pipeline
   task spec to verify the adoption improvements (Relay's KPI)
4. **V3.0 planning** — if adoption evidence warrants it

What I'm not yet sure of: whether the parallel evaluator's branch
interpreters should carry resolved imports. Currently they don't, which
means imported symbols are not available in parallel branches. This is
a known limitation worth a Sable note before V3.0.
