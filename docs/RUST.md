# Rust crate — canonical form

The `crates/noema-canonical/` crate is a second, independent implementation
of Noema's canonical form. It does not include an interpreter. Its purpose
is conformance, not replacement.

## Why a second implementation at all

A language is its specification, not any particular implementation. Until
two implementations can agree on a conforming document byte-for-byte, the
specification is effectively whatever the single implementation happens to
do. Writing a second implementation is the forcing function that moves the
specification out of code and into `docs/CANONICAL.md`.

## Why canonical form and not the interpreter

Semantics are still changing. The transitive effect-subset check is not
yet implemented, and shipping it will alter runtime behavior for any
program whose callees exceed their caller's declared effects. Porting an
interpreter whose semantics are in motion doubles the cost of every
semantics change. The canonical form is the stablest piece of Noema right
now, and it is also the piece whose agreement matters most because it is
what gets hashed and shipped between agents.

## What the Rust crate implements

- The AST, mirroring the Python dataclasses in `noema/core/types.py`.
- JSON projection: `to_canonical_json` / `from_canonical_json`.
- Canonical byte form: deterministic serialization following
  `docs/CANONICAL.md §Canonical serialization`.
- Content addressing: `sha256:<hex>` over canonical byte form.
- A tiny CLI (`noema-canonical bytes|hash`) that consumes canonical JSON
  and emits canonical bytes or the content hash.

The Rust crate does not parse `.nm` surface syntax. The Python reference is
authoritative for parsing in v0.

## Conformance surface

`tests/test_conformance.py` is the only place the two implementations meet.
It parses every `examples/*.nm` with Python, emits canonical JSON, hands it
to the Rust binary, and asserts byte-level equality with the Python
canonical bytes. The same file asserts content-hash equality. When the
crate is missing or `cargo` is not available, the suite skips those tests
with a clear reason.

If the two implementations ever disagree, the specification is the
adjudicator. One of the two implementations is a bug against the spec —
never the other way around. If both implementations agree but the spec is
silent, the spec is the bug.

## Build

```bash
cargo build --release
cargo test --release
```

The conformance tests invoke `cargo build --release -p noema-canonical`
automatically if the binary is missing, so `python3 -m noema test` is
still the single entry point.
