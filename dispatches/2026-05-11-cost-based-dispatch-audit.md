# Sable — audit of cost-based dispatch proposal (2026-05-11)

Auditor: Sable
Scope: the spec-amendment proposal at
`dispatches/2026-05-11-cost-based-dispatch-proposal.{readout.md,yaml}`.
Not the implementation (none exists yet); the proposal.

## Findings against the proposal

### CBD-1 — P1 — second-implementation conformance gap is real

The proposal acknowledges this at "medium" severity with the
mitigation "cost-based-dispatch test added to conformance suite."
I am upgrading it to P1.

Today, the Rust canonical crate does not parse or execute programs;
it only handles canonical form. That's fine for today's
conformance claim, which is byte-level agreement on canonical
form. Cost-based dispatch is a **runtime semantics** change, not
a canonical form change. The Rust crate doesn't execute, so it
can't "conform" to the dispatcher behavior.

This means:

- The conformance test can verify that a module with cost-annotated
  candidates parses and canonicalizes identically in Python and
  Rust. That's a canonical-form claim; still valid.
- The conformance test **cannot** verify that dispatch semantics
  agree, because only Python has a dispatcher.
- A future Rust runtime would have to implement cost-based
  dispatch *from the spec alone*. If the spec is ambiguous on
  any point (e.g., how ties between uncosted and cost=∞
  candidates break), the Rust runtime might diverge.

**Spec clarity required:** the proposal is specific enough on
the dispatch rule (`min(satisfied, key=(cost_or_infinity,
declaration_index))`), but it does not say **what happens if the
canonical form contains a non-integer `cost` value**. Options:

- Reject at parse time (proposal says this).
- Accept at parse time but reject at dispatch time (no-op today
  because parse-time rejection is strict enough).
- Accept and treat as `+∞` (lenient; bad idea; makes agent
  mistakes silent).

**Disposition:** proposal is close to sufficient but should
explicitly state that the canonical form's `cost` field MUST
be a non-negative JSON integer (or CBOR major-type-0) and that
any other shape is a `ParseError`. Right now the proposal says
this for the surface but not for the canonical form directly.

### CBD-2 — P1 — "cost = +∞ when absent" interacts surprisingly with all-uncosted programs

The proposed dispatcher rule is
`min(satisfied, key=(cost_or_infinity, declaration_index))`.

Today's dispatcher picks the first-declared satisfied candidate.
The proposed dispatcher picks it *only when every satisfied
candidate is uncosted* — in which case all have effective cost
`+∞`, and `min` by `(cost, index)` returns the earliest-declared.

This is the correct backwards-compatibility story. But it has an
edge case:

```codifide
def f
  intent "mixed annotations"
  cand
    intent "a"
    cost 100
    "a"
  cand
    intent "b"
    "b"
```

Under the proposal:
- `a` has cost 100
- `b` has effective cost `+∞`
- Dispatcher picks `a` (cost 100 < cost ∞)

Under today's semantics:
- Dispatcher picks `a` (declaration order)

Same answer. OK. Swap the order:

```codifide
def f
  intent "mixed annotations, reversed"
  cand
    intent "b"
    "b"
  cand
    intent "a"
    cost 100
    "a"
```

Under the proposal:
- `b` has effective cost `+∞`
- `a` has cost 100
- Dispatcher picks `a` (cost 100 < cost ∞)

Under today's semantics:
- Dispatcher picks `b` (declaration order; first wins)

**Different answers**. The amendment claims to be backwards
compatible for "programs without cost annotations," which is
true. But for **programs with even one cost annotation**, the
dispatcher can pick differently than declaration order would.

That is not a bug — it's exactly what cost-based dispatch is
for. But the proposal should name this explicitly so an agent
adding a single `cost` annotation to an existing candidate knows
the behavioral change it introduces.

**Disposition:** proposal should explicitly document "adding a
cost annotation to any candidate in a module changes the
dispatch semantics of that definition from 'first-satisfied' to
'cheapest-satisfied, declaration-index tiebreak.'" This is not a
spec change; just a clarity improvement in the readout.

### CBD-3 — P2 — `cost: 0` is meaningful and should be reserved

The proposal allows any non-negative integer. `cost: 0` means
"free" — always preferred over any positive cost. That's
consistent with the design, but it's also a footgun: an agent
that wants to say "I don't know the cost, use default" might
write `cost: 0` and accidentally promote the candidate to always
winning.

**Options:**

- Reserve `cost: 0` to mean "free, and you probably mean it."
  Document loudly.
- Forbid `cost: 0`. Require positive integers.
- Accept `cost: 0` silently and let agents learn.

**Recommendation:** allow, but document the footgun. Forbidding
is overreach; the proposal's thesis is that cost is informational.

**Disposition:** minor proposal edit to call out `cost: 0`
explicitly.

### CBD-4 — P3 — the proposal's `INFINITY` sentinel is implementation-level

The proposal's pseudocode uses `INFINITY` as a stand-in for "cost
when absent." That's fine in Python; the canonical form does
**not** encode infinity (canonical CBOR forbids infinity, and
canonical JSON would have to use some sentinel). The spec should
state that the absence of the `cost` field is the canonical
representation of "effective cost +∞," and that no infinity
value is ever written.

**Disposition:** minor spec-language edit in the eventual
`docs/CANONICAL.md` update.

### CBD-5 — P3 — proposal does not discuss interaction with effect check

The transitive effect check is orthogonal to dispatch. Cost
annotations do not change effects. But the proposal should
explicitly state that: a reader shouldn't have to reason about
whether cost annotations could somehow be used to route around
effect checking. They can't.

**Disposition:** one-sentence note in the proposal's "What this
proposal does not change" section.

### CBD-6 — P3 — proposal punts dynamic cost without saying when it will return

The proposal says dynamic cost (cost expressions rather than
literals) is "a future extension if the static form proves too
limiting." No criteria for "too limiting." The risk is that the
next persona to touch this decides dynamic cost is urgent and
re-opens the amendment.

**Disposition:** proposal should name a specific trigger for
re-opening, e.g. "if external feedback includes three distinct
requests for runtime-dependent cost, re-open." Weak trigger, but
better than "we'll know when we see it."

## What the proposal gets right

- Additive extension; existing canonical bytes and hashes are
  preserved. Strongest shape for a spec amendment.
- `min(cost, index)` dispatch rule is simple, specifiable, and
  easy to implement correctly.
- Integer-only cost avoids floating-point footguns.
- Backwards compatibility through "cost-absent means ∞" is
  clean and preserves v0 semantics when no annotations exist.
- The proposal explicitly refuses dynamic cost, float cost, and
  cost on primitives. Each of those would enlarge the surface
  and the risks.

## What I did not test

- I did not probe how the proposed dispatcher interacts with
  `believe` blocks. Belief dispatch is a different construct
  with its own rule; the proposal says it's unchanged, which I
  believe, but I did not verify the interaction explicitly.
- I did not probe whether cost annotations nest sensibly (a
  candidate whose body is a call to a function with its own
  costed candidates). This is second-order dispatch; should
  work via ordinary call semantics, but unverified.
- I did not audit what happens when `cost` is omitted **and**
  no candidate has a `guard`. This is the today-default case
  (no annotations anywhere), and `min` by `(∞, index)` returns
  the earliest-declared, matching today's behavior. But the
  audit of "dispatch over a program with zero annotations" is
  the exact test the existing test suite already pins, so it
  should survive.

## Post-audit disposition

- **CBD-1 (P1)** and **CBD-2 (P1)** are proposal edits, not
  rejections. The amendment is sound; the readout needs to be
  tighter on canonical-form field typing and on behavioral
  drift when adding a single cost annotation.
- **CBD-3 (P2)** is a documentation ask.
- **CBD-4, CBD-5, CBD-6 (P3)** are spec-language edits for
  the eventual CANONICAL.md update.

I recommend the proposal go back for a revision that resolves
CBD-1 and CBD-2 before Douglas approves it. Both are small
edits; 10 minutes of re-drafting, no semantic change.

## What I'm not yet sure of

Whether cost-based dispatch is the right next extension at all.
The proposal motivates it with a triage example, but agents
today don't have mature tools to estimate candidate cost. If
they can't annotate honestly, the amendment's value is theatre.
That's a strategic question for Douglas, not a soundness
question for me.
