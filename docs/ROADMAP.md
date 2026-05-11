# Codifide — Roadmap

## v0 (this commit)
- Canonical JSON schema
- Core types
- ASCII+unicode surface parser
- Tree-walking interpreter
- Effect enforcement
- Pre/post contract checking
- Belief dispatch
- Multi-candidate dispatch by guard
- Three examples + tests

## v0.1
- ~~CBOR serialization of canonical form~~ (deferred)
- ✅ Content-addressed symbol store (sha256 of canonical JSON)
- Structural diff and merge
- ~~Richer primitive library (math, collections, string)~~ ✅
- Better error messages that walk the intent graph ✅
- ✅ Capability manifest (agent-facing self-description)

## v0.2
- ✅ CBOR serialization alongside JSON (shipped one release early).
  Both forms produce byte-identical output across Python and Rust
  implementations on every example. Content addressing works over
  either form with distinct identities per form.
- Migration of primary content hash from JSON to CBOR. Breaking
  change; belongs with a v1.0-approaching release that invalidates
  all existing identities.

## v0.2
- Effect inference (so signatures can be partially elided)
- Guard ranking (cost annotations on candidates; dispatcher picks cheapest
  satisfying)
- Time-indexed types: `T@<timestamp>`
- Refusal (`bottom`) propagation semantics formalized

## v0.3
- Port of the interpreter hot path to Rust
- Graph-native runtime: parallel evaluation of independent dataflow nodes
- RPC API for agents to speak canonical form directly without text

## v1.0
- Formal semantics document
- Conformance test suite
- Stable canonical form
- Editor integration that displays the hypergraph, not the text
