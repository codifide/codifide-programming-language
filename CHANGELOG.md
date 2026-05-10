# Noema Changelog

All notable changes to Noema are recorded here. Releases follow semver once we
reach v1.0; until then, the canonical form may change between minor versions.

## [Unreleased]

### Added
- **Intent-graph error messages.** `EffectViolation` and
  `ContractViolation` now render the full call path on failure, each
  frame annotated with its intent. "The function exists because: ..."
  at every level.
- **Expanded pure primitive library:**
  - Math: `abs`, `min`, `max`, `pow`, `floor`, `ceil`, `round`.
  - Collections: `min_of`, `max_of`, `sum`, `reverse`, `append`
    (non-mutating), `contains_item`.
  - Strings: `upper`, `lower`, `trim`, `starts_with`, `ends_with`,
    `replace`, `split`, `join`.
- **`noema store verify <hash>`** — opt-in subcommand that walks a
  stored module's imports and reports any pointees missing from the
  store. Closes Sable's P3-1 from the index audit.
- **Parser fuzz harness** (`tests/test_parser_fuzz.py`) — 30
  hand-curated adversarial inputs + 200 structurally generated samples,
  each bounded by a 1s SIGALRM so hangs surface as failures.
- **Store concurrency test** (`tests/test_store_concurrency.py`) —
  8-process races on the same symbol and on distinct symbols; verifies
  identity agreement, object count, and absence of leftover temp files.
- **Documentation refresh:**
  - `README.md` rewritten to reflect current reality.
  - `docs/LANGUAGE.md` updated with imports, indices, shadowing,
    typed errors, recursion limit, store CLI.
  - `docs/TUTORIAL.md` new — end-to-end walk-through from first
    program to publishing and consuming an index.
  - `docs/ARCHITECTURE.md` new — layered structure for contributors.
  - `GETTING_STARTED.md` updated with the full-story walk-through.
- `sessions/2026-05-10.md` — session state for resumption.

### Fixed
- **P1-3: Lexer errors leaked as `LexError` through the parser's
  contract.** `_safe_parse_expr` now catches both `ExprParseError` and
  `LexError` and wraps them in `ParseError`. Found by the fuzz
  harness; affected unclosed strings, non-ASCII outside strings, and
  stray operator sequences.
- **P1-4: Deep parenthesis nesting blew the Python stack.** The
  expression parser now bounds paren nesting at 256 and raises a
  typed `ParseError` past that.

### Test count
76 passing (71 previous + 5 primitive library + 2 store verify + 2
parser fuzz + 2 store concurrency + 1 intent-chain -1 merged).

## [Content-addressed indices]

### Added
- **Content-addressed indices.** An *index* is a module whose
  `imports` map is its export table. New CLI subcommand:
  ```
  noema store index --name <mod> name=sha256:<hex> ...
  ```
  which mints an index, stores it, and prints its identity. The index
  is itself content-addressed: same inputs produce the same hash;
  changing the module name or the entry set changes the hash; entry
  order does not.
- **`from <identity> import <names>` surface syntax.** A consumer
  writes `from sha256:... import hello, goodbye` and the parser
  resolves each name through the target's `imports` map, binding it
  in the consumer's own imports. The result is shape-identical to a
  consumer that wrote the direct identity-per-name form.
- `parse(source, store=...)` for `from`-import resolution; the CLI's
  `run` subcommand opens the store on demand.
- Transitive effect check flows through indices unchanged: a pure
  consumer cannot launder effects by routing an effectful symbol
  through an index.
- Spec updates:
  - `docs/CANONICAL.md §Shadowing` — locals over imports over
    primitives; effect checks apply to the resolved callee.
  - `docs/CANONICAL.md §Indices and \`from\`-imports` — index
    definition, grammar, parse-time resolution allowed.
- `tests/test_indices.py` — 13 tests covering index identity,
  order-independence, name sensitivity, parse-time resolution,
  effect check through indices, shadowing, and rejection of
  non-index targets.
- `dispatches/2026-05-10-index-audit.md` — Sable's audit of the new
  surface (two P3s, no higher).

### Test count
64 passing (51 previous + 13 new index/shadowing).

## [Content-addressed imports]

### Added
- **Content-addressed imports.** Modules can now reference other
  symbols by content identity. Surface syntax:
  ```
  import <local_name> = sha256:<hex>
  ```
  Imports are resolved through a symbol store at runtime; the
  interpreter accepts a `store=` argument, and the CLI's `run`
  subcommand gained a `--store` flag matching `store` subcommand
  conventions. An imported callee behaves exactly like a local `def`
  at the call site — same effect check, same contracts, same
  dispatch.
- Transitive effect check now treats imported callees uniformly with
  local ones. A pure caller cannot import an effectful symbol and
  launder its effects; content identity is the property that keeps
  this sound (the adversary cannot substitute a more-effectful body
  under the same hash).
- Canonical form gained an optional top-level `imports` field, emitted
  only when present and sorted by local name for stable bytes.
- `tests/test_imports.py` — 11 tests covering resolution, missing
  identity rejection, tamper detection through the runtime, effect
  check across imports, canonical round-trip, and surface-syntax
  rejection of malformed identities.
- `examples/imports_demo.nm` — documents the capability and conformance
  surface; the Rust canonical crate accepts the same `imports` key.
- Spec update in `docs/CANONICAL.md §Top-level shape` describing
  imports formally.

### Changed
- `Module` grew an `imports` field (tuple of `(name, identity)`
  pairs). Modules without imports canonicalize identically to before.

### Test count
51 passing (40 previous + 11 new).

## [Symbol store]

### Added
- **Content-addressed symbol store** (`noema/store/`). Store symbols by
  SHA-256 of their canonical byte form; fetch by identity; verify hash
  on read (tampering raises `IntegrityError`, never returns a value);
  idempotent writes. Filesystem layout is Git-style sharded loose
  objects with atomic temp-file-plus-rename writes.
- CLI subcommands:
  - `noema store put <file.nm>` — store every symbol in a module.
  - `noema store get <hash>`     — print canonical JSON for an identity.
  - `noema store list`           — list every stored identity.
  - `noema store hash <file.nm>` — print identities without storing.
  - Store root via `--store`, `$NOEMA_STORE`, or default `~/.noema/store`.
- Typed store errors: `StoreError`, `NotFound`, `IntegrityError`.
- `tests/test_store.py` — 13 tests covering hashing properties, store
  round-trip, idempotency, tamper detection, malformed identity
  rejection, and cross-implementation hash agreement with the Rust
  binary.
- Spec addition in `docs/CANONICAL.md §Symbol store` — the three
  properties a conforming store must uphold (hash-verified reads,
  hash-verified writes, idempotent writes).
- Test suite closures: nested-believe round-trip in canonical form,
  numeric-edge Python/Rust conformance (both closed from audit
  unknowns; the parser does not yet accept multi-line believe-arm
  values, noted as a surface-syntax limitation not a spec one).
- `cargo audit` run: 0 vulnerabilities across 22 transitive deps.

### Test count
40 passing (28 previous + 12 new: 11 store + 1 nested believe).

## [Sable audit resolution]

### Added
- **Sable persona** (`.kiro/steering/personas/sable.md`) — adversarial
  auditor role distinct from the two journalists. Every milestone now
  runs three personas: Sable tries to break it, Quill reports it in
  prose, Glyph emits a structured dispatch.
- Transitive effect subset check: every callee's declared effects must
  be a subset of every caller's. Enforced as a static pass at module
  load. Closes security audit P0-1.
- Typed primitive errors: `PrimitiveError`, `BottomPropagationError`,
  `RecursionLimitError`. Host-language exceptions (ZeroDivisionError,
  IndexError, TypeError) no longer leak through the Noema error
  surface. Closes audit P1-1.
- Interpreter call-depth limit (`DEFAULT_MAX_DEPTH=64`) with typed
  `RecursionLimitError`. Defense-in-depth mapping in `run()` catches
  Python `RecursionError` if it wins the race. Closes audit P1-2.
- Rust canonical writer now ASCII-escapes non-ASCII codepoints to
  match Python's `json.dumps(ensure_ascii=True)` byte-for-byte. Closes
  audit P0-2.
- Python parser no longer double-decodes non-ASCII string literals via
  the `unicode_escape` path. Closes the second half of P0-2.
- `examples/unicode.nm` — non-ASCII conformance fixture. The
  conformance test now exercises byte-for-byte agreement on non-ASCII
  content with every run.
- Spec additions in `docs/CANONICAL.md`:
  - §Canonical serialization explicitly mandates ASCII-escaped strings.
  - §Contracts are pure — pre, post, guard run with effect budget ∅.
  - §Module names — grammar `[A-Za-z_][A-Za-z0-9_.-]*` required.
  - §Errors — eight typed error kinds enumerated.
  - §Content addressing clarifies that intent is part of identity.

### Changed
- Contracts (pre, post, guard) evaluate with an effect budget of ∅
  regardless of the surrounding signature. Closes audit P2-1.
- Module names are restricted to identifier grammar. Closes audit P2-2.

### Security
- See `dispatches/2026-05-10-security-audit.md` for the full audit
  report and `dispatches/2026-05-10-post-audit.yaml` for the
  structured resolution dispatch.
- Test count: 28 passing (23 previous + 5 security regressions).

## [Rust canonical addition]

### Added
- `docs/CANONICAL.md` expanded into a specification an independent
  implementer can follow without reading Python — normalization rules,
  canonical byte form, content-addressing scheme, effect algebra with the
  transitive-subset rule called out explicitly, dispatch and belief
  semantics.
- `crates/noema-canonical/` — a Rust crate implementing the canonical
  form (AST, JSON round-trip, canonical byte form, SHA-256 content hash)
  and a small `noema-canonical` CLI.
- Python-side `canonical_bytes` and `content_hash` helpers in
  `noema.projection.canonical`, exported from the top-level package.
- `docs/RUST.md` describing the two-implementation strategy and why the
  interpreter is deliberately not ported yet.
- `tests/test_conformance.py` — byte-for-byte and content-hash conformance
  between the Python reference and the Rust crate on every example.

### Notes
- The Rust crate deliberately omits the interpreter. Semantics are still
  changing (the transitive effect-subset check will alter runtime
  behavior) and porting a moving target doubles the cost of every
  semantics change. Canonical form is the stablest piece of Noema and the
  piece whose cross-implementation agreement matters most.
- Test count: 21 passing (19 previous + 2 conformance).

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
