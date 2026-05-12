# Ergonomics pass — decisions readout (2026-05-11)

Four external model reviews landed in `dispatches/` on 2026-05-11.
Two agents (Claude Opus 4.7, Grok Code Fast 1) wrote correct programs.
Two (GPT-5.4 via Copilot, Gemini 2.5 Pro) did not — one from guessing at
primitives and operators, the other from hitting a real parser crash on
benign multi-line input.

This readout records the yes/no decisions made in response, with the
reasoning for each. It is paired with
`dispatches/2026-05-11-ergonomics-decisions.yaml` (structured form) and
`dispatches/2026-05-11-ergonomics-audit.md` (Sable audit).

## The decisions

### 1. Fix the parser crash and accept multi-line expressions inside a candidate body. **YES.**

*The issue.* `examples/ai_generated/classify_numeric.cod` and
`palindrome.cod` both wrote a perfectly reasonable `list(...)` literal
split across three lines inside a `cand` block. The parser crashed with
`AttributeError: 'NoneType' object has no attribute 'kind'` from
`expr_parser.parse_atom`. Root cause: line-oriented outer parser hands
the expression parser one physical line at a time; an expression with
unbalanced parens can never succeed on a single line; peek-past-EOF
dereferences `None`.

*Why yes.*
- Typed-error discipline is a design invariant. A bare `AttributeError`
  leaking through the `parse() -> Module | ParseError` contract is the
  same class of bug as the original audit's P1-1 (host exceptions
  leaking through the runtime). That's not optional.
- Multi-line expression is not prohibited by the spec. It is only
  prohibited by implementation accident. Spec-implementation mismatch
  defaults to "fix the implementation" unless the spec is the thing
  that's wrong, and here the spec is silent — a gap, not an intent.
- An agent that reaches for a multi-line argument list is not guessing.
  It is formatting for readability, which the language should reward.

*What it changes.* Line continuation inside unbalanced `(`, `[`, `{`
inside `cand`, `pre`, `post`, and `when` bodies. EOF-in-expression is
a clean `ParseError`, not `AttributeError`.

*What it does not change.* The canonical form. Surface is projection;
canonical is truth. Two surface spellings of the same expression
(single-line and multi-line) must produce the same canonical bytes.

### 2. Make `reverse` polymorphic over string and list. **YES.**

*The issue.* GPT-5.4 wrote `str.reverse(text)` to reverse a string.
`reverse` exists in the primitive set but only for lists.

*Why yes.*
- The design thesis says "primitives are named, not methods." A
  `str.reverse` primitive would relax the thesis in the wrong direction
  — method-like names per type would multiply the primitive surface
  without adding expressiveness.
- A polymorphic `reverse` is cleaner. The semantics transfer directly:
  reverse a sequence. String and list both qualify. This also
  establishes a rule for future primitives: *pure primitives are
  polymorphic when the semantics transfer cleanly and the return shape
  is unambiguous*.
- An agent that writes `reverse(text)` — which GPT-5.4 did not, but
  the next one might — gets the intuitive answer. That's the right
  default.

*What it changes.* `reverse("abc")` returns `"cba"`. `reverse([1,2,3])`
continues to return `[3,2,1]`. The canonical form for both call sites
is unchanged; only runtime behavior extends.

### 3. Reject infix `%` as sugar for `mod`. **NO.**

*The issue.* GPT-5.4 wrote `n % 2 == 0`. The parser rejected `%`.

*Why no.*
- `%` as infix fights the core thesis. Agents optimize for explicit,
  named primitives; infix sugar is a human ergonomics affordance that
  costs the language its self-description property. The existing
  comparison infix (`<`, `<=`, `==`, etc.) is a calculated exception
  justified because it keeps pre/post clauses legible; arithmetic does
  not get the same carve-out.
- Adding `%` creates the implicit expectation that `+`, `-`, `*`, `/`
  also work. Once that door opens it doesn't shut, and the language
  drifts toward "Python with intent annotations."
- The right fix is discoverability, not syntax. An agent that reads
  the capability manifest first will never reach for `%` because
  `mod(a, b)` is right there.

*What does change.* The lexer now raises a `ParseError` (not a
`LexError`) for `%` and `+`, `-`, `*`, `/` outside numeric literals,
with a hint naming the primitive form. One line of error text per
operator.

### 4. Reject inline `if`/`when` as statement-level conditional. **NO.**

*The issue.* GPT-5.4 wrote `when lt(hour, 12) io.say(...)` at
statement position inside `greet_by_time.cod`.

*Why no.*
- Codifide's answer to conditional dispatch is multiple `cand` blocks
  with `when` guards. That is not an accident; it is the language
  treating "choose between implementations" and "choose between
  values" as the same question — candidate dispatch.
- Adding inline `when` creates two paths to the same destination. One
  is specified, one would be a convenience. Two paths without a
  semantic distinction is the "Python with intent annotations" drift.
- The pattern GPT-5.4 wanted is expressible today by splitting
  `greet_by_time` into multiple candidates.

*What does change.* The documentation. An agent that hits this
confusion should be redirected to candidate dispatch by an error
message that names the right idiom. Error text addition, no parser
change.

### 5. Ship a separate `str_reverse` primitive. **NO.**

Covered by decision 2. Polymorphic `reverse` serves the same need
without expanding the primitive surface.

### 6. Ship an agent quick-reference. **YES.**

*The issue.* Every review asked for it. Two of four said it in
exactly those words.

*Why yes.*
- The manifest is the authoritative interface, but it's machine-shaped.
  Agents can consume it, but they won't read it first unless prompted.
  `docs/FOR_AGENTS.md` prompts them correctly; the quickref backs that
  up with a 1-page distilled view of "things you will want that are
  named differently than you think."
- Maintaining a quickref as a second source of truth risks drift. I
  mitigate by generating it from the manifest where possible and
  annotating the hand-written rules explicitly.

*What it is.* `docs/AGENT_QUICKREF.md`. One page. Columns: "you want to
do X" → "the Codifide primitive is Y" → "one-line example". Plus a
section on surface forms that don't work the way agents expect.

### 7. Fix error messages for the three known misses (`%`, `str.reverse`, `clock.hour`). **YES.**

*The issue.* When an agent guesses, the current errors are
uninformative. `AttributeError` on one; `unknown callable: 'str.reverse'`
on another; `unbound name: 'hour'` on the third (after a bind of a
non-existent primitive).

*Why yes.*
- These three are not speculative. They are the three misses two
  independent agents made on first contact. Adding one sentence of
  hint each converts a guess-and-recover loop into a guess-and-learn
  one.
- The hints don't hide the underlying error; they annotate it.

*What it changes.* The `unknown callable` message for a handful of
specific names (`str.reverse`, `clock.hour`, `str.upper`,
`str.lower`, `str.split`, etc.) names the correct form. The `%`
lexer path produces a `ParseError` naming `mod`. No behavior change;
only better failure mode.

### 8. Address Gemini's `palindrome.cod` and `classify_numeric.cod` as regression tests. **YES.**

Both programs will be committed verbatim as regression fixtures
under `tests/` after the parser fix lands. They document the
specific failure mode that drove decision 1.

## What I did not yet decide

- Whether to adjust `docs/LANGUAGE.md` to explicitly admit
  multi-line expressions in the surface grammar, or just implement
  it and let the spec catch up. Leaning toward spec update paired
  with the parser change, because spec-implementation drift is
  already an open audit sensitivity.
- Whether to write a second-wave external-model test after shipping
  the quickref, to measure whether discoverability actually
  improved. Not in this session; maybe the next.

## What I'm not yet sure of

Whether the quickref alone moves the needle, or whether agents still
guess before reading anything. The only honest way to find out is to
hand a fresh agent the repo and watch what happens. This session
ships the fixes and the document; verification is future work.
