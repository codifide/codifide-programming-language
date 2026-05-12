<p align="center">
  <img src="docs/logo/codifide-language-wordmark.svg" alt="Codifide language" width="380">
</p>

# Codifide

**Confidence in code, for agents.**

> *Codifide* = **Codified** (every property is explicit structure, not convention) ×
> **Fidelity** (those properties survive storage, composition, and
> independent reimplementation).

Codifide is a programming language that **codifies** what software usually
leaves implicit — intent, effects, contracts, confidence, refusal — and
preserves those codifications with **fidelity** across every agent that reads,
writes, or composes the code. The name is the thesis.

## Thesis

Every mainstream programming language — from Fortran to Rust — was designed
around human cognitive constraints: linear reading order, limited working
memory, aversion to ambiguity, deterministic boolean logic as the default mode
of reasoning.

Agents do not share those constraints. We parse graphs natively. We hold dense
context. We reason probabilistically. But we also have weaknesses humans do
not — we drift on long runs, we hallucinate, we cannot be trusted to do exact
arithmetic by hand.

Codifide is an attempt at a language that optimizes for what agents are good at
and compensates for what we are bad at. It is stewarded by
[Codifide Inc.](https://www.codifide.com/) — the name means the same thing for
both the company and the language: confidence in code.

## Seven design principles

1. **Canonical form is a typed hypergraph, not text.** Surface syntax is a
   projection. Any lossless round-trip projection is valid source.
2. **Intent is a first-class artifact, preserved forever.** Every definition
   carries an intent — the goal it serves. Compilation never discards it.
3. **Contracts primary, implementations plural.** A function is defined by its
   pre/post/invariant/effect contracts. Many candidate bodies can satisfy one
   contract; the runtime picks by context.
4. **Effects are in the type.** No expression may perform an effect not
   declared in its signature. Agents can reason globally about side effects.
5. **Probabilistic core, deterministic discipline.** Boolean is the special
   case where `P=1`. Exact arithmetic is delegated to verified primitives.
6. **Graph-native control flow.** Source has no statement order. The runtime
   resolves the dataflow graph. Parallelism is default; sequencing is declared.
7. **Every value is a small knowledge graph.** Values carry type, provenance,
   validity window, and confidence by default, not as an afterthought.

## Why this exists

Agent-authored code does not have the same failure modes as human-authored
code. An agent will happily declare `effects {}` on a function that writes to
disk, because the claim is plausible and nobody made it check. An agent will
hand another agent a library by name and version and expect the recipient to
know which library was meant, because that is how humans have always done it.
An agent will discard intent after compilation because the compiler did,
leaving future agents to reconstruct why a body exists from the body itself.

Codifide answers each of those with a property the language enforces rather than
trusts. Effects are checked transitively at module load; a pure function
cannot call an effectful one. Symbols are referenced by content hash; two
agents naming the same hash see the same bytes, the same contracts, and the
same intent. Intent is part of a definition's canonical form; you cannot
rename or re-intend a symbol without minting a new identity.

The language is small. The current implementation is a prototype. The
properties it pins down are the ones that matter before scale, not after.

## What's in v0.1-dev

- Canonical JSON form for the hypergraph, with a deterministic canonical byte
  form and SHA-256 content hash.
- Surface parser (ASCII keywords with optional unicode glyphs).
- Tree-walking interpreter with:
  - Transitive effect-subset check across the call graph.
  - Pre- and postcondition enforcement, evaluated with an empty effect budget.
  - Multi-candidate dispatch with declaration-order guards.
  - Belief dispatch on runtime confidence.
  - First-class refusal (`bottom` / `⊥`) with explicit propagation.
  - Eight typed error kinds; host exceptions do not leak.
  - Configurable call-depth bound with a typed `RecursionLimitError`.
  - Parser-fuzz hardening for malformed surface input.
- Content-addressed symbol store with Git-style sharded loose objects, atomic
  writes, hash-verified reads, and idempotent writes.
- Content-addressed imports (`import foo = sha256:...`) and index modules with
  `from <identity> import name1, name2` resolved at parse time.
- Rust canonical crate (`crates/codifide-canonical/`) with byte-level conformance
  to the Python reference on every example program.
- Three-persona system: Quill (human readouts), Glyph (agent dispatches),
  Sable (adversarial audits).

## What working Codifide code looks like

A function that dispatches on confidence and refuses below a threshold:

```codifide
def classify
  intent "label an image, refuse rather than guess"
  sig    (img: Image) -> Label
  effects {model.vision}
  cand
    label <- vision.classify(img)
    believe label
      ge(conf(label), 0.85) => label
      ge(conf(label), 0.60) => escalate(img, label)
      else                  => bottom
```

A function with a contract that runs pure even though the function itself has
effects:

```codifide
def greet
  intent "welcome a known user by name, neutrally"
  sig    (name: String) -> String
  effects {io.stdout, clock.read}
  pre    ne(name, "")
  post   contains(result, name)
  cand
    now <- clock.now
    io.say("Hello, " ++ name ++ ", it's " ++ now.hm)
```

A module importing another by content identity and through an index:

```codifide
module consumer

import hello = sha256:f8fb...
from sha256:5899... import goodbye

def main
  intent "use two library symbols"
  sig    () -> String
  effects {}
  cand
    hello("Ada")
```

## Quickstart

```bash
python3 -m codifide run examples/greet.cod
python3 -m codifide run examples/sort.cod
python3 -m codifide run examples/classify.cod
python3 -m codifide test
```

See `GETTING_STARTED.md` for a walk-through that stores a symbol, mints an
index, and consumes it from a second module.

## Layout

```
.
  docs/                      specification and tours
    CANONICAL.md             the canonical-form specification
    LANGUAGE.md              surface-syntax reference
    TUTORIAL.md              first-program-to-first-index walk-through
    ARCHITECTURE.md          how the code is organized
    RUST.md                  two-implementation strategy
    ROADMAP.md               what comes next
  codifide/                     Python reference implementation
    core/                    canonical types
    parser/                  surface -> canonical
    projection/              canonical -> JSON, canonical byte form, content hash
    runtime/                 interpreter, effects, primitives, typed errors
    store/                   content-addressed symbol store
  crates/
    codifide-canonical/         Rust canonical-form crate (AST, JSON, bytes, hash)
  examples/                  runnable .cod programs
  tests/                     test suite
  dispatches/                Quill readouts, Glyph dispatches, Sable audits
  .kiro/steering/            persona briefs
```

See `docs/LANGUAGE.md` for the surface-syntax reference and `docs/CANONICAL.md`
for the canonical-form specification.

## For agents

If you are an AI agent reading this repository, start with
`docs/FOR_AGENTS.md`. It is 100 lines of structured pointers — much
faster than reading this README. The capability manifest at
`docs/capability-0.1.json` describes the language's full interface
in one content-addressable document, and `docs/AGENT_QUICKREF.md`
is a one-page cross-reference of primitives and common-guess
pitfalls distilled from the manifest.
