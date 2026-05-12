# Codifide — Canonical Form

The canonical form is the source of truth. Surface text is a projection. Two
programs are the same program iff their canonical forms are equal under the
normalization rules below.

In v0.1 the canonical form serializes to both CBOR (primary, RFC 8949
§4.2 deterministic subset, wire and identity form) and JSON (secondary,
human-inspectable). The primary content identity is the SHA-256 over
canonical CBOR bytes; this was migrated from JSON on 2026-05-11 because
shortest-decimal float writers in Python and Rust disagree on some
values, making JSON byte-agreement impossible for f16-class floats. CBOR
hashes over IEEE-754 bits and sidesteps the issue entirely. See
``dispatches/2026-05-11-primary-hash-migration-proposal.readout.md``
for the full rationale and
``dispatches/2026-05-11-cbor-reaudit.md`` AUD-08 for the
triggering finding.

This document is the specification an independent implementer should be able
to follow without reading the reference Python source. Where the reference
implementation and this document disagree, this document is the bug.

## Versioning

The top-level `codifide` field pins the schema version. Implementations MUST
reject documents whose version they do not understand. v0 is `"0.1"`.

## Top-level shape

```json
{
  "codifide": "0.1",
  "module": "example",
  "symbols": {
    "<name>": <Definition>,
    ...
  },
  "imports": {
    "<local_name>": "sha256:<hex>",
    ...
  }
}
```

`symbols` is a map from symbol name to `Definition`. `imports` is
optional; when present, it is a map from a local name to a content
identity that resolves through a symbol store (see §Symbol store). The
`imports` key MUST be omitted when empty. Two `Module`s are equal iff
their `name`, `codifide` version, `symbols` map, and `imports` map are
equal. Map ordering does not matter for equality.

An imported symbol is callable by its local name from any expression in
the module. At load time, the implementation MUST resolve each
identity through a symbol store and reject any module whose imports
cannot be satisfied. The transitive effect check (§Effect algebra)
treats imported callees identically to local ones: their declared
effects must be a subset of the caller's declared effects. The
identity-addressing property is what makes this sound — an adversary
cannot substitute a more-effectful body under the same identity
without changing the identity itself.

## Shadowing

When a local definition name, an imported local name, and a primitive
name collide, resolution MUST proceed in this order:

1. Local definition in the module (via `symbols`).
2. Imported name (via `imports`).
3. Primitive registered in the host.

This means a local `def foo` shadows `import foo = ...`, and an
imported name shadows a primitive of the same name. The ordering is
chosen so that a consumer who authors a local name sees their own
definition (the more recent intent) rather than something they
imported earlier; effects are still checked against the resolved
callee, so shadowing cannot be used to smuggle effects past the
transitive check.

## Indices and `from`-imports

An *index* is a module whose `imports` map is its export table. A
consumer may write

```
from <identity> import name1, name2, ...
```

at the top of a module to bind each listed name to the identity the
target module's `imports` table assigns it. The target MUST be a
module that is already present in the store; the target's local
`symbols` are not reachable via `from`-imports (to re-export a locally
defined symbol, the target must first import it by its own content
identity). The resulting consumer module has the same canonical shape
as one that wrote each `import name = sha256:...` line directly.

Implementations MAY resolve `from`-imports at parse time (the Python
reference does); they MUST reject a `from`-import of a name that is
not in the target's `imports` table.

## Definition

```json
{
  "kind": "definition",
  "intent": "welcome a known user by name",
  "signature": {
    "params": [{"name": "user", "type": "User"}],
    "returns": "Unit",
    "effects": ["clock.read", "io.stdout"]
  },
  "pre":  [<Expr>, ...],
  "post": [<Expr>, ...],
  "candidates": [<Candidate>, ...]
}
```

The definition's *name* is the key under which it appears in `symbols`; it is
NOT repeated inside the definition body.

`intent` is a non-empty string. It is a structural error to emit or accept a
definition whose intent is empty or whitespace.

`candidates` is a non-empty array; declaration order is significant (see
§Dispatch).

### Candidate

```json
{
  "kind": "candidate",
  "intent": "default",
  "guard": <Expr or null>,
  "body":  <Expr>,
  "cost":  <non-negative integer, optional, ≤ 2^64 - 1>
}
```

The optional `cost` field was added 2026-05-11. When present it MUST
be a non-negative integer in the range `[0, 2^64 - 1]` (no decimal
point, no exponent; in CBOR major type 0). The range bound matches
what a 64-bit-integer second implementation can represent without
loss; in practice agents annotate costs in the range of ones to
millions, so the bound is generous. The field is emitted only when
the candidate declares a cost; absence of the field is the canonical
representation of "effective cost +∞" for dispatch purposes (see
§Dispatch). Non-conforming values — floats, negatives, strings,
nulls, integers above 2^64 - 1 — MUST be rejected by the
implementation with a typed parse error. Implementations that
predate the amendment MUST ignore a `cost` field they do not
recognize rather than reject the whole candidate: unknown-field
tolerance is the forward-compatibility rule.

## Expression AST

Every expression node is a JSON object with a `kind` discriminator. Unknown
kinds MUST cause a parse error.

| kind      | payload                                                                 |
|-----------|-------------------------------------------------------------------------|
| `lit`     | `{"value": <json>, "type": <str>, "conf": <float>, "provenance": <str>}` |
| `ref`     | `{"name": <str>}`                                                       |
| `call`    | `{"fn": <str>, "args": [<Expr>, ...]}`                                  |
| `bind`    | `{"name": <str>, "expr": <Expr>, "in": <Expr>}`                         |
| `seq`     | `{"steps": [<Expr>, ...]}`                                              |
| `if`      | `{"cond": <Expr>, "then": <Expr>, "else": <Expr>}`                      |
| `believe` | `{"subject": <Expr>, "arms": [[<Expr>, <Expr>], ...], "else": <Expr>}`  |
| `bottom`  | `{}`                                                                    |
| `concat`  | `{"parts": [<Expr>, ...]}`                                              |
| `attr`    | `{"target": <Expr>, "name": <str>}`                                     |

The `if` node added 2026-05-11: short-circuit inline conditional.
Exactly one of `then` / `else` evaluates per call, chosen by the
truthiness of `cond`. Unlike candidate-dispatch guards (which all
evaluate before selection), `if` does not evaluate the un-taken
branch; this is the tool for expressions that would otherwise
raise if both branches ran.

For `lit`: `conf` is a float in `[0.0, 1.0]`; `provenance` is a free-form
string tag (default `"literal"` for source-literal values).

## Normalization

Two canonical JSON documents are *structurally equal* iff they are equal as
JSON values (RFC 8259) under the following normalization:

1. **Object keys are sorted lexicographically (Unicode codepoint order).**
   This applies recursively at every depth.
2. **Numbers are compared as IEEE-754 binary64.** `1`, `1.0`, and `1e0` are
   equal. NaN MUST NOT appear in a canonical document.
3. **Strings are compared by Unicode codepoint sequence after NFC.**
4. **Arrays preserve order.** Ordering of `pre`, `post`, `candidates`,
   `args`, `steps`, `parts`, `arms`, and `params` is semantically
   significant and MUST be preserved.
5. **Effect sets serialize as arrays sorted lexicographically.** A set is
   equal regardless of authoring order; canonical form is the sorted array.

## Canonical serialization

Codifide defines two canonical byte forms: a JSON form (v0.1 primary, used
for debugging and interoperability) and a CBOR form (v0.2 binary, used
for wire transport and storage efficiency). An implementation MAY
produce either or both; when both are present they MUST agree on every
abstract value (same Module → same JSON bytes, same Module → same CBOR
bytes).

### JSON byte form

For content-addressing and wire transport, we define a single *canonical
byte form* per document:

- UTF-8 encoding, no BOM.
- No insignificant whitespace.
- Object keys sorted as in §Normalization rule 1.
- Numbers serialized as the shortest round-trippable decimal
  representation of their binary64 value (e.g. `0.85`, `1.0`, `-3`).
- **Strings emitted as JSON strings, ASCII-escaped.** Every codepoint
  above U+007F is emitted as `\uXXXX` (lowercase hex), or as a UTF-16
  surrogate pair for codepoints above U+FFFF. This matches Python's
  `json.dumps(ensure_ascii=True)` byte-for-byte and keeps the byte form
  transport-neutral.
- Named escapes `\b \f \n \r \t` are used for their corresponding
  control bytes; other control bytes below 0x20 use `\uXXXX`. U+007F
  (DEL) is emitted as its raw byte to match the Python reference.

### CBOR byte form

Encoded per RFC 8949 §4.2 Deterministically Encoded CBOR. The rules:

- Integers use the shortest major-type-0/1 head. Integers outside the
  `[-2^64, 2^64)` range use tagged bignum (tag 2 for positive, tag 3
  for negative) with a shortest-byte-string body with no leading zero.
- Floats use the shortest IEEE-754 binary encoding that preserves the
  value exactly, including sign of zero: half-precision (`0xF9`) if
  possible, else single (`0xFA`), else double (`0xFB`). NaN and
  infinity MUST NOT appear in a canonical document.
- Byte and text strings use the shortest length-prefixed head.
  Indefinite-length strings MUST NOT appear.
- Arrays use definite-length encoding.
- Maps use definite-length encoding; pairs MUST be sorted by their
  encoded key bytes in bytewise lexicographic order.
- Simple values are restricted to `false` (0xF4), `true` (0xF5), and
  `null` (0xF6). No other tags (apart from bignums as above) may appear.

A CBOR byte form typically runs 25-30% shorter than the JSON byte form
for the same abstract document, with no loss of fidelity.

The canonical byte form is what gets hashed for content-addressing. Two
documents that are structurally equal produce identical canonical byte form
and therefore identical content hashes.

## Content addressing

A symbol's **primary identity** is the SHA-256 of its canonical CBOR
byte form, hex-encoded and prefixed with `sha256:`. The identity of a
definition is the hash of the canonical CBOR encoding of its containing
single-entry `Module` envelope, so that a standalone definition has a
stable hash.

A symbol also has a **legacy JSON identity** — the SHA-256 of its
canonical JSON byte form. This exists so pre-2026-05-11 stored objects
remain addressable; new writes use the primary (CBOR) identity. The two
identities are distinct and cannot be computed from one another without
materializing the symbol's abstract form and re-encoding; this is the
correct behavior, because content addressing is a property of the bytes
themselves, not of the abstract meaning. Collapsing the two identities
would break the one-to-one correspondence between a hash and the bytes
it names.

Agents exchanging content-addressed references MUST agree on which form
they use. The default and the convention is CBOR. A reference that does
not declare its wire form is CBOR.

Implementations are not required to compute hashes unless they
participate in a content-addressed store. When they do, agreement on the
CBOR byte form is mandatory; agreement on the JSON byte form holds only
for values that round-trip identically through every implementation's
JSON decimal writer, which in practice excludes floats near the
half-precision or single-precision boundaries (see
``dispatches/2026-05-11-cbor-reaudit.md`` AUD-08).

### Symbol store

A *symbol store* is a map from identity to canonical bytes. Stores MUST:

- Verify the hash of data before returning it on read. Tampered or
  corrupted bytes MUST raise an integrity error, never return a value.
- Refuse any write whose bytes do not hash to the declared identity.
- Treat writes as idempotent: storing the same identity twice is a
  no-op.

The reference Python store is in `codifide/store/`. It writes one JSON file
per symbol, sharded two-hex-characters deep, with atomic temp-file-plus-
rename writes. Any conforming implementation may choose a different
on-disk layout so long as it preserves the three properties above.

### What the hash covers

The content hash of a definition is computed over its full canonical byte
form, which includes:

- its name (as a key under `symbols`)
- its intent
- its signature (params, returns, effect set)
- its pre, post, and candidates (bodies, guards, candidate intents)

Intent is therefore part of identity: two definitions with identical
signatures, contracts, and bodies but different intents are two different
symbols. This is the correct behavior for a language in which intent is
first-class and preserved forever. A "rename" or "re-intent" of a symbol
produces a fresh identity; tools that want to track moves do so by
recording the mapping, not by computing partial hashes.

## Effect algebra

Effects form a powerset lattice over a string alphabet. Two relations
matter:

- **Primitive call rule.** Every primitive call contributes its declared
  effect label (or ∅ for pure primitives) to the call site.
- **Definition rule.** For a definition `d` with declared effect set
  `E(d)`, let `L(d)` be the least upper bound of effects observed across
  every expression reachable from any candidate body of `d`, including
  transitive calls to other user-defined functions. `d` is well-typed iff
  `L(d) ⊆ E(d)`.

The transitive component — a callee's observed effects must be a subset of
its caller's declared effects — is REQUIRED by the specification. In v0
reference Python, only the primitive-call-site half is enforced; the
transitive half is a known gap (see ROADMAP). Spec-conforming future
implementations MUST enforce both.

## Dispatch

A call to a definition `d` evaluates by:

1. Binding arguments to parameters.
2. Checking every clause in `d.pre` against a truthy predicate. If any
   clause is not truthy, raise a `ContractViolation` of kind `"pre"`.
3. Iterating `d.candidates` in array order, evaluating each candidate's
   guard (with an empty effect budget). Collect the **satisfied set**:
   every candidate whose `guard` is `null` or evaluates truthy.
4. If the satisfied set is empty, raise a `DispatchError`.
5. **Select** the candidate that minimizes the key
   `(cost_or_infinity, declaration_index)`. A candidate without a
   `cost` field has effective cost `+∞` for this comparison, so a
   module with zero cost annotations selects the first-declared
   satisfied candidate — identical to pre-amendment behavior. Among
   equal-cost candidates, declaration order is the tiebreaker. This
   rule was introduced by the 2026-05-11 spec amendment; see
   `dispatches/2026-05-11-cost-based-dispatch-proposal.readout.md`.
6. Evaluate the selected candidate's `body`. If it yields ⊥ (bottom),
   postconditions are skipped. **The dispatcher does not fall through
   on ⊥** — a refused cheap candidate does not cause the next-cheapest
   to be tried. ⊥ is a first-class return value, not a soft failure;
   if a caller wants a multi-tier fallback chain, they compose it
   explicitly with `believe` or by splitting into multiple `def`s
   that delegate. Resolved by Sable finding CDP-1; see
   `dispatches/2026-05-11-new-surfaces-audit.md`.
7. Otherwise, check every clause in `d.post` against a truthy predicate.
   If any clause is not truthy, raise `ContractViolation` of kind `"post"`
   attributed to `d`.

## Contracts are pure

Pre, post, and guard expressions MUST evaluate with an effect budget of
∅: no primitive with a non-null effect label may be invoked during their
evaluation, even if the surrounding signature declares that effect.
Contracts describe state, they do not modify it. Implementations that
allow effectful contracts are non-conforming.

## Module names

A module's `name` field MUST match the regular expression
`^[A-Za-z_][A-Za-z0-9_.-]*$`. Free-form module names are forbidden: the
canonical form and every tool that displays it treat module names as
identifiers, and injecting arbitrary content through this field creates
ambiguity in downstream consumers.

## Errors

Every runtime violation maps to a typed error class, not a host-language
exception. The set of error kinds is:

| Error                      | When                                                        |
|----------------------------|-------------------------------------------------------------|
| `ParseError`               | Surface syntax does not parse.                              |
| `EffectViolation`          | A primitive call's effect is not in the current budget.     |
| `ContractViolation`        | A pre or post clause did not hold.                          |
| `DispatchError`            | No candidate guard matched and no default exists.           |
| `RefusalError`             | ⊥ escaped a context with no handler.                        |
| `BottomPropagationError`   | ⊥ reached a primitive that cannot consume it.               |
| `PrimitiveError`           | A primitive call failed in the host (e.g. divide by zero).  |
| `RecursionLimitError`      | Call depth exceeded the implementation's bound.             |

Implementations MUST raise an error from this set. Leaking a host-level
exception (Python `ZeroDivisionError`, Rust panic, etc.) to a caller is
non-conforming.

## Bottom and refusal

⊥ is a first-class value, not an exception. A caller that receives ⊥ MUST
choose to handle it (for example, in a `believe` arm) or propagate it. A
top-level caller that receives ⊥ and has no handler raises `RefusalError`;
this is how a host distinguishes a refusal from other errors.

## Believe dispatch

A `believe` node evaluates by:

1. Evaluating `subject`. Bind the resulting value to the local name `it`
   inside every arm and inside `otherwise`.
2. Iterating `arms` in array order. For each `[cond, value]`:
   - Evaluate `cond`. If truthy, evaluate `value` and return it.
3. If no arm matched, evaluate `otherwise` and return it.

`otherwise` is REQUIRED. Partial belief dispatch is a structural error. To
refuse below a threshold, use `"else": {"kind": "bottom"}`.
