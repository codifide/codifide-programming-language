# Proposal — cost-based candidate dispatch (2026-05-11)

**Status:** SPEC-AMENDMENT PROPOSAL. Not implementation. Per
`GOVERNANCE.md §Decision-making`, spec changes require a dispatch
proposal + Sable audit + Douglas's approval before implementation
begins.

**Context.** Today's candidate dispatch (see `docs/LANGUAGE.md
§Multiple candidate bodies` and `docs/CANONICAL.md §Candidate
dispatch`) evaluates candidate guards in declaration order and
runs the first candidate whose guard holds. The dispatcher is
ordering-dependent: a candidate that appears earlier wins if its
guard is satisfied, regardless of whether a later candidate is
"better" by some other metric.

This is the right default for v0 — it's deterministic and
predictable. But it prevents a specific shape of program Codifide
was designed for: **agent-authored candidates annotated with
relative cost, where the dispatcher prefers cheaper candidates
when multiple guards hold.**

Example from a hypothetical future triage program:

```codifide
def classify
  intent "label a request; use the cheapest sufficient path"
  sig    (req: Request) -> Label
  effects {model.vision, model.language}

  cand
    intent "fast path for obviously-cat images"
    cost   1
    when   is_obvious(req)
    fast.classify(req)

  cand
    intent "medium path — cheap heuristic"
    cost   10
    when   has_text_label(req)
    heuristic.classify(req)

  cand
    intent "full vision inference"
    cost   1000
    vision.classify(req)
```

Today all three can satisfy the same `Request`, and the dispatcher
picks the first declared one (the fast path) even if `is_obvious`
is expensive and the vision path is actually cheaper. Cost
annotations let the dispatcher prefer candidates ranked by cost,
with declaration order only as a tiebreak.

## What changes in the canonical form

A new optional field on candidates:

```json
{
  "kind": "candidate",
  "intent": "fast path",
  "cost": 1,              // NEW: optional, integer, non-negative
  "guard": <expr>,
  "body": <expr>
}
```

- **`cost`** is optional; its absence means "cost = +∞ for
  dispatch purposes" (i.e. "only pick me if no cost-annotated
  candidate can satisfy"). The alternative — cost = 0 default —
  would silently promote unannotated candidates to winners.
- **`cost`** is a non-negative integer. Why integer not float:
  cost has no natural unit, floats invite fake precision, and
  the canonical CBOR form for integers is cleaner.
- **`cost`** is evaluated statically; it is not an expression.
  Dynamic cost (cost computed from runtime inputs) is a future
  extension if the static form proves too limiting.

**Canonical-form typing contract (resolves Sable CBD-1):** the
`cost` field MUST be a canonical-JSON integer literal (no `.`,
no exponent) or a canonical-CBOR major-type-0 value. The absence
of the `cost` field is the canonical representation of "effective
cost +∞"; no infinity sentinel is ever written. A `cost` value
that is anything other than a non-negative integer is a
`ParseError` at parse time. A canonical form consumer that cannot
validate this MUST reject the module.

**`cost: 0` is allowed but notable (CBD-3).** Zero means "always
preferred over any positive cost." An agent writing `cost: 0`
should mean it literally. Using `cost: 0` as a placeholder for
"I don't know" is a footgun: such a candidate will always win
over any honestly-annotated candidate. If you don't know the
cost, omit the field.

Existing candidates without a `cost` field remain valid. The
canonical form extension is **additive and backwards
compatible**: a module's canonical bytes and hash do not change
if its candidates have no cost annotations.

## What changes in the surface syntax

```codifide
cand
  intent "fast path"
  cost   1
  when   is_obvious(req)
  fast.classify(req)
```

Parser changes:

- New line-level keyword `cost <integer>` inside a `cand` block.
- Accepted after `intent` and before `when` (conventional order),
  but the parser accepts any order inside a `cand` just like it
  does for `intent`/`when` today.
- Rejects negative integers, floats, and non-numeric values with
  a typed `ParseError`.

## What changes in the dispatcher

Today's dispatcher:

```
for cand in definition.candidates:
    if cand.guard is None or eval(cand.guard) is truthy:
        return eval(cand.body)
raise DispatchError(definition.name)
```

Proposed dispatcher:

```
satisfied = [cand for cand in definition.candidates
             if cand.guard is None or eval(cand.guard) is truthy]
if not satisfied:
    raise DispatchError(definition.name)
chosen = min(satisfied, key=lambda c: (c.cost or INFINITY, declaration_index(c)))
return eval(chosen.body)
```

Sorting key is `(cost, declaration_index)`. A candidate without
a `cost` field has effective cost `+∞`, so it is picked only if
every other satisfied candidate is also uncosted. Among same-cost
candidates, declaration order is the tiebreaker.

**Guard evaluation order is still left-to-right.** The dispatcher
evaluates every candidate's guard, in declaration order, before
picking the winner. Guards are already pure (effect budget = ∅),
so evaluating all of them is free of observable side effects.

**The v0 semantics are preserved** when no candidate has a `cost`
field: every candidate has effective cost `+∞`, and `min` by
`(cost, index)` returns the earliest-declared satisfied candidate.
Which is exactly today's behavior. This is how the amendment is
additive rather than breaking.

## What changes in the capability manifest

The `candidate` AST kind's field list gains one entry:

```json
{
  "name": "cost",
  "type": "int?",
  "description": "optional non-negative dispatcher-cost annotation"
}
```

The manifest hash moves. The old hash
(`sha256:845dbbbf…`) and the new one would differ in exactly
one field description. That hash change is the cost of
any capability-surface extension; the spec committed to it when
the capability manifest was introduced (see `docs/CAPABILITY.md
§Stability`).

## What a second implementation must do

- Parse the optional `cost` field on `candidate` objects from
  canonical JSON and CBOR.
- Reject `cost` values that are not non-negative integers.
- Implement the `min(satisfied, key=(cost, index))` dispatch
  rule.
- If a legacy Codifide runtime (pre-amendment) receives a module
  with `cost`-annotated candidates, it MUST ignore the field
  and use declaration-order dispatch. This is the "forward
  compatibility through graceful degradation" rule already
  specified in `docs/CANONICAL.md §Unknown fields` (if that
  section doesn't exist, this amendment adds it).

## What this proposal does not change

- Guard evaluation semantics (still left-to-right, still pure).
- The `believe` block semantics. Belief dispatch is a different
  construct with different rules; this amendment does not
  touch it.
- The contract system (pre/post/guard are still evaluated with
  empty effect budget).
- The effect algebra (transitive subset rule is orthogonal to
  cost). Cost annotations cannot route around effect checking —
  the transitive check runs before dispatch and is unaffected
  by which candidate eventually wins.
- Anything about canonical form for modules that don't use
  cost annotations.

## Behavioral-drift notice (resolves Sable CBD-2)

**Adding a `cost` annotation to any candidate in a module
changes the dispatch semantics for that definition from
"first-satisfied" to "cheapest-satisfied, declaration-index as
tiebreak."** This is the feature, not a bug — but it means
adding a single cost annotation is not a local edit; it alters
how every unannotated candidate competes with the annotated one.

Concrete example. Consider:

```codifide
def f
  cand        # unannotated
    "b"
  cand
    cost 100
    "a"
```

Pre-amendment: always returns `"b"` (first satisfied).
Post-amendment: always returns `"a"` (cost 100 < cost ∞).

An agent refactoring a module to add a cost annotation to one
candidate should be aware that every other candidate is now
implicitly "cost +∞" and will lose to any cost-annotated
alternative that satisfies its guard. The fix, if the agent
wants to preserve old behavior, is to annotate every candidate.

## Risks

- **Agent authors can lie about cost.** A candidate annotated
  `cost 1` that actually costs a million operations will be
  chosen over an honest `cost 10` candidate. This is the same
  shape of risk as intent annotations — agents can claim
  anything. Spec does not attempt to validate cost; the claim
  is informational.
- **Cost as integer loses precision for some ratios.** A program
  that wants to express "A is 3.7× cheaper than B" has to use
  `cost 10` and `cost 37`, or similar. Integer encoding is
  deliberate; see above for rationale.
- **Second implementations must implement it consistently.** A
  Python implementation that dispatches by cost and a Rust
  implementation that still dispatches by declaration order
  produces observably different programs for the same canonical
  bytes. This is a conformance issue. The conformance test
  suite needs a cost-based-dispatch test.

## Migration story

There is none to speak of. The amendment is additive:

- Every existing `.cod` program continues to parse, canonicalize,
  and execute identically.
- Every existing canonical JSON or CBOR module round-trips
  through the new parser identically.
- Content hashes of existing modules are unchanged.
- New programs using `cost` are rejected by a pre-amendment
  runtime (unknown surface keyword `cost`) but accepted by the
  post-amendment runtime.

The one real change is the capability manifest hash. If the
primary-hash migration (separate proposal) ships before this
amendment, the manifest hash is recomputed under CBOR-primary at
that point and cited in both documents.

## What I'm asking Douglas to decide

- **Approve the amendment as written** — a future session implements it.
- **Approve with modifications** — note the modifications and I
  re-issue.
- **Defer until after v0.3 stabilizes** — the amendment is
  useful but not urgent.
- **Reject** — state the specific design concern; either the
  proposal gets revised or the amendment is withdrawn.

## What I'm not yet sure of

- Whether `cost` should be an expression rather than a literal.
  My proposal says literal. If the cost of a candidate is
  actually context-dependent (e.g. "cheap for small inputs,
  expensive for large"), a literal cost is too blunt. But I
  couldn't find a clean way to make it an expression without
  letting agents put arbitrary effectful computations in the
  cost — which defeats the point. Recommend: literal, revisit
  if limiting.
- Whether the dispatcher should also accept a `--cost-bias`
  flag at the CLI to prefer `(cost, index)` vs `(index, cost)`
  key ordering. My proposal picks one. If we want runtime
  tunability, the flag is easy.
- Whether cost annotations should appear in the capability
  manifest's `primitives` section too (primitives have inherent
  cost; agents might want to see it). I left primitives out of
  scope; this amendment is about user-defined candidates only.
- Whether the governance process has a convention about who
  writes the paired Sable audit of a spec amendment. I wrote
  the audit myself; if convention says a fresh persona should,
  re-issue.
