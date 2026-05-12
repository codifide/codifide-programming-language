# Six-program assessment (2026-05-11)

*By Quill, with a Sable finding or two along the way.*

After the full day of migrations and polish, user asked me to
write six random Codifide programs of varying complexity and
reassess. Here's what happened.

## The six programs

| # | File                                      | Complexity | Exercises                                                |
|---|-------------------------------------------|------------|----------------------------------------------------------|
| 1 | `01_fahrenheit_to_celsius.cod`            | trivial    | arithmetic primitives                                    |
| 2 | `02_email_valid.cod`                      | easy       | string `contains`, `and`, pre/post contracts             |
| 3 | `03_fizzbuzz.cod`                         | medium     | cost-based candidate dispatch, `and` + `mod` composition |
| 4 | `04_greeting_confidence.cod`              | medium     | `belief` + `conf` + `believe` dispatch, first-class refusal |
| 5 | `05_balanced_brackets.cod`                | medium-hard| string primitives for approximate balance check         |
| 6 | `06_pipeline.cod`                         | hardest    | multi-function composition, bind threading, cost dispatch |

## What happened on first run

Four programs ran first try. Two hit **previously-undiscovered
parser bugs** — not from anything I did today, but from
surfacing identifiers and call shapes the existing test corpus
never exercised. Both are in the expression parser's infix
desugaring pass. Fixed in this session.

### Bug 1: `and(...)` and `or(...)` as function calls misparsed

`02_email_valid.cod`'s `post eq(result, and(contains(s, "@"),
contains(s, ".")))` failed with `unexpected token ','`. Root
cause: the desugarer treats `and` and `or` as infix operators
and tries to rewrite `and(a, b)` into call form, but that
rewrite assumes `and` sits *between* two operands. A call-shaped
`and(a, b)` has only `(` to its right, which the desugarer
misreads as the right operand's start.

Fix: when a word operator is immediately followed (after
optional whitespace) by `(`, it's a function call, not infix.
Skip the rewrite in that case.

### Bug 2: identifiers containing `or` or `and` were split

`04_greeting_confidence.cod`'s call `greet_or_refuse("Ada")`
failed with `unbound name: 'greet_'`. Root cause: the word-
boundary check used Python's `str.isalnum()`, which considers
`_` a non-alphanumeric character. So inside
`greet_or_refuse`, the substring `or` has `_` on both sides —
passes the boundary check — and the desugarer split the
identifier into `greet_` + `_refuse`.

Fix: treat `_` as part of an identifier for the boundary check.
Both `greet_or_refuse` and `check_and_act` now parse correctly.

### Why existing tests missed both

Neither pattern appears in any `.cod` example pre-today. The
language's own standard idioms use `and`/`or` as infix (`p and
q`), never as calls. Examples happen to avoid identifiers with
`or`/`and` substrings. Assessment programs written with no such
bias surfaced both immediately.

Filed as Sable finding AUD-2026-05-11-11 (both are P2 — parser
incorrectness, not soundness; agents can work around but
shouldn't have to).

Regression tests in `tests/test_parser.py`:

- `test_and_as_function_call_parses`
- `test_or_as_function_call_parses`
- `test_and_call_runs_end_to_end`
- `test_identifier_containing_or_does_not_split`
- `test_identifier_containing_and_does_not_split`

## What the programs reveal about the language today

### What worked well

- **Cost-based dispatch landed as intended.** `fizzbuzz_one`'s
  four candidates dispatch in expected order:
  divisible-by-both-3-and-5 wins first because it's cheapest (cost
  1) among its satisfying peers. Reading the code, the cost is
  the selection rationale; the guards are the factual predicates.
  That separation is useful.
- **Contracts carry weight.** Every non-trivial program has a
  `pre ne(s, "")`. A few have `post` clauses that re-derive the
  result (`post eq(result, upper(trim(s)))`). Writing the post
  made me write a body that matched it; the post is cheap
  documentation plus machine-checked proof.
- **`believe` + `conf` + refusal compose.** Program 4
  demonstrates the confidence-gated idiom Codifide was designed
  for. A name that might be initials gets hedged; an empty name
  is refused. The refusal isn't an exception — it's `bottom`,
  which the `else` arm of `believe` produces and the top-level
  `run` surfaces as `RefusalError`. This is the language's
  distinctive shape.
- **Multi-line expressions work.** Programs 3 and 6 both have
  `list(...)` literals spanning many lines. Previously, this was
  the Gemini-crash case (2026-05-11 morning). Now uneventful.

### What Codifide cannot do yet (surfaced by these programs)

- **Per-character iteration is not a thing.** My
  `balanced_brackets.cod` (#5) degenerated into a count-only
  check because there's no way to iterate characters or fold
  over a string. A proper balance check requires either
  recursion over string indices (no `char_at` primitive today)
  or a fold (no fold primitive). I left the workaround in with
  a comment calling it out explicitly.
- **No `if ... then ... else` expression.** The pipeline program
  uses bind-then-compose-strings because there's no inline
  conditional. For longer pipelines this would grow.
- **The `classify_length` function in #6 has three candidates
  with cost annotations and no default** — if no cost-annotated
  guard holds, we'd get `DispatchError`. In practice my
  `"long"` candidate has no guard so it's always-satisfied, and
  it has the highest cost so it only wins when nothing cheaper
  matches. This works but required thinking about.
- **String operations are fine for normalize-and-check but
  limited for parse-and-transform.** There's no regex, no
  substring-index-of, no slice. Enough for programs that treat
  strings as opaque tokens.

### The language's distinctive strength

Reading the six programs back-to-back, the thing that makes
Codifide feel different from a "Python with intent" is how
**refusal and confidence compose naturally.** Program 4's
dispatch tree reads like a conversation:

- If I'm 90% confident, greet normally.
- If I'm 40% confident, hedge.
- Otherwise, refuse.

Writing that as nested `if` in Python would be ugly. Writing it
as exceptions would conflate "this is below threshold" with
"this crashed." Codifide's `believe` + `bottom` gives the right
shape for the thing. That's the win.

## Numbers after this assessment

- **Python tests: 178 passing** (was 172 after this morning's
  polish). +5 new regression tests from the parser bugs found
  today; no other delta.
- **Rust tests: 28 passing** (unchanged).
- **Manifest hash: unchanged** —
  `sha256:56fa68ae1794a99f2c52c1e5dda0fc7fa2f51241fbfca32c79296e184e6b43b5`.
  The parser-bug fixes are behavioral, not capability-surface.
- **Assessment pass rate: 6/6** after two parser fixes.

## Honest reassessment

The language is in usable shape. Writing six varied programs in
maybe 15 minutes with only two real blockers is a reasonable
outcome. Both blockers were pre-existing bugs the test corpus
hadn't surfaced — not bugs I introduced today. That's a good
sign: today's changes added surface without breaking what
already worked, and the act of using the language honestly
surfaces what the tests can't.

Three observations for where to steer next:

1. **Fuzz the expression parser against identifiers.** The
   infix-desugaring bug class is probably not exhausted. A
   generator that produces identifiers containing every keyword
   and operator substring would catch peers of these two bugs
   before external agents do.
2. **A small standard library of composable string operations.**
   `char_at`, `indexof`, `slice` would turn #5 from "approximate
   balance" into "actual balance." Not urgent, but the gap is
   real.
3. **Document the idiom for "multi-tier fallback without
   `bottom` propagation."** Program 4 dispatches on confidence
   cleanly via `believe`; program 6 dispatches on input shape
   via guards + cost. Both work, but an agent coming in fresh
   might reach for one where the other is clearer. A
   cookbook-style doc with a handful of "here's the shape for
   this kind of problem" patterns would help.

Not filed as proposals. Filed as observations in this dispatch
for future sessions to consider.

## What I'm not yet sure of

Whether the language's current feature set is actually
sufficient for the programs agents will want to write. The six I
wrote here are deliberately-chosen; the ones an agent facing a
real task would reach for might want things Codifide hasn't
imagined yet. The fresh-agent simulation from this morning is
still the most honest answer to that question, and the most
honest answer is that we don't yet know.
