# Codifide — Agent Quick Reference

One-page cross-reference for agents writing Codifide on first contact.
The **capability manifest** (`python3 -m codifide capability`) is the
authoritative interface; this page is a distillation intended to
short-circuit the most common first-miss patterns.

If anything here disagrees with the manifest, the manifest wins and
this file is the bug.

## Before you write a single line

Run this first:

```bash
python3 -m codifide capability --hash
```

That identity is the language's interface. If you plan to write more
than one program against it, also run `python3 -m codifide capability`
and keep the output open in another window.

## Things agents reach for that don't exist

Four external model reviews on 2026-05-11 converged on the same
misses. Here is the table.

| You'll reach for | Codifide has | One-liner |
|---|---|---|
| `a % b` | `mod(a, b)` | `eq(mod(n, 2), 0)` |
| `a + b` (numbers) | `add(a, b)` | `add(x, 1)` |
| `a - b` (numbers) | `sub(a, b)` | `sub(x, 1)` |
| `a * b` | `mul(a, b)` | `mul(price, qty)` |
| `a / b` | `div(a, b)` | `div(sum(xs), len(xs))` |
| `str.reverse(s)` | `reverse(s)` | `reverse` is polymorphic over strings and lists |
| `str.upper(s)` | `upper(s)` | `upper(trim(name))` |
| `str.lower(s)` | `lower(s)` | `lower(code)` |
| `str.split(s, sep)` | `split(s, sep)` | `split("a,b,c", ",")` |
| `str.replace(s, a, b)` | `replace(s, a, b)` | `replace(text, "fox", "***")` |
| `list.reverse(xs)` | `reverse(xs)` | same primitive as string reverse |
| `list.append(xs, x)` | `append(xs, x)` | returns a new list; does not mutate |
| `list.sum(xs)` | `sum(xs)` | `sum([1,2,3])` → `6` |
| `clock.hour` | `clock.now.hm` | `clock.now` returns `{hm: "14:05", unix: …}` |
| `clock.minute` | `clock.now.hm` | split `hm` on `:` if you need a number |
| inline `if` / `when` statement | multiple `cand` blocks with `when` guards | see `examples/ai_generated/classify_numeric.cod` |

The comparison operators `<`, `<=`, `==`, `!=`, `>`, `>=` **do** work
as infix inside expressions. They desugar to `lt`, `le`, `eq`, `ne`,
`gt`, `ge` before the canonical form. Arithmetic operators do not get
the same treatment — arithmetic is always through named primitives.

## Canonical primitive groups

### Arithmetic
`add sub mul div mod neg abs pow floor ceil round min max`

`min` and `max` are two-arg. Use `min_of` / `max_of` on a list.

### Comparison (pure)
`eq ne lt le gt ge`

Also available as infix: `==`, `!=`, `<`, `<=`, `>`, `>=`.

### Boolean (pure)
`and or not` — variadic `and`/`or` accept any number of args.

### Collections (pure)
`len list head tail reverse append contains_item is_sorted is_permutation sum min_of max_of`

### Strings (pure)
`upper lower trim starts_with ends_with contains replace split join str reverse slice at char_at indexof`

`reverse`, `slice`, and `at` work on both strings and lists.
`char_at` is string-only. `indexof` returns `-1` when not found.
`str` converts any value to its string form.

**`contains` is case-sensitive.** `contains("Hello", "hello")` is `false`.
Normalize first: `contains(lower(msg), "keyword")`.

### Confidence (pure)
`conf belief` — `belief(value, 0.85)` wraps a value with a confidence
score; `conf(x)` reads it. Use these to feed a `believe` block.

### I/O (`{io.stdout}`)
`io.say(msg)` — print and return the message as a string.

### Clock (`{clock.read}`)
`clock.now` — returns a record with `hm` (string `"HH:MM"`) and
`unix` (float seconds since epoch).

### Vision (`{model.vision}`, stubbed in v0)
`vision.classify(img)` — returns a `Belief` over a label.
`escalate(img, label)` — escalation path used in belief dispatch.

### Host bridges (pure)
`host_sorted host_image` — trusted escape hatches for things the
language does not want to reimplement.

## Inline conditional

`if cond then a else b` as an expression. Short-circuit — exactly
one branch evaluates. This is the tool for "choose between two
values in an expression." For "choose between two function
bodies," reach for candidate dispatch instead.

```codifide
cand
  if lt(n, 0) then neg(n) else n
```

Unlike candidate dispatch guards, the un-taken branch is never
evaluated, so it's safe to put an expression there that would
raise if the condition pointed the other way:

```codifide
cand
  if gt(len(s), 0) then char_at(s, 0) else ""
```

## Cost-annotated candidate dispatch

Added 2026-05-11. A candidate can declare a `cost` — a non-negative
integer — that tells the dispatcher how expensive this candidate is
relative to others. Among candidates whose guards hold, the
dispatcher picks the cheapest one.

```codifide
def classify
  intent "label using the cheapest sufficient path"
  sig    (n: Int) -> String
  effects {}

  cand
    intent "fast path for zero"
    cost   1
    when   eq(n, 0)
    "zero"

  cand
    intent "small numbers"
    cost   10
    when   lt(n, 10)
    "small"

  cand
    intent "fallback"
    cost   100
    "large"
```

Rules:

- `cost <non-negative-integer>` inside a `cand` block, between
  `intent` and `when` (any order accepted).
- A candidate without `cost` has effective cost +∞ — it wins only
  when no costed candidate is satisfied. Un-annotated modules
  dispatch in declaration order, identical to pre-amendment.
- The dispatcher does not fall through on `bottom`. If the
  cheapest candidate's body returns `bottom`, the refusal escapes;
  the next-cheapest candidate is not tried. If you want multi-tier
  fallback, compose it explicitly with `believe` or by splitting
  into multiple `def`s.
- Adding a single `cost` annotation to a multi-candidate module
  changes the dispatch semantics for that definition. If you want
  declaration-order behavior preserved, annotate every candidate.

## Idioms

**Parity.**
```codifide
def is_even
  intent "parity"
  sig    (n: Int) -> Bool
  effects {}
  cand
    eq(mod(n, 2), 0)
```

**Normalize a string.**
```codifide
def normalize
  intent "trim and uppercase"
  sig    (s: String) -> String
  effects {}
  pre    ne(s, "")
  post   eq(result, upper(trim(s)))
  cand
    upper(trim(s))
```

**Arithmetic mean.**
```codifide
def average
  intent "arithmetic mean"
  sig    (xs: List) -> Number
  effects {}
  pre    gt(len(xs), 0)
  cand
    div(sum(xs), len(xs))
```

**Conditional dispatch (Codifide's `if`).**
```codifide
def classify
  intent "label a number"
  sig    (n: Number) -> String
  effects {}
  cand
    intent "low"
    when   lt(n, 10)
    "low"
  cand
    intent "high"
    "high"
```

**Multi-branch value routing.**

Use `cand` + `when` guards when each branch is a distinct decision path
(idiomatic, shows intent per branch):

```codifide
def route
  intent "route by label"
  sig    (label: String) -> String
  effects {}
  cand
    intent "unsafe goes to blocked"
    when   eq(label, "unsafe")
    "blocked"
  cand
    intent "safe goes to approved"
    when   eq(label, "safe")
    "approved"
  cand
    intent "anything else escalates"
    "escalate-to-human"
```

Use `if/then/else` when you need to choose between two values inline
within a single candidate body:

```codifide
cand
  if eq(label, "unsafe") then "blocked" else "approved"
```

Both patterns are valid. `cand` + `when` is preferred for three or more
branches; `if/then/else` is preferred for binary choices inside a body.

**`is_bottom` — value inspector, not propagation catcher.**

`is_bottom(x)` returns `true` when `x` is a literal `bottom` value.
It **cannot** catch a `bottom` that propagated through a bind:

```codifide
# WRONG — bottom propagates through the bind before is_bottom sees it
cand
  r <- function_that_refuses()
  if is_bottom(r) then "caught" else r   # raises BottomPropagationError

# RIGHT — use a believe arm to handle propagated bottom
cand
  r <- function_that_refuses()
  believe r
    ge(conf(r), 0.70) => r
    else              => bottom          # or handle the refusal here
```

`is_bottom` is useful when `bottom` is passed as an explicit argument
or stored in a data structure, not when it arrives via function return.

## Content-addressed imports

Individual symbol imports bring one symbol into scope by name:

```codifide
import classify_content = sha256:<hash>
```

**Important:** individual imports do not carry transitive dependencies.
If `route_message` calls `moderate` internally, you must also import
`moderate` explicitly — or use an index.

The idiomatic pattern for multi-symbol composition is an **index**:

```bash
# Publish symbols
python3 -m codifide store put module_a.cod
python3 -m codifide store put module_b.cod

# Bundle into an index
python3 -m codifide store index --name my_lib \
  "symbol_a=sha256:<hash-a>" \
  "symbol_b=sha256:<hash-b>"
# → prints: sha256:<index-hash> my_lib
```

Then from-import the whole bundle:

```codifide
from sha256:<index-hash> import symbol_a, symbol_b
```

**Runtime note:** `from`-imports require a store to be available at parse time.
Pass `--store <path>` to the Rust runtime (default store: `~/.codifide/store`),
or use `CODIFIDE_RUNTIME=python` for the Python reference runtime. Both runtimes
support `from`-import as of v2.0.

## Surface rules that surprised other agents

- **Every `def` must declare `intent`.** The parser rejects
  definitions without it. This is not a style preference; it is the
  language's core feature.
- **Every `def` must declare `effects`.** Use `effects {}` for pure
  functions. Calling an effectful primitive without declaring the
  effect is a module-load error, not a runtime error.
- **`believe` blocks require `else => ...`.** Partial dispatch is a
  parse error. To refuse below threshold, write `else => bottom`.
- **Contracts run pure.** Pre, post, and `when` guards evaluate with
  an empty effect budget. A postcondition cannot call `io.say` even
  if the surrounding function is allowed to.
- **`when` guards execute before the candidate body.** A bind (`<-`)
  is part of the body — the bound name does not exist yet when `when`
  runs. This pattern fails:

  ```codifide
  cand
    label <- moderate(message)   # body — runs after guard
    when   eq(label, "unsafe")   # guard — runs first; label unbound
    "blocked"
  ```

  Error: `unknown callable: 'label'`. Fix: move the bind into the body
  and use `if/then/else` to route on the result:

  ```codifide
  cand
    label <- moderate(message)
    if eq(label, "unsafe") then "blocked"
    else if eq(label, "safe") then "approved"
    else "escalate-to-human"
  ```

- **`bottom` propagates.** A `bottom` that escapes a top-level call
  raises `RefusalError`. Handle it in a `believe` arm or accept the
  refusal. `is_bottom()` cannot catch a propagated `bottom` — see
  the `is_bottom` note in Idioms above.
- **Multi-line expressions are fine.** Call arguments, bind
  right-hand sides, and contract expressions may span multiple
  physical lines as long as brackets are balanced at the end.

## When the parser or runtime rejects you

Codifide errors are typed and come from a closed set of eight classes.
Several of them now include one-line hints for common-guess misses:

- `ParseError: unexpected character '%' ... hint: use mod(a, b)` —
  reach for the named primitive.
- `CodifideError: unknown callable: 'str.reverse' ... hint: use reverse(s)` —
  the primitive exists, just not under that name.
- `CodifideError: unbound name: 'hour' ... hint: time is read via clock.now` —
  the field you want is on the record that `clock.now` returns.

If you see an error without a hint and the fix is not obvious from
the manifest, that's signal worth filing: copy
`dispatches/feedback/TEMPLATE.md` into `dispatches/feedback/` with
your experience and recommend either a hint addition or a spec
tightening.

## One more time — the entry point

```bash
python3 -m codifide capability
```

Read it. Write the program. The language will meet you where you land
if you land where the manifest points.
