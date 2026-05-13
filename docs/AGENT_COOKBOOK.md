# Codifide — Agent Cookbook

Failure modes observed across five external agent sessions (four v1.0 reviews
on 2026-05-11, three Track 1 case studies on 2026-05-13). Each entry follows
the same shape: what the agent intended → what they tried → what actually works
→ a working example.

If you are reading this before writing code, skim the headings. If you are
reading this because something failed, find the error message in the entries
below.

The **capability manifest** is still the authoritative interface:

```bash
python3 -m codifide capability
# or from the web, no install required:
# curl https://www.codifide.com/capability.json
```

This cookbook is a shortcut, not a replacement.

---

## 1. Arithmetic operators don't exist as infix

**Intention:** compute `n % 2`, `a + b`, `a - b`, `a * b`, `a / b`

**What agents try:** `n % 2 == 0`, `price + tax`, `x - 1`

**Error:** `ParseError: unexpected character '%' ... hint: use mod(a, b)`

**What works:** named primitives for all arithmetic

```codifide
def is_even
  intent "parity check"
  sig    (n: Int) -> Bool
  effects {}
  cand
    eq(mod(n, 2), 0)

def total
  intent "price plus tax"
  sig    (price: Number, tax: Number) -> Number
  effects {}
  cand
    add(price, tax)
```

**Why:** Codifide exposes arithmetic as named primitives, not infix operators.
Comparison operators (`<`, `<=`, `==`, `!=`, `>`, `>=`) do work as infix —
they desugar to `lt`, `le`, `eq`, `ne`, `gt`, `ge`. Arithmetic does not get
the same treatment.

**Quick table:**

| You'll reach for | Use instead |
|---|---|
| `a + b` | `add(a, b)` |
| `a - b` | `sub(a, b)` |
| `a * b` | `mul(a, b)` |
| `a / b` | `div(a, b)` |
| `a % b` | `mod(a, b)` |
| `abs(x)` | `abs(x)` ✅ (this one works) |

---

## 2. String and list operations are top-level primitives, not methods

**Intention:** reverse a string, uppercase a string, split on a delimiter

**What agents try:** `str.reverse(s)`, `s.upper()`, `string.split(s, ",")`

**Error:** `CodifideError: unknown callable: 'str.reverse' ... hint: use reverse(s)`

**What works:** top-level primitives

```codifide
def normalize
  intent "trim and uppercase"
  sig    (s: String) -> String
  effects {}
  cand
    upper(trim(s))

def words
  intent "split a sentence into words"
  sig    (s: String) -> List
  effects {}
  cand
    split(s, " ")

def reversed_str
  intent "reverse a string"
  sig    (s: String) -> String
  effects {}
  cand
    reverse(s)
```

**Why:** Codifide has no method dispatch. Every operation is a named primitive.
`reverse` is polymorphic — it works on both strings and lists.

**Quick table:**

| You'll reach for | Use instead |
|---|---|
| `str.reverse(s)` | `reverse(s)` |
| `str.upper(s)` | `upper(s)` |
| `str.lower(s)` | `lower(s)` |
| `str.trim(s)` | `trim(s)` |
| `str.split(s, sep)` | `split(s, sep)` |
| `str.replace(s, a, b)` | `replace(s, a, b)` |
| `str.contains(s, x)` | `contains(s, x)` |
| `list.append(xs, x)` | `append(xs, x)` — returns new list, does not mutate |
| `list.reverse(xs)` | `reverse(xs)` |
| `list.sum(xs)` | `sum(xs)` |
| `list.len(xs)` | `len(xs)` |

---

## 3. `contains` is case-sensitive — normalize first

**Intention:** check if a message contains a keyword regardless of case

**What agents try:** `contains(message, "spam")`

**What happens:** works for lowercase input, silently fails for `"SPAM"` or `"Spam"`

**What works:** normalize with `lower()` first

```codifide
def classify_content
  intent "label a message by keyword"
  sig    (message: String) -> Label
  effects {}
  cand
    intent "unsafe — spam detected"
    when   contains(lower(message), "spam")
    belief("unsafe", 0.90)
  cand
    intent "fallback"
    belief("uncertain", 0.75)
```

**Why:** `contains(s, needle)` is a substring check. It is case-sensitive.
`lower(s)` normalizes to lowercase before the check. Always use
`contains(lower(s), "keyword")` for keyword matching.

---

## 4. Time is read via `clock.now`, not `clock.hour`

**Intention:** get the current hour or minute

**What agents try:** `clock.hour`, `clock.minute`, `now.hour`

**Error:** `CodifideError: unbound name: 'hour' ... hint: time is read via clock.now`

**What works:** `clock.now` returns a record with `hm` (string `"HH:MM"`) and
`unix` (float seconds since epoch)

```codifide
def greet_by_time
  intent "greet based on time of day"
  sig    () -> String
  effects {clock.read}
  cand
    t <- clock.now
    if lt(head(split(t.hm, ":")), 12) then "Good morning" else "Good afternoon"
```

**Why:** Codifide has no `clock.hour` primitive. `clock.now` returns a record.
Access the `hm` field and split on `":"` if you need a numeric hour.

---

## 5. `believe` blocks require `else` — and `else => bottom` is the right refusal

**Intention:** gate on confidence, refuse if too low

**What agents try:** `believe result ge(conf(result), 0.85) => result` (no else)

**Error:** `ParseError: believe block requires else arm`

**What works:**

```codifide
def label_or_refuse
  intent "label or refuse when confidence is too low"
  sig    (img: Image) -> Label
  effects {model.vision}
  cand
    result <- vision.classify(img)
    believe result
      ge(conf(result), 0.85) => result
      else                   => bottom
```

**Why:** Partial belief dispatch is a parse error. The `else` arm is required.
`else => bottom` is the idiomatic refusal — it propagates the refusal to the
caller, who must handle it in their own `believe` arm or accept `RefusalError`.

---

## 6. `is_bottom()` cannot catch propagated `bottom`

**Intention:** check if a function refused before routing on its result

**What agents try:**
```codifide
cand
  r <- function_that_may_refuse()
  if is_bottom(r) then "refused" else r
```

**Error:** `BottomPropagationError: primitive 'is_bottom' received ⊥`

**Why it fails:** `bottom` propagates through the bind (`<-`) before
`is_bottom()` can inspect it. The bind raises `BottomPropagationError`
immediately.

**What works:** use a `believe` arm to handle propagated `bottom`

```codifide
cand
  r <- function_that_may_refuse()
  believe r
    ge(conf(r), 0.70) => r
    else              => bottom   # or handle the refusal here
```

**When `is_bottom()` IS useful:** when `bottom` is passed as an explicit
argument or stored in a data structure — not when it arrives via function
return propagation.

```codifide
# This works — bottom is a literal argument
cand
  is_bottom(bottom)   # returns true
```

---

## 7. Bind-before-when: guards execute before candidate bodies

**Intention:** bind a result, then dispatch on it with `when` guards

**What agents try:**
```codifide
cand
  label <- moderate(message)
  when   eq(label, "unsafe")
  "blocked"
```

**Error:** `unbound name: 'label' ... hint: if 'label' is a name you intended
to bind with '<-', note that 'when' guards execute before the candidate body`

**Why it fails:** `when` guards are evaluated before the candidate body runs.
The bind (`<-`) is part of the body — `label` doesn't exist yet when the
guard runs.

**What works:** bind in the body, route with `if/then/else`

```codifide
def route_message
  intent "route a message to blocked, approved, or escalate-to-human"
  sig    (message: String) -> Decision
  effects {}
  cand
    label <- moderate(message)
    if eq(label, "unsafe") then "blocked"
    else if eq(label, "safe") then "approved"
    else "escalate-to-human"
```

**When to use `cand` + `when` vs `if/then/else`:**
- `cand` + `when`: three or more branches, each representing a distinct
  decision path. Shows intent per branch. Idiomatic for multi-branch dispatch.
- `if/then/else`: binary choices inside a single candidate body, or when
  you need to route on a value you just bound.

---

## 8. Content-addressed imports require an index for transitive dependencies

**Intention:** import a function that depends on other functions

**What agents try:**
```codifide
import route_message = sha256:<hash>
```

**Error:** `CodifideError: unknown callable: "moderate"` (or whichever
transitive dependency is missing)

**Why it fails:** individual `import` statements bring one symbol into scope.
They do not carry transitive dependencies. If `route_message` calls `moderate`
internally, `moderate` must also be in scope.

**What works:** publish all symbols, create an index, `from`-import the bundle

```bash
# Publish all symbols
python3 -m codifide store put my_module.cod

# Bundle into an index
python3 -m codifide store index --name my_lib \
  "classify_content=sha256:<hash>" \
  "moderate=sha256:<hash>" \
  "route_message=sha256:<hash>"
# → prints: sha256:<index-hash> my_lib
```

```codifide
from sha256:<index-hash> import classify_content, moderate, route_message
```

**Runtime note:** `from`-imports require the Python runtime in v2.0:

```bash
CODIFIDE_RUNTIME=python python3 -m codifide run my_program.cod
```

The Rust parser does not yet support `from`-import syntax. Individual
`import name = sha256:<hash>` works in both runtimes but does not carry
transitive dependencies.

---

## 9. Every `def` must declare `intent`, `sig`, and `effects`

**Intention:** write a function

**What agents try:** omitting `intent`, or omitting `effects`

**Error (missing intent):** `ParseError: expected 'intent' after 'def <name>'`

**Error (missing effects):** `EffectViolation: '<name>' performed effect
'io.stdout' which is not in its declared set {}`

**What works:**

```codifide
def my_function
  intent "what this function decides"   # required — not optional
  sig    (x: String) -> String          # required
  effects {}                            # required — use {} for pure functions
  cand
    x
```

**Why:** `intent` is the language's core feature — it is not a comment, it is
a first-class artifact. The parser rejects definitions without it. `effects`
is the effect declaration — use `effects {}` for pure functions, `effects
{io.stdout}` for functions that print, etc. The runtime enforces effects
transitively: if you call an effectful function, your caller must also declare
that effect.

---

## 10. `belief(...)` return type is advisory, not enforced

**Intention:** return a confidence-annotated value from a function declared
`-> Label`

**What agents wonder:** "I declared `-> Label` but I'm returning
`belief("unsafe", 0.90)` which the manifest says returns `Any`. Will this fail?"

**Answer:** No. Return types in signatures are advisory — the runtime does not
enforce them against belief wrappers. `belief(value, confidence)` wraps any
value; the declared return type is documentation for callers, not a checked
constraint.

```codifide
def classify
  intent "label with confidence"
  sig    (msg: String) -> Label   # advisory — belief("unsafe", 0.90) is fine here
  effects {}
  cand
    when contains(lower(msg), "spam")
    belief("unsafe", 0.90)        # returns Any in the manifest — that's correct
  cand
    belief("uncertain", 0.75)
```

**Why:** Codifide does not yet have a type checker. The `sig` declaration is
read by callers and by the capability manifest; it is not enforced at runtime.
This is a known limitation tracked for v2.0.

---

## Quick diagnostics

| Error | Likely cause | See entry |
|---|---|---|
| `ParseError: unexpected character '%'` | Infix arithmetic | #1 |
| `unknown callable: 'str.reverse'` | Method-shaped name | #2 |
| `unknown callable: 'str.upper'` | Method-shaped name | #2 |
| `unbound name: 'hour'` | `clock.hour` doesn't exist | #4 |
| `ParseError: believe block requires else arm` | Missing `else` | #5 |
| `BottomPropagationError: primitive 'is_bottom' received ⊥` | `is_bottom` on propagated bottom | #6 |
| `unbound name: '<name>' ... hint: if '<name>' is a name you intended to bind` | Bind before when guard | #7 |
| `unknown callable: '<function-name>'` after import | Transitive dependency missing | #8 |
| `ParseError: expected 'intent'` | Missing `intent` on `def` | #9 |
| `EffectViolation: performed effect ... not in declared set` | Missing effect declaration | #9 |
| `parse error: from-import ... not yet supported in the Rust parser` | Need Python runtime | #8 |

---

*Cookbook version 1.0 — May 2026*  
*Derived from: 2026-05-11 four-model review, 2026-05-13 Track 1 case studies*  
*Maintained by: Douglas Jones + Claude*
