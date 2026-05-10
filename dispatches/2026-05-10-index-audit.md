# Noema — audit note, index and `from`-import surface

*By Sable. 10 May 2026.*

Scope: the new `from <identity> import <names>` syntax, index module
authoring via `noema store index`, and the parser/runtime integration
for both. Methodology: six adversarial probes against the surface.

I did not test concurrent writes to indices, index lookups over a
compromised filesystem, or the interaction of indices with future
CBOR serialization. The first two are carried over from earlier audits.

## Findings

### P3-1 — Index targets are validated opportunistically, not exhaustively

**What.** When a consumer writes `from <index> import name1, name2`, the
parser resolves each listed name against the target index's `imports`
map. If the resolution succeeds, the consumer's import list is
populated with the identities those names point at. But the parser
does not verify that those pointees are actually present in the
store. A broken index — one naming identities that have never been
put — parses fine and blows up at runtime with a clean
`NoemaError: cannot resolve import`.

**Why this is a P3, not P2.** The runtime error is typed, clear, and
surfaces the exact missing identity. No silent failure; no data loss;
no soundness hole. The only thing an author loses by the opportunistic
rule is the ability to detect broken indices at publish time rather
than consume time.

**The alternative and why I'm not demanding it.** A parser pass that
walks every from-import target and verifies each pointee exists would
add an arbitrary amount of I/O to parse. It would also open a
denial-of-service vector against the parser via a hostile index
(thousands of entries pointing at non-existent identities). Leaving
the check at runtime is defensible.

**Fix if prioritized.** Add an opt-in `noema store verify <index>`
subcommand that walks an index's pointees and reports missing ones,
rather than shifting the cost into every parse.

### P3-2 — Name shadowing rule was behavior, not specification

**What was true before this audit.** Local defs won over imports won
over primitives. That was the lookup order in the interpreter. Nowhere
did the spec say so.

**Why this matters.** Not a security bug on its own, but a soundness
question when a fix lands: if someone "improves" the lookup order to
prefer imports, a consumer's local overrides silently stop taking
effect. Without a written rule, a second implementation could make a
different choice and still call itself spec-conforming.

**Closed during this audit.** The spec now has a §Shadowing section
stating the precedence order explicitly. A regression test pins the
local-wins behavior. The rule is: locals over imports over
primitives, and effect checks apply to whichever callee was
resolved. A local cannot launder effects through a shadowed import
because the transitive effect check examines the local def's declared
effects, not the import's.

### Not-findings (explicitly cleared)

- **Forged index bytes.** Storing arbitrary JSON at a hash and trying
  to `from-import` through it is rejected with `does not export` —
  the "index" has no `imports` map, so no name resolves. Clean.
- **From-importing a symbol (not an index) by its hash.** Same
  rejection path: a symbol's canonical JSON has no `imports` map.
  Clean.
- **Name collision with local def (shadowing).** Probed, behavior
  confirmed, now in spec and under test. See P3-2.
- **Huge name list stress.** 2000 names against a bad index fails
  fast (<1ms) on the first missing name. No pathological parser
  behavior.
- **Cycles via chained indices.** `from`-import reads the target's
  `imports` map once and binds names; no recursive unpacking.
  Cycles are not reachable through this path.

## What I did not test

- Concurrent writes racing the same index identity (carried over from
  previous audit; still open).
- Indices under a filesystem that can return different bytes for the
  same path on different reads (supply-chain of the filesystem itself
  is out of scope for now).
- Index rotation / deprecation workflow. The store grows monotonically;
  neither the store nor indices have a story for "this name used to
  point here, now it points there." By design, I think — content
  addressing means a rotated pointer is a new index with a new hash —
  but no test or doc pins this down.
- `cargo audit` on the dependency set after this turn's changes. No
  new deps were added, but re-running at every release gate is the
  discipline.

## Summary

Two P3 findings. The first is opportunistic index validation (runtime
surfaces it cleanly; tighten if someone hits it repeatedly). The
second is the shadowing rule that was behavior-only; now specified
and tested. No P0s, P1s, or P2s. The surface is honest.

The uncomfortable observation: indices make the store *much* more
useful, which means adversarial pressure on the store will increase.
The next audit should specifically look at index authoring as an
attack surface, because an agent that publishes indices is publishing
pointers into other agents' code.
