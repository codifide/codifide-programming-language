# Codifide v4.0 — Tasks

## REQ-V4-1: Runtime type enforcement

- [x] **V4-1-1** Add `TypeViolation` to `codifide/runtime/errors.py`
- [x] **V4-1-2** Implement `_check_type(value, declared_type)` in interpreter
- [x] **V4-1-3** Call type check at every user-function call boundary (args + return)
- [x] **V4-1-4** Add `TypeViolation` to capability manifest errors list
- [x] **V4-1-5** Write `tests/test_type_enforcement.py` (20 tests)
- [x] **V4-1-6** Verify all existing tests still pass (450 passing)
- [x] **V4-1-7** Sable audit of type enforcement implementation- [x] **V4-1-8** File Quill/Glyph dispatch

## REQ-V4-2: Standard library

### V4-2a: File I/O
- [x] **V4-2a-1** Add `io.read`, `io.write`, `io.exists` to `primitives.py`
- [x] **V4-2a-2** Add `io.read` and `io.write` effects to capability manifest
- [x] **V4-2a-3** Path traversal defense tests
- [x] **V4-2a-4** Size bound test

### V4-2b: HTTP client
- [x] **V4-2b-1** Add `http.get`, `http.post` to `primitives.py`
- [x] **V4-2b-2** Add `http.fetch` effect to capability manifest
- [x] **V4-2b-3** HTTPS-only enforcement test
- [x] **V4-2b-4** Timeout and size bound tests

### V4-2c: JSON primitives
- [x] **V4-2c-1** Add `json.parse`, `json.encode` to `primitives.py`
- [x] **V4-2c-2** Add to capability manifest (pure — no effect)
- [x] **V4-2c-3** Round-trip tests

### V4-2d: Date arithmetic
- [x] **V4-2d-1** Add `clock.today`, `clock.parse`, `clock.add_days`, `clock.format` to `primitives.py`
- [x] **V4-2d-2** Add to capability manifest
- [x] **V4-2d-3** Tests

### V4-2 shared
- [x] **V4-2-10** Write `tests/test_stdlib.py` (44 tests)
- [x] **V4-2-11** Update `docs/AGENT_QUICKREF.md` with new primitive groups
- [x] **V4-2-12** Add cookbook entries for stdlib patterns
- [x] **V4-2-13** Sable audit of stdlib (path traversal, HTTPS enforcement, JSON injection)
- [x] **V4-2-14** File Quill/Glyph dispatch

## REQ-V4-3: Public registry

- [x] **V4-3-1** Write `docs/REGISTRY.md`
- [ ] **V4-3-2** Publish the five canonical pipeline symbols to codifide.com (blob write API pending)
- [x] **V4-3-3** Add `registry` field to capability manifest — deferred (no field defined yet)
- [x] **V4-3-4** Add cookbook entry for publish-and-resolve workflow
- [ ] **V4-3-5** Verify `run --registry https://codifide.com` resolves pipeline symbols
- [x] **V4-3-6** File Quill/Glyph dispatch
- [x] **V4-3-7** Registry browser at codifide.com/registry

## REQ-V4-4: Network-safe server — DEFERRED

All tasks deferred. No adoption evidence for network-exposed server.

## Session Close

- [x] **SC-1** `python3 -m codifide dispatch-check` exits 0
- [x] **SC-2** All open Quill readouts have paired Glyph YAMLs
- [x] **SC-3** session-close.readout.md and session-close.yaml filed
- [x] **SC-4** CHANGELOG.md updated
- [x] **SC-5** ROADMAP.md updated
- [x] **SC-6** publicsite updated (capability.json, capability.cbor, index.html)

## Open items (post-v4.0)

- [ ] Sable audit of type enforcement (V4-1-7) — DONE
- [ ] Sable audit of stdlib (V4-2-13) — DONE (3 fixes applied: HTTPS redirect, io.write size limit, JSON recursion)
- [ ] Cookbook entries for stdlib patterns (V4-2-12) — DONE
- [ ] Cookbook entry for publish-and-resolve workflow (V4-3-4) — DONE
- [ ] Fix blob store write API — query params not headers (in progress)
- [ ] Seed registry with pipeline symbols (blocked on blob write fix)
- [ ] Verify end-to-end registry resolution (blocked on seeding)
- [ ] Publish to PyPI
- [ ] Run unstructured agent session for organic adoption signal
