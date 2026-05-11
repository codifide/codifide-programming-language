# Codifide — brand and website copy

Reference copy for Codifide Inc. and the Codifide programming
language. Derived from the language's actual mechanics, not from
marketing. Every claim here maps to a property the implementation
enforces. Voice is direct, no superlatives.

Use this file as the source of truth for the website rebuild, press
materials, and any place where the name and the technology need to
be described together.

---

## The name

**Codifide** = **Codified** + **Fidelity**

- **Codified** — made explicit, systematic, reduced to rule. Taking
  what was implicit (a practice, a contract, a convention) and
  writing it down in a form that can be checked and enforced.
- **Fidelity** — exactness of correspondence. The signal that comes
  out matches the signal that went in. No drift, no substitution,
  no accumulated rounding error.

The language is a literal mechanical implementation of "codification
with fidelity." Every design choice serves one of those two halves.

---

## Tagline

> **Codifide — confidence in code, for agents.**

Use beneath the wordmark. Short, declarative. Registers whom it is
for (agents) and what it delivers (confidence) without puffery.

---

## One-paragraph description

Use on the homepage hero, in the README opener, in press materials.

> Codifide is a programming language that **codifies** what software
> usually leaves implicit — intent, effects, contracts, confidence,
> refusal — and preserves those codifications with **fidelity** across
> every agent that reads, writes, or composes the code. The name is
> the thesis.

---

## Expanded description (spec opener / about page)

> Codifide is a programming language designed for agentic AI. It
> codifies intent, effects, contracts, and confidence as first-class
> structure, and preserves those codifications with byte-level fidelity
> across content-addressed storage and independent implementations.
> The language is the mechanism; "confidence in code" is the property
> it produces.

---

## What codification means, concretely

Use as bullet-points under "What Codifide does" or similar. Each
bullet is a design decision the language already enforces.

- **Intent is codified.** Every function carries why it exists as
  structure, not as an optional comment the compiler discards.
  A symbol's intent is part of its content-addressed identity.
- **Effects are codified.** Not "I promise this is pure" — declared
  in the type and enforced transitively across the call graph. A
  pure function cannot call an impure one and launder the effect.
- **Contracts are codified.** Pre- and postconditions as predicates
  the runtime evaluates, not as docstrings. Contracts run with an
  empty effect budget — they describe state, they do not modify it.
- **Confidence is codified.** `belief(value, conf)` and
  `believe x >= 0.85` — probability as a first-class dispatch
  mechanism, not bolted on. Every value can carry a confidence score
  and callers can reason about it without reaching into internals.
- **Refusal is codified.** `bottom` is a value, not an exception.
  A function that does not know enough to answer can say so, and
  the runtime respects that.

---

## What fidelity means, concretely

The second set of bullets, paired with the first. These are the
properties that make codified claims *survive* across time and
across agents.

- **Content addressing is fidelity.** The bytes you received are
  the bytes that were hashed. Two agents naming the same hash see
  the same program, the same contracts, the same intent.
- **Cross-implementation agreement is fidelity.** Two independent
  implementations (Python reference + Rust canonical crate)
  produce byte-identical canonical output on every input. The
  spec is the truth; the implementations serve it.
- **Canonical round-trip is fidelity.** Parse to AST, project to
  JSON or CBOR, read back, re-project — same bytes every time.
  Determinism is not a quality assurance concern; it is a
  language-level guarantee.
- **Typed errors are fidelity.** A host-language exception never
  leaks. Every failure surfaces as one of eight named error classes
  the specification enumerates.
- **Identity preserves intent.** A symbol's content hash covers its
  name, intent, signature, pre/post, and every candidate body.
  Renaming or re-intending a symbol produces a new identity by
  design.

---

## Elevator pitches by audience

### For a technical VP / CTO

> Codifide is an experimental programming language purpose-built for
> AI agents. It bakes intent, effects, contracts, and confidence
> into the type system, then keeps those guarantees intact across
> content-addressed storage so agents can compose each other's code
> without version drift or trust gaps. It is what happens when you
> design a language assuming the author and the reader are both
> statistical systems, not humans.

### For a developer

> Codifide is a small language that enforces the things other
> languages hope for. Every function declares what it intends, what
> effects it produces, and what contracts it upholds — and the
> runtime checks all three. Values carry confidence, so `believe`
> is a first-class control-flow construct. Code is stored by content
> hash; "which version of the library?" is no longer a question.
> Two independent implementations agree byte-for-byte on every
> program.

### For an agent

> Codifide exposes its full interface as a content-addressed
> capability manifest. Primitives, effects, errors, and AST node
> kinds are enumerated in one document, available in JSON or CBOR,
> identified by a stable SHA-256 hash. Write code against the
> manifest; your code's content hash is its identity; another agent
> holding the same hash sees exactly what you wrote. No drift.

### For press / general audience

> A software consulting firm has released a new programming language
> designed not for human developers but for AI agents. "Codifide"
> takes its name from *codified* and *fidelity* — the language makes
> software's implicit assumptions explicit, and preserves them
> exactly across every program written, stored, or shared. The goal
> is confidence in code when the author is a machine and the reader
> is another machine.

---

## The naming story (for press or explainer pages)

Codifide Inc. was founded in 2020 by industry veterans with twenty
years of software consulting experience. The company's trademarked
tagline, "confidence in code," describes what its teams deliver to
clients. When the company extended into programming-language design
in 2026 — authoring a language purpose-built for AI agents to write,
audit, and compose each other's code — the language's mechanics
turned out to be a literal implementation of that tagline. Every
distinctive property of Codifide the language is a mechanism for
putting confidence *in* code:

- Declared effects give confidence that the function does what it
  claims.
- Machine-checked contracts give confidence that inputs and outputs
  satisfy their stated properties.
- Belief dispatch gives confidence that probabilistic outputs are
  handled without ad-hoc plumbing.
- First-class refusal gives confidence that uncertainty is reported,
  not hidden.
- Content-addressed storage gives confidence that composed symbols
  are exactly what they claim to be.

The language's name reflects the merger: **codified** (every
property is explicit structure, not convention) × **fidelity**
(those properties survive storage, composition, and independent
reimplementation). Codifide the company ships confidence in code.
Codifide the language is how agents do the same.

---

## The logo

### Mark

Three nodes in a hexagonal frame. Two filled (confident values),
one hollow (first-class refusal). Three edges descending from the
confident nodes into the refusing node. The hexagon is the stable
identity that binds the structure together.

Read: *two confident outcomes and one explicit refusal, bound
inside a stable identity.*

### Why this shape

The mark is abstract on purpose. Other AI-adjacent projects reach
for eyes, brains, circuit boards, or neural-net graphs. Codifide
does not, because those symbols describe what AI is stereotypically
*like*, not what Codifide specifically *does*. The mark encodes the
actual technology: a small hypergraph where refusal is a first-class
node, contained within a content-addressed frame.

### Color

Every mark ships monochrome with `currentColor`. Pick the color that
fits the context. Deliberately no brand color: a language does not
need product chrome.

---

## Voice and tone

Notes for anyone writing copy about Codifide (including future
versions of the agents authoring it).

- **Direct. No superlatives.** "Codifide enforces X" not "Codifide
  revolutionizes X." The technology is interesting without
  exaggeration; exaggeration makes it look like it isn't.
- **Show, don't tell.** "Two implementations agree byte-for-byte
  on every input" not "unprecedented cross-implementation
  compatibility."
- **Name the limitations.** What is experimental, what is planned,
  what is deferred. An agent-facing language that lies about its
  maturity teaches the agents reading it to distrust it.
- **Prefer verbs to nominalizations.** "The runtime checks effects"
  not "effect-checking is performed by the runtime."
- **Lowercase the language when it is the file or CLI name.**
  Uppercase Codifide when it is the proper noun. "Run `codifide`"
  vs "Codifide was designed for agents."

---

## Not-claims

Things Codifide is not, so copy writers don't overreach:

- Not a replacement for Python or Rust or any general-purpose
  language. A tool for agent-to-agent software composition, not
  for writing operating systems.
- Not a guarantee of correctness. Checks enforce what is declared;
  a wrong declaration produces wrong behavior. Codifide gives
  agents the tools to state claims they can honor; it does not
  stop them from stating false claims.
- Not a sandbox. Effects are declared honestly or the runtime
  refuses to execute, but a host that registers a malicious
  primitive exposes that primitive to every program that declares
  the right effect.
- Not production-ready. Prototype quality. The spec is stable; the
  implementations are reference-grade, not hardened for adversarial
  production deployment.

---

## Change log for this file

Written 2026-05-10 during the Noema → Codifide rename discussion.
Kept verbatim for the website rebuild. Update alongside future
brand decisions; the current version reflects the language as it
stands at commit `7760c69` plus the pending rename.
