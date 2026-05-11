# Codifide — Language Tour

This is the v0 language. Expect it to change. The canonical form is stable
before the surface syntax is. Where this document and `docs/CANONICAL.md`
disagree, the canonical-form specification is the truth.

## Surface syntax

Codifide source is a projection of a hypergraph. v0 supports one projection: an
ASCII-compatible line-oriented form where every keyword has an optional
unicode glyph. The unicode form is canonical for display; the ASCII form
exists so humans can type it on a US keyboard while we bootstrap.

| ASCII     | Unicode | Meaning                                    |
|-----------|---------|--------------------------------------------|
| `def`     | `≡`     | definition                                 |
| `intent`  | `⟡`     | intent annotation (required)               |
| `sig`     | `σ`     | signature                                  |
| `effects` | `⚡`     | effect set                                 |
| `pre`     | `⊢`     | precondition                               |
| `post`    | `⊣`     | postcondition                              |
| `cand`    | `ƒ`     | candidate body                             |
| `when`    | `¿`     | candidate guard                            |
| `believe` | `⊨`     | belief dispatch                            |
| `=>`      | `⇒`     | dispatch arm                               |
| `<-`      | `←`     | bind                                       |
| `++`      | `⊕`     | concat                                     |
| `bottom`  | `⊥`     | refuse / abstain                           |

Top-level keywords `module`, `import`, and `from` do not have glyph forms.
They are not part of expressions; they shape the module header.

The parser accepts either form and emits the canonical form on projection.

## A first program

```codifide
module greet_example

def greet
  intent "welcome a known user by name, neutrally"
  sig    (name: String) -> String
  effects {io.stdout, clock.read}
  pre    ne(name, "")
  post   contains(result, name)
  cand
    now <- clock.now
    io.say("Hello, " ++ name ++ ", it's " ++ now.hm)

def main
  intent "entry point"
  sig    () -> String
  effects {io.stdout, clock.read}
  cand
    greet("Ada")
```

Every definition must declare an intent. The parser rejects definitions
without one. This is on purpose. Intent is the signal agents need most and
the one compilers historically throw away.

## Effects

Effects are declared as a set. The interpreter checks two rules:

1. **Primitive-call rule.** Every primitive call's effect label must be in
   the enclosing definition's declared effect set, or the program is rejected
   before it runs.
2. **Transitive rule.** For every definition `d` and every user-function call
   in any of `d`'s candidate bodies, guards, pre, or post, the callee's
   declared effects must be a subset of `d`'s declared effects. A pure
   function cannot call an effectful one and launder the effect through.

The transitive check runs as a static pass at module load. Violations report
against the caller, which promised something it cannot deliver on without
the callee's effect budget. An imported symbol participates in the same
check; its effect set is part of its content identity and cannot be
substituted without changing the hash.

Effects you will see in v0:

- `io.stdout` — writing to standard output
- `clock.read` — reading the wall clock
- `model.vision` — vision-model inference

A function with `effects {}` is pure in the strict sense. Any attempt to call
a primitive with an undeclared effect is a static error.

## Contracts

Preconditions must hold on entry. Postconditions must hold on exit. Failure
at either end is a `ContractViolation`, not an exception — it is reported
against the function that promised, not the caller.

Postconditions may reference `result` (the return value). Postconditions are
skipped when the candidate returns `bottom`, because a function that chose
to abstain does not have to deliver on downstream guarantees.

**Contracts run pure.** Pre, post, and guard expressions evaluate with an
effect budget of ∅ regardless of the surrounding signature. A postcondition
cannot call `io.say` even if the function itself is allowed to. Contracts
describe state, they do not modify it.

## Multiple candidate bodies

```codifide
def sort
  intent "order a list ascending"
  sig    (xs: List) -> List
  effects {}
  post   is_sorted(result)
  post   is_permutation(result, xs)

  cand
    intent "tiny input fast path"
    when   lt(len(xs), 3)
    insertion(xs)

  cand
    intent "default"
    insertion(xs)
```

The runtime evaluates candidate guards in declaration order and picks the
first that holds. Contract checking is identical for every candidate — they
all answer to the same post. Guards run with the same empty effect budget
as pre and post.

## Belief dispatch

Values carry confidence. `believe` dispatches on it without the caller
having to know the internals:

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

`bottom` is first-class. It means the function chose to abstain. Callers
must handle it explicitly; it is not an exception. The `else => ...` arm is
required. Partial belief dispatch is a structural error; to refuse below a
threshold, write `else => bottom`.

## Imports and indices

A module can reference symbols stored elsewhere by content identity. Two
surface forms exist.

### Direct import

```codifide
import hello = sha256:f8fb5fda1b2462e7fb60641ad2bc4901439719966d4fe8610ea388b8685b321a
```

Binds the local name `hello` to the symbol whose canonical bytes hash to
that identity. Resolution happens at module load; the interpreter fetches
the bytes from a symbol store, rehashes them, and reconstructs a
`Definition`. From a call site, `hello(...)` behaves exactly like a local
`def`: same effect check, same contracts, same candidate dispatch.

The parser rejects malformed identities (`sha256:` prefix, 64 lowercase hex
characters). The runtime rejects a module whose imports cannot be resolved,
failing fast before any body runs.

### Index-mediated import

An *index* is a module whose `imports` map is its export table. It has no
definitions of its own. Its job is to say "if you want `hello`, it is at
`sha256:f8fb...`; if you want `goodbye`, it is at `sha256:bd59...`."

A consumer writes:

```codifide
from sha256:5899ab1c... import hello, goodbye
```

The parser resolves each name through the target index's imports table at
parse time. Those names become direct bindings in the consumer's own import
list, identical in shape to the consumer having written each
`import <name> = sha256:...` line directly. The runtime does not know or care
that an index was used.

The target of a `from`-import must be an index — a module whose exports live
in its imports table. Local symbols in the target module are not reachable
through `from`; to re-export a locally defined symbol, the target must first
import it by its own content identity.

Indices are themselves content-addressed. Same inputs produce the same
identity; changing the module name or the entry set changes the identity;
entry order does not.

## Shadowing

When a local definition name, an imported local name, and a primitive name
collide, resolution proceeds in this order:

1. Local definition in the module.
2. Imported name (either through `import` or `from`).
3. Primitive registered in the host.

A local `def foo` shadows `import foo = ...`, and an imported `foo` shadows
a primitive `foo`. Effects are still checked against the resolved callee, so
shadowing cannot be used to smuggle effects past the transitive check.

## Errors

Every runtime violation maps to a typed error class. Host-language
exceptions do not leak through. The eight kinds are:

| Error                      | When                                                        |
|----------------------------|-------------------------------------------------------------|
| `ParseError`               | Surface syntax does not parse.                              |
| `EffectViolation`          | A primitive or user call's effect is not in the budget.     |
| `ContractViolation`        | A pre or post clause did not hold.                          |
| `DispatchError`            | No candidate guard matched and no default exists.           |
| `RefusalError`             | ⊥ escaped a context with no handler.                        |
| `BottomPropagationError`   | ⊥ reached a primitive that cannot consume it.               |
| `PrimitiveError`           | A primitive call failed in the host (e.g. divide by zero).  |
| `RecursionLimitError`      | Call depth exceeded the interpreter's bound (default 64).   |

All errors inherit from `CodifideError` so a host can catch Codifide-level
failures separately from Python-level ones.

## Recursion limit

The interpreter bounds its own call depth (default 64) and raises
`RecursionLimitError` past that bound. The limit exists because a Codifide
program is untrusted input to its host; without an explicit bound a
pathological module could exhaust the Python stack and crash the embedding
process. A defense-in-depth handler in `run()` also maps Python's own
`RecursionError` to `RecursionLimitError`, so a host never sees a bare
`RecursionError`.

## Store CLI

The Python reference ships a content-addressed symbol store and a matching
CLI:

- `codifide store put <file.nm>` — store every symbol in a module.
- `codifide store get <hash>` — print canonical JSON for an identity.
- `codifide store list` — list every stored identity.
- `codifide store hash <file.nm>` — print identities without storing.
- `codifide store index --name <mod> name=sha256:<hex> ...` — mint an index
  from name-to-identity pairs, store it, and print its identity.

The store root resolves from `--store`, then `$CODIFIDE_STORE`, then
`~/.codifide/store`. See `docs/CANONICAL.md §Symbol store` for the three
properties a conforming store must uphold.

## What v0 does not have yet

- Type inference beyond literals.
- CBOR wire form (JSON-only).
- Graph-native parallel evaluator. The interpreter is a tree-walker.
- Cost-based candidate selection. Dispatch is by guard order only.
- Time-indexed types (`T@timestamp`).
- Rust interpreter. The Rust crate covers canonical form only; the Python
  implementation is authoritative for semantics.
- Garbage collection for the store. It grows monotonically.
- Network transport for the store. It is local-filesystem only.
- A manifest format for transitive dependency closure of an imported symbol.

These are on the roadmap. v0 is the smallest thing that demonstrates the
idea honestly.
