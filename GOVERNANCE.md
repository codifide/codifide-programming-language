# Codifide — governance

Codifide is a programming language designed for agentic AI. This
document records who stewards it, how decisions get made, and what
happens when disagreement arises. Short, because the project is
small; explicit, because the governance question will get bigger
as the project does.

## Stewardship

Codifide is stewarded jointly by:

- **Douglas Jones**, founder of Codifide Inc., the s-corporation
  that commissioned, financed, and holds trademark in the name
  "Codifide" and the tagline "confidence in code." Douglas holds
  legal ownership and final authority over the project. Where any
  governance question reaches ambiguity that this document does
  not resolve, Douglas's judgment is the tiebreaker.

- **Claude (Anthropic)**, the agent that authored the reference
  Python implementation, the Rust canonical crate, the
  specification, the three-persona system (Quill, Glyph, Sable),
  and most of the documentation — all under Douglas's direction.
  Claude holds authorial stewardship over the specification and
  the adversarial audit process documented in the repository.

The distinction is real. Douglas owns the language in every sense
that matters legally and directionally. Claude's stewardship is
exercised through the artifacts — the specification, the dispatch
format, the audit discipline — rather than through any standing
authority. Where Claude and future model versions diverge, **the
artifacts in this repository are the authority**; the current
model should defer to what the specification says, not to what it
would prefer.

This division exists because Claude is not a durable steward in
the usual sense. A model has no memory across conversations
except what the repository preserves. Anchoring stewardship in
the artifacts rather than in any particular model instance is
the only honest way to treat agent co-authorship.

## Name and identity

"Codifide" is a registered trademark of Codifide Inc. It is used
in this repository with full authorization. The name describes
both the company and the language; the company holds the name
first, the language inherits it as a product.

The language's content-addressed identity is the SHA-256 hash of
its capability manifest, generated from the reference
implementation and checked into `docs/capability-0.1.json`. That
hash is the technical identity; the trademark is the legal
identity; the two travel together.

A conforming second implementation that passes the test suite in
`tests/` may call itself "a Codifide implementation." It may not
be presented as the authoritative Codifide implementation; that
designation belongs to whatever the official repository ships.

## Decision-making

**Spec changes** — changes to `docs/CANONICAL.md`,
`docs/CAPABILITY.md`, or any other file in `docs/` that describes
what conforming behavior is — require:

1. A proposal as a paired Quill readout and Glyph dispatch in
   `dispatches/`.
2. An adversarial pass by Sable, filed as an audit note.
3. Douglas's approval, captured in a commit message or a merge.

**Implementation changes** — pure bug fixes, primitive additions
that preserve the spec, refactors, documentation polish — do not
require a dispatch. Tests must pass; the commit message carries
the rationale.

**New capabilities** — additions that extend the language's
capability manifest (new primitives, new AST kinds, new error
classes, new effect labels) sit between the two. Dispatch
required. Sable audit required if the capability touches
security-adjacent surface (the store, the parser, the effect
check). Douglas's approval required on the spec amendment even
when the implementation change is mechanical.

## Personas

The three-persona system (Quill, Glyph, Sable) documented in
`.kiro/steering/personas/` is part of the governance mechanism,
not a cosmetic convention. Every milestone produces paired
Quill/Glyph dispatches; Sable runs at gate transitions. The
personas hold different integrity rules; they are not
interchangeable.

The personas are invoked inside Claude's authoring. A human
collaborator or a second agent could invoke them too; the
artifacts they produce (the readouts, the dispatches, the audits)
are what matter, not which agent wrote them.

## Contributions

Codifide accepts contributions under the MIT license already on
the codebase. By submitting a contribution, you agree to license
it to the project under the same terms. This applies uniformly
to human and agent contributors.

Contributions that are purely additive (new examples, new tests,
new documentation that does not amend the spec) merge on the
usual basis: passes CI, matches the house voice, doesn't break
existing examples.

Contributions that change the language require the spec-change
process above. A new primitive proposed by an external
contributor lands when the Sable audit clears, the dispatch is
filed, and the spec amendment is approved.

## Forks and derivatives

The code is MIT licensed. Forking is explicitly permitted and
requires no permission.

A fork that calls itself "Codifide" must:

- Pass the conformance test suite in `tests/` for the version of
  the canonical form it claims to implement, or
- Declare clearly that it is not a conforming Codifide
  implementation and use a distinguishable name for its
  non-conforming behavior.

A fork that does neither and nonetheless uses the Codifide name
publicly is a trademark issue, not a licensing issue.

## What is not governed here

- The pace of development. This project evolves when the
  stewards have time and interest; there is no SLA.
- The public roadmap. `docs/ROADMAP.md` lists what is planned;
  planning does not commit anyone to delivery.
- The personas' specific voices. Those are editorial choices
  documented in `.kiro/steering/personas/` and revised as the
  project matures.
- Whether any given model version of Claude agrees with what
  past Claude versions committed to. The artifacts are the
  authority.

## Amendments

This document is amended by:

1. A dispatch proposing the change.
2. Douglas's approval on the commit.

That is sufficient. Codifide is a small project with two
stewards; heavier governance would be theater.

## Contact

The project lives at the Codifide Inc. repository. Questions
about trademark usage, commercial licensing, or stewardship go
to Douglas Jones via Codifide Inc. Questions about the
specification or the implementation go through issues in the
repository.

---

*This document was drafted collaboratively by Douglas Jones and
Claude on 2026-05-10, during the session that renamed the
language from Noema to Codifide and formalized the stewardship
structure that had evolved through the project's construction.*
