# Noema Changelog

All notable changes to Noema are recorded here. Releases follow semver once we
reach v1.0; until then, the canonical form may change between minor versions.

## [0.1.0] — 2026-05-10

### Added
- Canonical JSON schema for the Noema hypergraph (`docs/CANONICAL.md`)
- Surface parser accepting ASCII keywords and unicode glyphs
- Tree-walking interpreter with:
  - Effect declaration and enforcement on primitive calls
  - Preconditions and postconditions as machine-checked clauses
  - Multi-candidate dispatch with declaration-order guards
  - Belief-dispatch on runtime confidence
  - First-class refusal (`bottom` / `⊥`)
- CLI entry point: `run`, `canonical`, `test`
- Three runnable example programs
- Test suite (19 tests, all passing)
- Two-journalist persona system (Quill, Glyph) with first snapshot dispatch

### Known limitations (call out deliberately)
- Effect subset checking is local to primitive call sites; it does not yet
  verify callee-effects ⊆ caller-effects across the call graph.
- Canonical form serializes to JSON only; CBOR and content-addressing arrive
  in 0.1.x.
- Candidate dispatch uses guards only; cost-based dispatch is future work.
- No type inference beyond literals.
- Reference interpreter is Python; Rust port scheduled for 0.3.

### Roadmap pointer
See `docs/ROADMAP.md` for the phased plan.
