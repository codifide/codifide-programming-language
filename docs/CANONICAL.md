# Noema — Canonical Form

The canonical form is the source of truth. Surface text is a projection. Two
programs are the same program iff their canonical forms are equal under the
structural-equality rule below.

In v0 we serialize canonical form as JSON. CBOR and a content-addressed store
are planned.

## Top-level shape

```json
{
  "noema": "0.1",
  "module": "example",
  "symbols": {
    "<name>": <Definition>,
    ...
  }
}
```

## Definition

```json
{
  "kind": "definition",
  "name": "greet",
  "intent": "welcome a known user by name",
  "signature": {
    "params": [{"name": "user", "type": "User"}],
    "returns": "Unit",
    "effects": ["io.stdout", "clock.read"]
  },
  "pre":  [<Expr>, ...],
  "post": [<Expr>, ...],
  "candidates": [<Candidate>, ...]
}
```

### Candidate

```json
{
  "kind": "candidate",
  "intent": "default",
  "guard": <Expr or null>,
  "body":  <Expr>
}
```

## Expression AST

Every expression node has a `kind` discriminator.

| kind       | payload                                             |
|------------|-----------------------------------------------------|
| `lit`      | `{"value": <json>, "type": <str>, "conf": <float>}` |
| `ref`      | `{"name": <str>}`                                   |
| `call`     | `{"fn": <str>, "args": [<Expr>...]}`                |
| `bind`     | `{"name": <str>, "expr": <Expr>, "in": <Expr>}`     |
| `seq`      | `{"steps": [<Expr>, ...]}`                          |
| `believe`  | `{"subject": <Expr>, "arms": [[<Expr>, <Expr>], ...], "else": <Expr>}` |
| `bottom`   | `{}`                                                |
| `concat`   | `{"parts": [<Expr>, ...]}`                          |
| `attr`     | `{"target": <Expr>, "name": <str>}`                 |

## Structural equality

Two canonical forms are equal if their JSON is equal *after*:

1. Sorting object keys lexically.
2. Normalizing floats to their canonical IEEE representation.
3. Interning string literals.
4. Stripping `intent` strings from comparison when semantic-equality is
   requested (the default is intent-preserving).

This gives us a stable hash for content addressing.

## Effect set algebra

Effects form a powerset lattice. Static analysis computes for every expression
a least upper bound of its subexpressions' effects plus any primitive it calls.
A definition is well-typed iff every candidate's effect LUB is a subset of the
signature's declared effect set.

This is the cheapest, most useful static check we can ship and it rules out an
entire class of agent errors (accidentally phoning home, accidentally touching
state) with a single pass.
