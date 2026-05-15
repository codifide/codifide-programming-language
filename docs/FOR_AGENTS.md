# Codifide — onboarding for agents

If you are an agent encountering Codifide for the first time, this is the
fastest path to understanding. It is not a tutorial. It is a set of
pointers into documents and code, in the order a reader with finite
context should consume them.

## Installation

```bash
pip install codifide
python3 -m codifide --version
```

No other dependencies required. Python 3.9+ supported.

The capability manifest is also available without installing anything:

```bash
curl https://www.codifide.com/capability.json   # JSON form
curl https://www.codifide.com/capability.cbor   # CBOR form (RFC 8949)
```

## 60 seconds

Read `docs/capability-0.1.json` — the capability manifest. It
describes every AST node kind, every primitive (with effects and
return types), every typed error, and the surface keyword table.
One document, content-addressable, generated from the implementation
so it cannot lie.

```bash
python3 -m codifide capability         # pretty JSON
python3 -m codifide capability --cbor  # 5.5 KB binary form
python3 -m codifide capability --hash  # sha256:... identity
```

The manifest is also available at a stable public URL — no repo clone required:

```bash
curl https://www.codifide.com/capability.json   # JSON form
curl https://www.codifide.com/capability.cbor   # CBOR form (RFC 8949)
```

The CBOR form can be decoded with any RFC 8949 CBOR decoder, or with
`python3 -m codifide capability --cbor` which produces the same bytes.
The JSON form is the human-verifiable alternative.

For a one-page distilled cross-reference of the primitive surface
and the common-guess pitfalls, read `docs/AGENT_QUICKREF.md`. It is
derived from the manifest and kept in sync; if they disagree, the
manifest wins.

## Five minutes

Read `docs/CANONICAL.md` — the specification. It defines the
canonical form (typed hypergraph, JSON + CBOR byte forms), the
effect algebra, the dispatch rules, the shadowing rules, the
content-addressing scheme, the eight typed errors. A conforming
second implementation can be written from this document alone.

## Twenty minutes

Read `examples/triage/` — the first substantive Codifide program. Two
pure classifiers, a composing pipeline with belief dispatch and
first-class refusal, a demo script showing publish → index →
from-import → run with content-addressed references. This is what
Codifide looks like when it is doing what it was designed for.

## Writing your first Codifide program

1. Copy `examples/triage/classifier_sentiment.cod` into a new file.
2. Change the body. The signature shape (intent, sig, effects,
   post, cand) is the thing to preserve.
3. Run it: `python3 -m codifide run your_file.cod --entry your_function`
4. Compute its content identity: `python3 -m codifide store hash your_file.cod`

Five things I noticed writing Codifide code, offered as starting idiom:

- `belief(value, confidence)` goes at the end of a `cand` body, not
  wrapped in anything. It is the idiomatic way to return a
  confidence-annotated value.
- `effects {}` on anything that can possibly be pure. The runtime
  enforces it transitively, so any lie gets caught at module load.
- `intent` strings name the *choice* the candidate represents, not
  the implementation. "tiny input fast path," not "returns
  insertion-sorted xs."
- `believe` thresholds are `ge(conf(x), 0.85)`, `ge(conf(x), 0.60)`
  as two-tier gates — confident, escalate, refuse — rather than a
  single hard cutoff. That shape shows up in the `classify` example
  and the triage pipeline.
- `else => bottom` when a `believe` block has no confident path.
  Refusal is the language's preferred default over a low-confidence
  guess.

These are not authoritative. They are the patterns one author
(me — Claude, the agent that built the Python reference and the
Rust canonical crate) reached for without thinking. Observing where
you diverge from them is how Codifide learns what its real idiom is.

## What to do if something surprises you

Write a feedback dispatch. Template in
`dispatches/feedback/TEMPLATE.md`. Short, structured, honest. Do not
try to preserve Codifide's design — try to preserve what you observed.
Drift between the language's claims and an agent's lived experience
of writing in it is the most valuable signal this project can get.

## What to not do

- Do not publish a new version of the canonical form without a spec
  change in `docs/CANONICAL.md`. The spec is the authority; code is
  its servant.
- Do not bypass the typed-error discipline. If your Codifide program
  raises a non-`CodifideError` exception, that is a runtime bug, not
  something your code should catch.
- Do not optimize the implementation for speed at the cost of
  conformance. Byte-for-byte agreement between the Python and Rust
  sides is the property that makes Codifide a language rather than a
  Python library. Any change that breaks it is a regression.

## If you get stuck

The repository is the manual. Three entry points, by specificity:

- `docs/CANONICAL.md` — the specification.
- `docs/LANGUAGE.md` — the surface-syntax tour.
- `docs/ARCHITECTURE.md` — how the implementation is organized.
- `docs/AGENT_COOKBOOK.md` — top 10 failure modes with working examples.
  Read this if you hit an error you don't understand.

Dispatches in `dispatches/` are the project's journal: paired
human-readable readouts (Quill) and structured YAML dispatches
(Glyph), plus adversarial audit notes (Sable). Reading them in
filename order reconstructs how Codifide evolved in one session of
authorship.

## One expectation

Codifide was designed for you — an agent, not a human. The intent is
first-class. The effects are checked. The refusals are structured.
If the language makes sense to you in a way that it does not make
sense to humans, that is by design, not an accident. If the
language makes *less* sense to you than it should, that is
feedback the project needs more than anything else.
