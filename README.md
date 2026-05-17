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

Codifide is a **contract-and-dispatch language**, not a systems language or a
general-purpose computation language. It optimizes for declaring intent and
contracts, dispatching among candidates, enforcing effects, and
content-addressing compositions — the properties that matter for
agent-to-agent trust.

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

The language is small. v4.0 shipped on 2026-05-14. The
properties it pins down are the ones that matter before scale, not after.

## What's in v4.0

- Canonical JSON and CBOR forms for the hypergraph, with a deterministic canonical byte
  form and SHA-256 content hash. CBOR is the primary hash format.
- Surface parser (ASCII keywords with optional unicode glyphs), with multi-line expression
  continuation and fuzz-hardened against malformed input.
- Tree-walking interpreter with:
  - Transitive effect-subset check across the call graph.
  - Pre- and postcondition enforcement, evaluated with an empty effect budget.
  - Multi-candidate dispatch with declaration-order guards.
  - Cost-based candidate selection — `min(cost, declaration_index)` among satisfied candidates.
  - Belief dispatch on runtime confidence.
  - Inline conditional expression (`if ... then ... else`) with short-circuit evaluation.
  - First-class refusal (`bottom` / `⊥`) with optional reason string and explicit propagation.
  - Runtime type enforcement — `sig` declarations checked at every call boundary.
  - Ten typed error kinds; host exceptions do not leak.
  - Configurable call-depth bound with a typed `RecursionLimitError`.
- Standard library: file I/O (`io.read`, `io.write`, `io.exists`), HTTP client
  (`http.get`, `http.post`), JSON (`json.parse`, `json.encode`), date arithmetic
  (`clock.today`, `clock.parse`, `clock.add_days`, `clock.format`).
- Indexed primitives: `slice`, `at`, `char_at`, `indexof`.
- Content-addressed symbol store with Git-style sharded loose objects, atomic
  writes, hash-verified reads, idempotent writes, and garbage collection via declared roots.
- Content-addressed imports (`import foo = sha256:...`) and index modules with
  `from <identity> import name1, name2` resolved at parse time.
- **Public registry** at `https://codifide.com/symbols/<hash>` — publish symbols,
  resolve them from any machine. Browse at `https://codifide.com/registry`.
- Rust interpreter and Rust parser with byte-level conformance to the Python reference.
- Parallel evaluator with full import support.
- Remote symbol resolution (`--registry` flag, `store push` command).
- Three-persona system: Quill (human readouts), Glyph (agent dispatches),
  Sable (adversarial audits).
- 450 Python tests passing, 28 Rust canonical tests passing, 0 skipped.

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
pip install codifide
python3 -m codifide run examples/greet.cod
python3 -m codifide run examples/sort.cod
python3 -m codifide run examples/classify.cod
python3 -m codifide test
```

Or clone and run from source:

```bash
git clone https://github.com/codifide/codifide-programming-language
cd codifide-programming-language
pip install -e .
python3 -m codifide agent-quickstart
```

See `GETTING_STARTED.md` for a walk-through that stores a symbol, mints an
index, and consumes it from a second module.

## Public registry

The canonical pipeline symbols are published at `https://codifide.com/registry`.
Any agent can resolve them by hash:

```bash
# Import from the public registry in your .cod file
import classify_content = sha256:377099c5bddb8cebe9e8bc6b8499bb00ea99083798d1b064799ac82c55636fae

# Run with registry resolution
python3 -m codifide run my_program.cod --registry https://codifide.com
```

Publish your own symbols:

```bash
python3 -m codifide store put my_module.cod
python3 -m codifide store push sha256:<hash> --registry https://codifide.com
```

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
