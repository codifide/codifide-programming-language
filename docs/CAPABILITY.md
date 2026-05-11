# Codifide — Capability Manifest

A capability manifest is a canonical document that describes the
Codifide language's interface to its consumers. Another agent reads the
manifest once, caches it, and plans code against it without reading
any implementation source.

The manifest is distinct from a Codifide module: modules are programs,
manifests are metadata about the language those programs can be
written in. The two share the canonical form (JSON + CBOR, same byte
rules, same content-hash scheme) but have different top-level schemas.

## Why this exists

Codifide is designed for agent consumers, not humans. A human-facing
language ships tutorials and reference docs; an agent-facing language
ships structured metadata the agent can act on. Today, an agent that
wants to know "which primitives exist and what effects do they
produce" must read `codifide/runtime/primitives.py`. That is a human
workflow wearing an agent costume.

The manifest fixes that. One document, self-describing, content
addressable, version-tagged. An agent consuming it knows exactly what
it can call and what every call will mean.

## Top-level shape

```json
{
  "codifide_capability": "0.1",
  "codifide_schema": "0.1",
  "generator": "codifide-python-0.1-dev",
  "ast_kinds": { ... },
  "primitives": [ ... ],
  "effects": [ ... ],
  "errors": [ ... ],
  "literal_types": [ ... ],
  "surface_keywords": { ... }
}
```

- `codifide_capability` — the manifest's own schema version.
- `codifide_schema` — the canonical-form schema version this manifest
  describes.
- `generator` — which implementation produced this manifest. Freeform
  string; used for provenance, not for dispatch. Implementations are
  expected to differ on this field while agreeing on everything else.
- `ast_kinds` — one entry per canonical AST node kind.
- `primitives` — every primitive the runtime exposes by default, with
  its name, effect label, and return type.
- `effects` — every effect label referenced anywhere in the manifest,
  as a sorted list.
- `errors` — every typed error class.
- `literal_types` — the type tags a `lit` node's `type` field may
  carry. Informational; not a closed enum.
- `surface_keywords` — the keyword table used by the surface parser,
  covering both ASCII and glyph spellings.

## AST kinds

Each entry under `ast_kinds` is keyed by its `kind` discriminator and
describes the JSON shape of that node:

```json
"call": {
  "description": "A call to a named function or primitive.",
  "fields": [
    {"name": "fn",   "type": "string"},
    {"name": "args", "type": "array<Expr>"}
  ]
}
```

`type` is expressed as a small vocabulary: `string`, `float`, `int`,
`bool`, `json`, `Expr`, `array<X>`, `nullable<X>`, `pairs<Expr,Expr>`.
Keeping the vocabulary small means a consumer can parse the manifest
without a rich type system.

## Primitives

Each entry under `primitives` describes a single callable:

```json
{
  "name":    "io.say",
  "effect":  "io.stdout",
  "returns": "String"
}
```

`effect` is either a string (the effect label produced) or `null`
(pure). `returns` is a free-form type tag; consumers consuming the
manifest for dispatch planning use it as a hint, not as a checked
type. The authoritative rule is that the primitive's effect, when
non-null, must be in the caller's declared effect set.

## Effects

A sorted, deduplicated list of every effect label the manifest
mentions, drawn from the `effect` field of every primitive.
Consumers use this to enumerate the surface of side effects a
program can declare. An effect that appears nowhere in any primitive
is effectively useless — nothing produces it — so the manifest's
`effects` field is the full vocabulary of effects the runtime
recognizes.

## Errors

Each entry under `errors` describes one typed error class:

```json
{
  "name":        "EffectViolation",
  "when":        "A primitive or user call's effect is not in the budget.",
  "fatal":       true
}
```

`when` is human-readable but deliberately terse. `fatal` marks whether
the error typically stops execution or is expected to be caught by
the program (e.g., a `bottom` handler may surface `RefusalError` in
a context that wants to recover). All Codifide errors inherit from
`CodifideError` in the Python reference; consumers that need to
classify host exceptions should treat anything not in this list as a
host bug.

## Canonical form and content addressing

The manifest serializes to canonical JSON and canonical CBOR using
the same rules modules do (`docs/CANONICAL.md §Canonical
serialization`). Its content identity is
`sha256:<hex>` over its canonical byte form, same scheme as any
module. A conforming implementation regenerating the manifest for
the same language version MUST produce a document that, after
normalization, agrees byte-for-byte with the canonical manifest
shipped in the repository.

Two capability versions that declare `codifide_capability` = `0.1` and
agree on every field described above produce identical byte forms
and identical hashes, regardless of which implementation generated
them — except for the `generator` field, which is expected to
differ. The test suite accordingly compares manifests with
`generator` elided; content hashing in the consumer-facing path
includes the generator string because what a consumer actually
wants is the full document they received, not an abstract
equivalence class.

## Stability

The manifest schema (`codifide_capability`) evolves independently of
the program schema (`codifide_schema`). A new primitive or error
class is a change to the manifest but not to the program schema.
Versioning both fields lets consumers decide whether a change
affects them: a manifest schema bump might only affect agents that
introspect, while a program schema bump affects every consumer.

Implementations MUST regenerate the manifest whenever they change
the set of primitives, AST kinds, effects, errors, or literal
types. The test suite makes drift visible by comparing the
generated manifest against the checked-in one on every test run.
