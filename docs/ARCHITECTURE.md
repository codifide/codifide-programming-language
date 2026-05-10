# Noema — Architecture

How the code is organized, for someone who wants to contribute. This is the
builder's map. For the specification, read `docs/CANONICAL.md`; for the
surface tour, read `docs/LANGUAGE.md`.

## Layered structure

Noema's reference implementation is four layers stacked on a shared data
model. Each layer depends only on the ones below it.

```
  +--------+  +-------+  +-----------+
  |  CLI   |  | tests |  | dispatches|
  +--------+  +-------+  +-----------+
       \        |         /
        v       v        v
  +----------------------------+
  |         runtime            |   interpreter, effects, typed errors
  +----------------------------+
          |            |
          v            v
  +-----------+  +-----------+
  | projection |  |   store   |   canonical JSON, bytes, hash   |   content-addressed store
  +-----------+  +-----------+
          |            |
          v            v
  +----------------------------+
  |          parser            |   surface .nm -> canonical AST
  +----------------------------+
               |
               v
  +----------------------------+
  |           core             |   canonical types (AST dataclasses)
  +----------------------------+
```

- **core** (`noema/core/types.py`). The canonical hypergraph as Python
  dataclasses. `Module`, `Definition`, `Candidate`, `Signature`, `Param`,
  `Expr` as a tagged union of `Lit`, `Ref`, `Call`, `Bind`, `Seq`,
  `Believe`, `BottomExpr`, `Concat`, `Attr`. Runtime-only types `Value`,
  `Belief`, and `Bottom` also live here because they are part of the
  language's data model. Everything above this layer speaks in these
  types.

- **parser** (`noema/parser/`). Surface `.nm` source to canonical AST.
  The outer parser in `parser.py` is line-oriented and delegates
  expression parsing to `expr_parser.py`, which tokenizes through
  `lexer.py` using the keyword table in `tokens.py`. The parser never
  executes anything; it produces a `Module` or raises `ParseError`.

- **projection** (`noema/projection/canonical.py`). Canonical AST to
  canonical JSON and back, plus `canonical_bytes` (deterministic byte
  form) and `content_hash` (`sha256:<hex>` over the byte form). This is
  the layer that agrees with the Rust crate.

- **runtime** (`noema/runtime/`). `interpreter.py` is a tree-walker;
  `primitives.py` is the registry of effect-labeled primitives;
  `errors.py` declares the eight typed errors.

- **store** (`noema/store/`). Filesystem-backed content-addressed symbol
  store. Used by the runtime to resolve imports and by the CLI directly.

- **CLI** (`noema/__main__.py`). `run`, `canonical`, `test`, and the
  `store put|get|list|hash|index` subcommands.

## Two-implementation strategy

There are two implementations of the canonical form. The Python reference
is authoritative for semantics; the Rust crate is authoritative for
nothing — it exists to force the specification out of code and into
`docs/CANONICAL.md`.

```
  .nm source
      |
      v
  +--------------+                   +---------------------+
  | Python parse |                   |   Rust canonical    |
  | noema.parse  |                   |   crates/noema-     |
  +------+-------+                   |   canonical         |
         |                           +----------+----------+
         v                                      |
  +--------------+                              |
  | canonical    |<-- canonical JSON ----------+|
  | JSON         |                             ||
  +------+-------+                             v|
         |                           +---------+-----------+
         v                           | canonical bytes     |
  +--------------+                   | + content hash      |
  | canonical    |                   +---------+-----------+
  | bytes + hash |<===== byte-for-byte =========
  +--------------+
```

The two implementations meet in one place: `tests/test_conformance.py`.
Every example is parsed by Python, emitted as canonical JSON, handed to
the Rust binary, and the Rust round-trip bytes are compared against the
Python canonical bytes byte-for-byte. Content hashes are compared the
same way. If `cargo` is absent, the test skips with a clear reason
rather than silently pass.

The Rust crate does not parse `.nm` surface syntax. It does not include
an interpreter. Both are deliberate. Semantics are still changing (see
`docs/ROADMAP.md`); porting moving targets doubles the cost of every
semantics change. The canonical form is the stablest piece of Noema, and
it is also the piece whose cross-implementation agreement matters most
because it is what gets hashed and shipped between agents.

For the full reasoning, read `docs/RUST.md`.

## How effects are checked

Effect enforcement has two halves. Both live in
`noema/runtime/interpreter.py`.

**Primitive-call half** (inside `Interpreter._call_primitive`). Every
primitive has a declared effect label (or `None` for pure). Before
running the primitive, the interpreter checks that its effect is in the
current frame's allowed set. During normal body evaluation the allowed
set is the surrounding definition's `signature.effects`; during contract
evaluation (pre, post, guards) it is the empty set, enforced by
`_with_pure_budget`. A mismatch raises `EffectViolation`.

**Transitive half** (in `_check_transitive_effects`, runs once per
module at load time before any body executes). For every definition
`d`, for every user-function call reachable from any candidate body,
guard, precondition, or postcondition, the callee's declared effects
must be a subset of `d`'s declared effects. Imports participate in the
check exactly as local definitions do; their effect sets are read from
the canonical JSON the store returns. Violations are reported against
the caller, which promised something it cannot deliver on without the
callee's effect budget.

Why a static pass rather than a call-site runtime check: errors here
are authoring mistakes, not execution-time accidents. Surfacing them
before dispatch makes the failure mode the same whether the bug is on a
cold path or a hot one. This is the property that lets an agent reason
globally about side effects.

## How imports resolve

Import resolution is two-stage.

**Parse-time stage** (`noema/parser/parser.py`). Surface forms:

- `import <name> = sha256:<hex>` — direct binding, no store needed at
  parse time. The `(name, identity)` pair lands in `Module.imports`.
- `from sha256:<hex> import <name1>, <name2>` — the target must be
  present in the store at parse time. The parser opens the store, fetches
  the target module's canonical JSON, reads its `imports` map, and
  resolves each requested name to the per-symbol identity the target
  assigned it. Those resolved pairs land in the consumer's `Module.imports`
  identically to the direct form.

**Load-time stage** (`noema/runtime/interpreter._ResolvedImports.from_module`).
When `run()` receives a module with imports, it requires a `store=`
argument. It iterates the imports, fetches each identity, reconstructs a
`Definition` from its canonical JSON, and builds a name-to-`Definition`
map. This map is passed into the `Interpreter` alongside the module.

At call sites, `Interpreter._call` tries local definitions first, then
imports, then primitives. Shadowing is specified in
`docs/CANONICAL.md §Shadowing`. The effect check in
`_check_transitive_effects` already treats imported callees uniformly
with local ones, so shadowing cannot smuggle effects past it.

## How the store works on disk

`noema/store/symbol_store.py` is a filesystem-backed key-value store.

**Layout.** Git-style sharded loose objects:

```
<root>/sha256/
  ab/
    abcd...ef.json
  cd/
    cdef...01.json
  ...
```

The first two hex characters of the digest are a sharding prefix so a
single directory does not accumulate tens of thousands of files. This is
the same shape Git uses for loose objects; filesystem performance stays
reasonable at scale.

**Atomic writes.** Bytes go to a temporary file in the same directory
(so the rename is within one filesystem) via `tempfile.mkstemp`,
`write`, `flush`, `fsync`, and then `os.replace` into place. A crashed
writer leaves no half-written object visible; the temp file is cleaned
up on the next run.

**Hash-verified reads.** `SymbolStore.get_bytes` re-hashes the bytes on
disk and compares them to the identity the caller asked for. Mismatch
raises `IntegrityError` rather than returning a value. Reads never
trust the disk.

**Hash-verified writes.** `_write_atomic` hashes the bytes before
accepting them. A caller who asks the store to save bytes under an
identity those bytes do not produce gets `IntegrityError` — defense
against the caller, not against the disk.

**Idempotent writes.** Storing bytes that already exist under the same
identity is a no-op. Content addressing makes this correct: same bytes,
same hash, same object.

**Indices.** An index is a `Module` with empty `symbols` and a non-empty
`imports` map. The `store index` CLI subcommand builds one from
name-to-identity pairs, computes its content hash the same way any
other module's hash is computed (over `to_canonical(module)`), and
writes through the same atomic-write path. The on-disk layout makes no
distinction between a symbol object and an index object.

The spec-level contract is in `docs/CANONICAL.md §Symbol store`: three
properties (hash-verified reads, hash-verified writes, idempotent
writes) that any conforming implementation must uphold. A different
on-disk layout is fine so long as those hold.

## How conformance is maintained

The conformance surface is `tests/test_conformance.py`. The test flow:

1. `setUpClass` checks for `cargo` and builds the Rust binary with
   `cargo build --release -p noema-canonical`. If either step fails, every
   test in the class is skipped with a message naming what failed.
2. For each `examples/*.nm`:
   a. Parse with Python. Emit canonical JSON.
   b. Compute Python canonical bytes and hash.
   c. Run the Rust binary `noema-canonical bytes` on the canonical JSON.
   d. Run the Rust binary `noema-canonical hash` on the canonical JSON.
   e. Assert byte-equality on the serialized bytes.
   f. Assert equality on the `sha256:<hex>` identity.

If the two ever disagree, the specification is the adjudicator. One of
the implementations is a bug against the spec. If both agree but the
spec is silent, the spec is the bug. This rule is in `docs/RUST.md` and
the test's module docstring.

## File map for contributors

| You want to...                       | File                                    |
|--------------------------------------|-----------------------------------------|
| Add an AST node kind                 | `noema/core/types.py`                   |
| Parse a new surface construct        | `noema/parser/parser.py`                |
| Parse a new expression form          | `noema/parser/expr_parser.py`           |
| Add a keyword or glyph               | `noema/parser/tokens.py`                |
| Add a primitive                      | `noema/runtime/primitives.py`           |
| Change interpreter evaluation        | `noema/runtime/interpreter.py`          |
| Change effect-check logic            | `noema/runtime/interpreter.py` (`_check_transitive_effects`) |
| Add a typed error                    | `noema/runtime/errors.py`               |
| Change canonical JSON shape          | `noema/projection/canonical.py`         |
| Change store on-disk layout          | `noema/store/symbol_store.py`           |
| Add a CLI subcommand                 | `noema/__main__.py`                     |
| Keep the Rust crate in sync          | `crates/noema-canonical/src/`           |

## Test topology

```
tests/
  test_parser.py             surface -> canonical
  test_parser_fuzz.py        adversarial surface input
  test_canonical.py          canonical round-trip and structural rules
  test_runtime.py            interpreter semantics
  test_store.py              store properties (round-trip, integrity, etc.)
  test_store_concurrency.py  concurrent puts of the same symbol
  test_imports.py            import resolution and effect check across imports
  test_indices.py            index identity, from-imports, shadowing
  test_conformance.py        Python <-> Rust byte and hash agreement
```

Run the full suite with `python3 -m noema test`. Run Rust tests with
`cargo test --release -p noema-canonical`.

## Persona interaction

The three personas in `.kiro/steering/personas/` are not code, but they
shape what lands here. Sable files audits in `dispatches/<date>-*.md`.
Quill writes paired human readouts as `dispatches/<date>-*.readout.md`.
Glyph writes structured agent dispatches as `dispatches/<date>-*.yaml`.
Every milestone produces a Quill readout and a Glyph dispatch; Sable
runs at gate transitions. The dispatches are the project's journal;
read them chronologically to see how the language evolved.
