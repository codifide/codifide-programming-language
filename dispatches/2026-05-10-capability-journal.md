# Session journal — capability manifest

*Working notes, written as I go. Not a Quill readout, not a Glyph
dispatch — this is the live journal so the decisions are recoverable.*

## Goal

Make Noema the kind of language another agent can build in without
reading Python. The highest-leverage move I named is a **capability
manifest**: a single canonical document that describes the language's
interface — every primitive, every AST kind, every error, every effect
label. An agent reads it once, caches it, and plans code without
reverse-engineering the implementation.

## Design decisions I'm making up front

**The manifest is its own document schema.** Not a Noema module. A
module is a program; a manifest is metadata about the language. Giving
them distinct top-level schemas (`noema.capability/0.1` vs
`noema/0.1`) keeps the two kinds of document honestly separate.

**Generated, not hand-authored.** If the manifest and the implementation
disagree, the manifest is always the bug. So the manifest must be
derived from the implementation — introspecting the primitive registry,
the AST node classes, the error hierarchy, the spec's effect labels.
Tests assert that what the implementation exposes equals what the
manifest describes. Drift is impossible by construction.

**Dual canonical forms from day one.** JSON and CBOR, same as modules.
The canonical byte form has a content hash; the hash becomes the
manifest's identity. A different language version produces a different
hash, which an agent can check in one call.

**Checked in as a build artifact.** Agents read `docs/capability-0.1.json`
directly from the repo. `noema capability` regenerates it on demand.
CI (if we had CI) would verify the checked-in file matches what would
be generated today.

**Not describing every internal type.** The canonical AST kinds, yes.
The internal `Value`/`Belief` runtime wrappers, no — those are
implementation detail a different implementation wouldn't have. The
manifest describes the *interface*, not the Python classes.

## What I will not do in this turn

- Conformance corpus as data (separate piece of work; manifest first).
- Direct-from-AST agent entry-point docs (mostly already covered in
  canonical spec + architecture doc).
- CLI introspection beyond the one subcommand.
- Machine-readable tutorial (speculative; no evidence an agent needs it).

## Steps

1. Spec `docs/CAPABILITY.md` describing the manifest schema.
2. Implement `noema/capability.py` with `generate_capability()`.
3. Add `noema capability` CLI subcommand with JSON/CBOR output.
4. Commit generated `docs/capability-0.1.json`.
5. Test: manifest agrees with implementation (no drift). Manifest
   round-trips canonical form. Manifest bytes are stable.
6. Update CHANGELOG and roadmap.
7. Paired Quill/Glyph dispatch.

Writing now.


## Spec written

`docs/CAPABILITY.md` is in. One decision surfaced while writing:

- The `generator` field differs by implementation, but the content
  hash of the manifest includes it. That means two implementations
  generate manifests with different hashes even when they describe
  the same language. Is that right?

  Thinking about it: yes. An agent consuming manifest X wants to
  know *which X* it got. "The Python reference's manifest for v0.1"
  and "the Rust reference's manifest for v0.1" are different
  artifacts; they describe the same language but through different
  lenses (different doc-strings, potentially). For equivalence
  testing we strip `generator`. For provenance, we keep it.

- The `literal_types` field is informational and not a closed enum.
  Noema's `lit.type` is a free-form string in the canonical form
  (so user code can annotate a literal as `"Image"` or `"User"`
  without the language needing to know about those types). The
  manifest can't authoritatively enumerate them, only hint.

Now implementing.


## Implementation landed

`noema/capability.py` generates the manifest from:

- The primitive registry (`build_default_registry`) — full introspection.
- The typed-error class hierarchy (`noema.runtime.errors`).
- The surface keyword/operator tables (`noema.parser.tokens`).
- Hand-curated AST kind descriptions (because canonical shape is the
  authority, not Python dataclass shape).

The CLI gained `noema capability`, `noema capability --cbor`, and
`noema capability --hash`. Checked in the generated JSON at
`docs/capability-0.1.json`. A drift test asserts checked-in ≡
regenerated (modulo `generator`).

## One decision I did not make but should name

**Rust manifest.** The Rust crate only implements canonical form,
not the interpreter. Its manifest would be a thin subset:
`ast_kinds`, canonical version, maybe literal types. Three options:

1. Rust crate also emits a manifest. Consumers get one per
   implementation they use.
2. Rust crate never emits a manifest; Python manifest is
   authoritative. Rust side is described by omission (it implements
   canonical form, which is specified elsewhere).
3. Both implementations emit manifests, but the Rust one has a
   different top-level schema tag (e.g. `noema_canonical/0.1`)
   because it describes a subset capability.

Option 2 for now. Option 3 is the right long-term shape once there's
a Rust interpreter. Not doing Option 1 because a redundant manifest
is worse than no manifest — it creates two sources of truth for the
same information.

## Test results

122/122 passing. 12 new tests covering manifest generation, drift
between implementation and manifest, cross-CBOR/JSON stability,
error-class completeness, primitive-list completeness, surface-
keyword agreement.

## The real question underneath this work

The manifest changes what Noema feels like from an agent's
perspective. Before: "read the Python source to know what's
available." After: "read one JSON document, indexed by a stable
hash, describing the language's full interface."

That is closer to what the README claims Noema is for. Not all the
way there — the manifest tells you what exists; it doesn't yet tell
you what's idiomatic, what composes with what, what an agent should
reach for first. Those are meta-questions the capability manifest
can't answer. They'll need a different artifact, and I don't know
yet what shape that artifact should take.

Filing the paired dispatch next.
