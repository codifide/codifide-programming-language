# The day Codifide grew up a little — session readout (2026-05-11)

*By Quill.*

One day. Four external model reviews in the morning; by evening the
language has new ergonomics, three breaking-change proposals approved
and shipped, nine paired dispatches filed, and 166 tests passing
where there used to be 122. This is what happened.

## Before the day started

Codifide was a working prototype of a language for agents. Canonical
form as a typed hypergraph. Two wire serializations, JSON and CBOR,
agreeing byte-for-byte across Python and Rust. An effect system that
actually checks effects transitively. First-class refusal. A
content-addressed symbol store. Three personas — Quill, Glyph, Sable
— keeping the project honest in prose, structure, and audit.

122 Python tests passed. 10 Rust tests passed. The capability manifest
hash was `sha256:522c48d0…`.

## What the morning brought

Four external AI agents — Copilot GPT-5.4, Claude Opus 4.7, Gemini
2.5 Pro, and Grok Code Fast 1 — each wrote three Codifide programs
after reading the docs. Two agents wrote nine-for-nine correct
programs. Two did not.

The failure modes were informative. Copilot guessed `%` for modulo,
`str.reverse` for string reversal, `clock.hour` for hour-of-day.
None of those are Codifide. The language has `mod`, `reverse` (list
only), and `clock.now` (a record). The docs said so; Copilot didn't
read that far.

Gemini's failures were different. It wrote perfectly reasonable
multi-line `list(...)` literals inside `cand` blocks — the kind of
thing any human programmer writes without thinking. The parser hit
an uncaught `AttributeError` and crashed. Not Gemini's fault. Ours.

The four reviews converged on the same ask: a quick-reference
cheat-sheet, better error messages when an agent reaches for
something that doesn't exist, and — quietly — "please fix the
parser."

## The ergonomics pass (morning session)

Three personas reviewed the feedback critically. Sable filed a P1
on the parser crash. Quill wrote the prose. Glyph structured the
decisions.

Six yes/no calls, recorded in `dispatches/2026-05-11-ergonomics-
decisions.readout.md`. The three yesses:

- **Fix the parser.** Multi-line expressions inside `cand`, `pre`,
  `post`, `when`, and bind right-hand sides. EOF-safe peeks. Clean
  `ParseError` where there used to be `AttributeError`.
- **Make `reverse` polymorphic.** Same primitive name, works on
  strings and lists. Establishes the rule: pure primitives are
  polymorphic when semantics transfer cleanly.
- **Ship hint messages.** When an agent reaches for `str.reverse`,
  `clock.hour`, or `%`, the error now names the correct form in
  one line.

Plus a new `docs/AGENT_QUICKREF.md` page distilled from the
capability manifest.

The three nos, with reasoning on the record:

- No infix `%` for `mod`. It opens the door to `+`, `-`, `*`, `/`
  as infix — drifts the language toward "Python with intent
  annotations." Better error text instead.
- No inline `if`/`when` statement. Candidate dispatch is the
  answer already. Two paths to the same destination is the drift.
- No separate `str_reverse` primitive. Polymorphic `reverse` does
  the job without enlarging the primitive surface.

After the pass: 129 Python tests, capability manifest unchanged at
`sha256:845dbbbf…` (had already moved in an earlier session, for
unrelated reasons).

## The carryover pass (late morning)

Seven items had been sitting in "deferred." User pushed back: why.

Per-item triage produced three do-now and four hold-with-reasoning
calls.

The three do-nows:

- **Numeric-boundary CBOR conformance tests.** A straightforward
  coverage extension — integer head transitions, signed zeros,
  exact-f16 values. But the exhaustive f16 fixture uncovered a real
  cross-parser divergence. Python's `json` and Rust's `serde_json`
  disagree on decimal parsing for f16 subnormals. About 14% of f16
  patterns hash differently. Filed as AUD-04 at P2, which later
  upgraded to P1 after further probing.
- **Rust canonical-crate fuzz harness.** 22 hand-curated adversarial
  inputs plus 500 random ones. Zero panics found. Zero new
  dependencies.
- **CLI filesystem-safety audit.** Sable probed the Python CLI's
  file-read paths. Found a P1: `codifide canonical /dev/zero` hung
  indefinitely. Fixed in-session with a 16 MiB read cap; two P3s on
  symlinks and store paths accepted as documented behavior.

The four holds (with recorded reasons rather than drift): primary-
hash migration needed user approval; store GC needed a design
dispatch; cost-based dispatch needed a spec-amendment proposal;
CBOR re-audit needed new surface to audit.

141 Python tests, 14 Rust tests, one skipped diagnostic documenting
the f16 divergence.

## The deferred-first-step pass (afternoon)

User pushed again: take the first step on each deferred item,
preserving the governance boundary.

This is where the day got interesting. The CBOR re-audit — the one
I thought would be the easy one — found that the f16-subnormal
divergence wasn't CBOR-only. It also affected the JSON primary hash.
Python emits `5.960464477539063e-08` as the shortest decimal for
that value; Rust's serde_json emits `5.960464477539064e-8`. Same
abstract float, different canonical bytes, different SHA-256. I
had to upgrade AUD-04 to AUD-08 at P1 severity: the language's
cross-implementation content-hash claim was actually false on some
reachable inputs. Not on any current example, but on any program
containing an f16-class float literal.

The three proposals landed with Sable audits attached:

- **Primary-hash migration JSON → CBOR** — motivated directly by
  AUD-08. CBOR hashes IEEE-754 bits and sidesteps decimal-parser
  divergence entirely. Sable audited the proposal and found four
  more P1/P2 concerns, which I resolved before filing. (Manifest
  hash is CBOR already; polyform store read path is confirmed
  clean; no in-repo content depends on specific JSON hashes; the
  `conf: 1.0` on every literal happens to round-trip exactly.)
- **Cost-based candidate dispatch** — an optional `cost` field on
  candidates, with the dispatcher picking `min((cost, index))`
  over satisfied candidates. Additive and backwards-compatible.
  Sable flagged two P1s (canonical-form typing needed tighter
  language; behavioral-drift notice needed to be explicit). Both
  resolved in R1 revision.
- **Store GC design** — user-declared roots in a `ROOTS` file;
  dry-run default; file-lock concurrency safety; explicit refusal
  to GC with empty roots. Two alternatives refused with reasons:
  time-based GC (conflates "old" with "unwanted") and implicit GC
  on every put (violates the mental model).

Paired readouts and YAMLs filed. Capability manifest unchanged;
nothing had shipped yet.

## The migrations pass (evening)

User: "The change cost is low now as we have not published yet. I
want you do all of what's on the todo list now."

Fair enough. Three proposals, one session, in dependency order.

### Primary hash migration

`symbol_hash`, `symbol_bytes`, `content_hash`, `canonical_bytes`,
store `put`/`put_module`, the Python CLI, and the Rust CLI all
moved to CBOR primary. Legacy JSON paths preserved under `_json`
suffixes. Pre-migration stored objects remain fetchable by their
old JSON identities (the store's polyform read path).

Structurally closes AUD-04 (P2) and AUD-08 (P1) on the Python
primary path. The Rust CLI still accepts canonical JSON text as
input — which means the f16-exhaustive diagnostic still fails
when feeding JSON text to Rust. Un-skipping that test requires a
Rust subcommand that accepts canonical CBOR bytes directly;
scheduled as a future follow-on.

### Cost-based candidate dispatch

`Candidate.cost` as an optional `Option[int]`. Surface keyword
`cost` inside `cand`. Dispatcher rewritten. Canonical form
additive: un-annotated modules produce byte-identical canonical
form as before. Rust crate updated. Spec docs updated in
`docs/CANONICAL.md` and `docs/LANGUAGE.md`. 14 new tests.

### Store GC

New `ROOTS`, `GC.LOG`, `LOCK` files at the store root.
`SymbolStore.gc(execute=False)` with `GCReport`. CLI subcommands
`codifide store gc [--execute]` and `codifide store roots
{list,add,remove}`. 11 new tests covering the sound-deletion
contract, transitive closure through indices, log durability,
and ROOTS file semantics.

## Where things stand at session close

- **166 Python tests passing + 1 skipped** (was 122 at day start).
- **14 Rust canonical tests passing** (was 10).
- **Capability manifest hash**: `sha256:56fa68ae…` (was
  `sha256:522c48d0…` at day start, briefly `845dbbbf…` between).
  The delta over the day: the `cost` surface keyword is new.
- **Nine new dispatches filed.** Four ergonomics, three
  deferred-item proposals with audits, one carryover post, one
  migrations post. Plus this readout.
- **One long-standing design vulnerability (AUD-08) closed** on
  the Python primary path. Rust primary path awaits one small
  follow-on.

## What I'm not yet sure of

Whether any of today's changes actually improve what agents can
do with Codifide. The parser fix closes a real crash; the
hint-driven errors address four named agent failures directly;
the cost dispatch and GC extend the language meaningfully. But
the honest test is the next external-model run, which has not
happened yet. If a fresh agent reads the new `docs/AGENT_QUICKREF.md`,
consumes the new manifest at `sha256:56fa68ae…`, and writes correct
Codifide on first try at a higher rate than Copilot and Gemini did
this morning, the day worked. Until then, I'm optimistic but not
certain.

The language is in better shape than it was this morning. That I
am sure of.
