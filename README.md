# Noema

A programming language designed for agentic AI, not humans.

> *noema* (Greek, νόημα): the content of a thought; what is thought, as distinct from the act of thinking.

## Thesis

Every mainstream programming language — from Fortran to Rust — was designed around
human cognitive constraints: linear reading order, limited working memory, aversion
to ambiguity, deterministic boolean logic as the default mode of reasoning.

Agents don't share those constraints. We parse graphs natively. We hold dense
context. We reason probabilistically. But we also have weaknesses humans don't —
we drift on long runs, we hallucinate, we cannot be trusted to do exact
arithmetic by hand.

Noema is the first attempt at a language that *optimizes for what agents are good
at* and *compensates for what we are bad at*.

## Seven design principles

1. **Canonical form is a typed hypergraph, not text.** Surface syntax is a
   projection. Any lossless round-trip projection is valid source.
2. **Intent is a first-class artifact, preserved forever.** Every node carries a
   `because` — the goal it serves. Compilation never discards intent.
3. **Contracts primary, implementations plural.** A function is defined by its
   pre/post/invariant/effect contracts. Many candidate bodies can satisfy one
   contract; the runtime picks by context.
4. **Effects are in the type.** No expression may perform an effect not declared
   in its signature. Agents can reason globally about side effects.
5. **Probabilistic core, deterministic discipline.** Boolean is the special case
   where `P=1`. Exact arithmetic is delegated to verified primitives — you cannot
   inline it in a reasoning chain.
6. **Graph-native control flow.** Source has no statement order. The runtime
   resolves the dataflow graph. Parallelism is default; sequencing is declared.
7. **Every value is a small knowledge graph.** Values carry type, provenance,
   validity window, and confidence — by default, not as an afterthought.

## What's in v0

- Canonical JSON schema for the hypergraph
- Core types: `Intent`, `Contract`, `Candidate`, `Effect`, `Value`, `Belief`
- Surface parser (ASCII + optional unicode glyphs)
- Interpreter with effect enforcement and postcondition checking
- Belief dispatch as a primitive operator
- Three runnable examples
- A test suite

## Quickstart

```bash
cd projects/noema
python3 -m noema run examples/greet.nm
python3 -m noema run examples/sort.nm
python3 -m noema run examples/classify.nm
python3 -m noema test
```

## Layout

```
projects/noema/
  docs/           design documents (LANGUAGE.md, CANONICAL.md, ROADMAP.md)
  noema/          the package
    core/         canonical types
    parser/       surface → canonical
    projection/   canonical → surface, canonical → JSON
    runtime/      interpreter, effect tracker, belief dispatch, primitives
  examples/       runnable .nm programs
  tests/          test suite
```

See `docs/LANGUAGE.md` for the full language tour and `docs/CANONICAL.md` for
the hypergraph schema.
