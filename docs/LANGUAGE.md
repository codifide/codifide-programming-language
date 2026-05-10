# Noema — Language Tour

This is the v0 language. Expect it to change. The canonical form is stable before
the surface syntax is.

## Surface syntax

Noema source is a *projection* of a hypergraph. v0 supports one projection: an
ASCII-compatible line-oriented form where every keyword has an optional unicode
glyph. The unicode form is canonical for display; the ASCII form exists so
humans can type it on a US keyboard while we bootstrap.

| ASCII         | Unicode | Meaning                                    |
|---------------|---------|--------------------------------------------|
| `def`         | `≡`     | definition                                 |
| `intent`      | `⟡`     | intent annotation (required)               |
| `sig`         | `σ`     | signature                                  |
| `effects`     | `⚡`     | effect set                                  |
| `pre`         | `⊢`     | precondition                               |
| `post`        | `⊣`     | postcondition                              |
| `cand`        | `ƒ`     | candidate body                             |
| `when`        | `¿`     | candidate guard                            |
| `believe`     | `⊨`     | belief dispatch                            |
| `=>`          | `⇒`     | dispatch arm                               |
| `<-`          | `←`     | bind                                       |
| `++`          | `⊕`     | concat                                     |
| `bottom`      | `⊥`     | refuse / abstain                           |

The parser accepts either form and emits the canonical form on projection.

## A first program

```noema
def greet
  intent "welcome a known user by name, neutrally"
  sig    (user: User) -> Unit
  effects {io.stdout, clock.read}
  pre    user.name != empty
  post   io.stdout.tail contains user.name
  cand
    io.say("Hello, " ++ user.name ++ ", it's " ++ clock.now.hm)
```

Every definition **must** declare an intent. The parser rejects definitions
without one. This is on purpose. Intent is the signal agents need most and the
one compilers historically throw away.

## Effects

Effects are declared as a set. During interpretation, every primitive call
contributes its effect label; the union must be a subset of the declared set,
or the program is rejected *before* running.

Effects you'll see in v0:

- `io.stdout` — writing to standard output
- `io.stdin` — reading from standard input
- `clock.read` — reading the wall clock
- `rand` — nondeterministic sampling
- `net.*` — any network call
- `model.*` — any model inference call

A function with `effects {}` is pure in the strict sense. Any attempt to call
a primitive with an undeclared effect is a static error.

## Contracts

Preconditions must hold on entry. Postconditions must hold on exit. Failure at
either end is a contract fault, not an exception — it is reported against the
function that promised, not the caller.

Postconditions may reference `result` (the return value) and the special
variables `io.stdout.tail`, `net.sent`, etc., which capture effect traces for
the call.

## Multiple candidate bodies

```noema
def sort
  intent "order a list ascending"
  sig    (xs: List[Int]) -> List[Int]
  effects {}
  post   sorted(result) and permutation(result, xs)

  cand
    intent "tiny input"
    when   len(xs) < 16
    insertion_sort(xs)

  cand
    intent "default"
    timsort(xs)
```

The runtime evaluates candidate guards in declaration order and picks the first
that holds. Contract checking is identical for every candidate — they all
answer to the same post.

## Belief dispatch

Values carry confidence. `believe` dispatches on it without the caller having
to know the internals:

```noema
def classify
  intent "label an image, refuse rather than guess"
  sig    (img: Image) -> Label
  effects {model.vision}
  cand
    label <- vision.classify(img)
    believe label
      conf(label) >= 0.85 => label
      conf(label) >= 0.60 => escalate(img, label)
      else                => bottom
```

`bottom` is first-class. It means the function *chose* to abstain. Callers must
handle it explicitly; it is not an exception.

## What v0 does not have yet

- Type inference beyond literals
- Full unicode glyph parsing (only the short list above)
- Multiple projections (JSON-only canonical round-trip)
- Time-indexed types (`Price@2026-05-10`)
- Content-addressed symbol store
- Distributed/parallel dataflow runtime
- Contract-driven candidate selection across performance axes
- Primitive delegation for arithmetic beyond the built-in set

These are on the roadmap. v0 is the smallest thing that demonstrates the idea
honestly.
