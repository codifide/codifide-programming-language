---
inclusion: auto
---

# Coding Standards & Quality Gates

These standards apply to all code produced in this project, whether written by AI or human.

---

## Test Coverage

| Category | Target | Rationale |
|----------|--------|-----------|
| New interpreter code | **100%** | Semantic correctness is non-negotiable |
| New parser code | **100%** | Parse errors must be deterministic |
| New store code | **100%** | Data loss is not acceptable |
| Canonical form / CBOR | **100%** | Byte-level conformance is the contract |
| Security-sensitive code | **100%** | Effect enforcement, sandboxing |
| CLI / surface commands | **95%** | High-impact user-facing paths |
| Legacy / ported code | **95%** critical, **80%** services | Risk-based |
| Generated / boilerplate | **Excluded** | Not our code |

### Exception Process
If code genuinely cannot reach the target:
1. Document the reason in a code comment: `# COVERAGE-EXCEPTION: <reason>`
2. Create a tracking ticket
3. Aegis approves or rejects
4. "It's hard to test" is NOT a valid reason

---

## Conformance Rule

**Python and Rust runtimes must produce byte-identical canonical output on all test programs.**

- Every new language feature must have a conformance test in `tests/test_conformance.py`
- Conformance tests run against both runtimes
- A divergence between Python and Rust is a **P0 blocker** — not a MINOR finding
- The Rust canonical crate (`crates/codifide-canonical/`) is the reference for CBOR encoding

---

## Security Standards

### Every Change
- No secrets in source code
- No host-language exceptions leaking through typed error boundaries
- Effect enforcement must be transitive — a lie in `effects {}` gets caught at module load
- Sandboxing: a Codifide program must not be able to escape into the host

### Interpreter Level
- All primitives validate their arguments before executing
- `bottom` propagation must raise `BottomPropagationError` before reaching a primitive
- `RecursionLimitError` must fire before the host stack overflows
- Effect budget is checked before any effectful primitive executes

### Store Level
- Atomic writes only — no partial writes visible to readers
- Sharded loose objects — no single-file corruption takes down the store
- GC must not collect objects reachable from any live root
- Symlink writes are forbidden (P1 finding from 2026-05-10 audit, resolved)

### Review Triggers
Sentinel reviews any change that touches:
- Effect enforcement logic
- The `bottom` propagation path
- The symbol store (reads, writes, GC)
- The canonical form encoder/decoder
- The CLI's file I/O (unbounded reads are a P1 — resolved 2026-05-11)
- Any new primitive with side effects

---

## Code Quality

### Naming
- Clear, descriptive names — no abbreviations unless universally understood in PL theory
- Functions describe what they DO, not how
- Boolean variables read as questions (`is_pure`, `has_effect`, `can_dispatch`)

### Architecture
- Single responsibility — one reason to change
- The interpreter, parser, store, and projection layers are separate modules; keep them that way
- No god objects
- Dependencies injected, not created internally
- The Python reference implementation is the spec; the Rust implementation must conform to it

### Documentation
- Public APIs have doc comments
- Complex logic has inline comments explaining WHY (not what)
- ADRs for significant decisions
- `docs/CHANGELOG.md` updated for every user-visible change
- Capability manifest regenerated whenever the primitive surface changes

---

## CI Requirements

Every change must pass:
1. **Build** — `python3 -m codifide` imports without error; `cargo build` succeeds
2. **Tests** — all Python tests pass (`pytest`); all Rust tests pass (`cargo test`)
3. **Conformance** — `tests/test_conformance.py` passes on both runtimes
4. **Dispatch check** — `python3 -m codifide dispatch-check` exits 0
5. **Capability manifest** — if primitives changed, manifest is regenerated and drift test passes

---

## Patterns Learned from Adversarial Review

### Effect Enforcement Must Be Transitive
A function declared `effects {}` that calls an effectful primitive must fail at module load, not at call time. The check happens when the module is loaded, not when the function is invoked.

### `bottom` Propagation Is Not Catchable with `is_bottom()`
`is_bottom(x)` only works on literal `bottom` values. A `bottom` that propagated through a bind raises `BottomPropagationError` before `is_bottom` sees it. This is documented in `AGENT_QUICKREF.md` and the capability manifest `note` field. Do not change this behavior without a conformance test and a Sable audit.

### Bind-Before-When Is a Parser Responsibility
The `when` guard executes before the candidate body. A bind (`<-`) is part of the body. The parser should catch bind-before-when statically (REQ-V2-2). Until V2-2 ships, the runtime hint in `_unbound_name_message` must stay in place.

### From-Import Requires Python Runtime Until V2-3 Ships
`from <hash> import name` is not yet supported in the Rust parser. The error message explains this and instructs the user to set `CODIFIDE_RUNTIME=python`. Do not remove this message until V2-3 is complete.
