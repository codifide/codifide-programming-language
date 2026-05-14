# Codifide v2.0 Language Work — Tasks

## REQ-V2-1: RPC API (P1)

- [x] **V2-1-1** Write `docs/RPC_API.md` — spec for the HTTP/gRPC interface
- [x] **V2-1-2** Design dispatch: endpoint shape, auth model, error responses
- [x] **V2-1-3** Implement POST `/symbols` — accept canonical CBOR, store, return hash
- [x] **V2-1-4** Implement GET `/symbols/<hash>` — return canonical CBOR by hash
- [x] **V2-1-5** Implement GET `/symbols/<hash>/imports` — resolve import graph
- [x] **V2-1-6** Test: agent completes Program 5 via HTTP only
- [x] **V2-1-7** File Quill/Glyph dispatch for RPC API completion
- [x] **V2-1-8** Sable audit of RPC API surface

## REQ-V2-2: Static bind-before-when detection (P2)

- [x] **V2-2-1** Add scope tracking to the Python parser
- [x] **V2-2-2** Raise `ParseError` for bind-before-when with clear message
- [x] **V2-2-3** Add regression tests
- [x] **V2-2-4** Remove runtime hint only after BOTH Python (V2-2-2) and Rust (V2-2-5) parsers catch bind-before-when statically
- [x] **V2-2-5** Port to Rust parser
- [ ] **V2-2-6** File Quill/Glyph dispatch

## REQ-V2-3: `from`-import in Rust parser (P3)

- [x] **V2-3-1** Implement `from <hash> import name` in Rust lexer + parser
- [x] **V2-3-2** Implement store resolution in Rust interpreter
- [x] **V2-3-3** Conformance tests: byte-identical output with Python runtime
- [x] **V2-3-4** Remove `CODIFIDE_RUNTIME=python` note from AGENT_QUICKREF
- [x] **V2-3-5** File Quill/Glyph dispatch

## REQ-V2-4: Manifest `docs` field (P3)

- [x] **V2-4-1** Add `docs` field to `generate_capability()` in `capability.py`
- [x] **V2-4-2** Update `docs/CAPABILITY.md` schema documentation
- [x] **V2-4-3** Regenerate `docs/capability-0.1.json`
- [x] **V2-4-4** Update manifest endpoint on publicsite
- [x] **V2-4-5** File Quill/Glyph dispatch

## Session Close

- [ ] **SC-1** `python3 -m codifide dispatch-check` exits 0
- [ ] **SC-2** All open Quill readouts have paired Glyph YAMLs
- [ ] **SC-3** session-close.readout.md and session-close.yaml filed
