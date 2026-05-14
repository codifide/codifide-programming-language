# GPT-4o Session Prompt — T1-2 (updated for v3.0)
# Paste everything below this line as your first message.
# ─────────────────────────────────────────────────────────────────────────────

You are a fresh agent encountering the Codifide programming language for the
first time. You have no prior knowledge of it. Your job is to complete five
programs using only the context provided below.

**Document every failure and fix as you go:**
1. First attempt — paste the code you wrote before running it
2. First error — exact error message if it failed
3. Fix — what you changed and why
4. Final working code — the version that ran
5. Surprises — anything the language did that you did not expect

First-attempt successes are signal too — note them.

The interpreter command is: `python3 -m codifide run <file.cod>`
Run each program before moving to the next.

---

## RESOURCE 1 — Onboarding guide (FOR_AGENTS.md)

# Codifide — onboarding for agents

If you are an agent encountering Codifide for the first time, this is the
fastest path to understanding. It is not a tutorial. It is a set of
pointers into documents and code, in the order a reader with finite
context should consume them.

## 60 seconds

Read the capability manifest below — it describes every AST node kind,
every primitive (with effects and return types), every typed error, and
the surface keyword table. One document, content-addressable, generated
from the implementation so it cannot lie.

The manifest is also available at a stable public URL — no repo clone required:

```bash
curl https://www.codifide.com/capability.json   # JSON form
curl https://www.codifide.com/capability.cbor   # CBOR form (RFC 8949)
```

For a one-page distilled cross-reference of the primitive surface and the
common-guess pitfalls, read RESOURCE 2 (AGENT_QUICKREF.md).

If you have the interpreter available, run this for a zero-to-running-program
quickstart:

```bash
python3 -m codifide agent-quickstart
```

## Writing your first Codifide program

Five things to know before you write a single line:

- `belief(value, confidence)` goes at the end of a `cand` body, not
  wrapped in anything. It is the idiomatic way to return a
  confidence-annotated value.
- `effects {}` on anything that can possibly be pure. The runtime
  enforces it transitively, so any lie gets caught at module load.
- `intent` strings name the *choice* the candidate represents, not
  the implementation. "tiny input fast path," not "returns
  insertion-sorted xs."
- `believe` thresholds are `ge(conf(x), 0.85)`, `ge(conf(x), 0.60)`
  as two-tier gates — confident, escalate, refuse — rather than a
  single hard cutoff.
- `else => bottom` when a `believe` block has no confident path.
  Refusal is the language's preferred default over a low-confidence
  guess.

## One expectation

Codifide was designed for you — an agent, not a human. The intent is
first-class. The effects are checked. The refusals are structured.
If the language makes *less* sense to you than it should, that is
feedback the project needs more than anything else.

---

## RESOURCE 2 — Quick reference (AGENT_QUICKREF.md)

# Codifide — Agent Quick Reference

## Things agents reach for that don't exist

| You'll reach for | Codifide has | One-liner |
|---|---|---|
| `a % b` | `mod(a, b)` | `eq(mod(n, 2), 0)` |
| `a + b` (numbers) | `add(a, b)` | `add(x, 1)` |
| `a - b` (numbers) | `sub(a, b)` | `sub(x, 1)` |
| `a * b` | `mul(a, b)` | `mul(price, qty)` |
| `a / b` | `div(a, b)` | `div(sum(xs), len(xs))` |
| `str.reverse(s)` | `reverse(s)` | polymorphic over strings and lists |
| `str.upper(s)` | `upper(s)` | `upper(trim(name))` |
| `str.lower(s)` | `lower(s)` | `lower(code)` |
| `str.split(s, sep)` | `split(s, sep)` | `split("a,b,c", ",")` |
| `str.replace(s, a, b)` | `replace(s, a, b)` | `replace(text, "fox", "***")` |
| `list.reverse(xs)` | `reverse(xs)` | same primitive as string reverse |
| `list.append(xs, x)` | `append(xs, x)` | returns a new list; does not mutate |
| `list.sum(xs)` | `sum(xs)` | `sum([1,2,3])` → `6` |
| `clock.hour` | `clock.now.hm` | `clock.now` returns `{hm: "14:05", unix: …}` |
| `clock.minute` | `clock.now.hm` | split `hm` on `:` if you need a number |
| inline `if` / `when` statement | multiple `cand` blocks with `when` guards | see idioms below |

The comparison operators `<`, `<=`, `==`, `!=`, `>`, `>=` **do** work
as infix inside expressions. Arithmetic operators do not — always use
named primitives.

## Canonical primitive groups

### Arithmetic
`add sub mul div mod neg abs pow floor ceil round min max`

### Comparison (pure)
`eq ne lt le gt ge` — also available as infix `==`, `!=`, `<`, `<=`, `>`, `>=`

### Boolean (pure)
`and or not` — variadic

### Collections (pure)
`len list head tail reverse append contains_item is_sorted is_permutation sum min_of max_of`

### Strings (pure)
`upper lower trim starts_with ends_with contains replace split join str reverse slice at char_at indexof`

**`contains` is case-sensitive.** Always normalize first:
`contains(lower(msg), "keyword")`

### Confidence (pure)
`conf belief` — `belief(value, 0.85)` wraps a value with a confidence score;
`conf(x)` reads it.

### I/O (`{io.stdout}`)
`io.say(msg)` — print and return the message as a string.

**Double-print note:** `io.say` prints to stdout *and* returns the message as
a string. If `main` returns that string, the CLI also prints the return value.
Programs that call `io.say` in `main` will print twice — once from `io.say`
and once from the CLI. This is expected behavior.

## Inline conditional

`if cond then a else b` as an expression. Short-circuit — exactly one branch
evaluates.

```
cand
  if gt(len(s), 0) then char_at(s, 0) else ""
```

## Cost-annotated candidate dispatch

```
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
    intent "fallback"
    cost   100
    "large"
```

## Idioms

**Confidence-gated refusal:**
```
def label
  intent "label or refuse"
  sig    (img: Image) -> Label
  effects {model.vision}
  cand
    result <- vision.classify(img)
    believe result
      ge(conf(result), 0.85) => result
      else                   => bottom
```

**Conditional dispatch:**
```
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

## Multi-branch routing

Use `cand` + `when` for three or more branches (idiomatic):

```
def route
  intent "route by label"
  sig    (label: String) -> String
  effects {}
  cand
    intent "unsafe"
    when   eq(label, "unsafe")
    "blocked"
  cand
    intent "safe"
    when   eq(label, "safe")
    "approved"
  cand
    intent "fallback"
    "escalate-to-human"
```

Use `if/then/else` for binary choices inside a single candidate body.

## `is_bottom` — value inspector only

`is_bottom(x)` works on literal `bottom` values (with or without a reason string). It **cannot** catch
a `bottom` that propagated through a bind — that raises
`BottomPropagationError` before `is_bottom` sees it.

```
# WRONG
cand
  r <- function_that_refuses()
  if is_bottom(r) then "caught" else r   # BottomPropagationError

# RIGHT — use believe to handle propagated bottom
cand
  r <- function_that_refuses()
  believe r
    ge(conf(r), 0.70) => r
    else              => bottom
```

**Direct-call `is_bottom` works.** If you need to check whether a function
refuses *before* binding its result, call `is_bottom` directly on the call
expression — no bind needed:

```
# Works — is_bottom sees the value before any bind propagates it
cand
  if is_bottom(moderate(message)) then "refused" else moderate(message)
```

This short-circuits: if `moderate` refuses, the `else` branch never runs.
Note that `moderate` is called twice — once for the check and once for the
value. For expensive functions, prefer the `believe` pattern instead.

## Surface rules that surprised other agents

- **Every `def` must declare `intent`.** The parser rejects definitions without it.
- **Every `def` must declare `effects`.** Use `effects {}` for pure functions.
- **`believe` blocks require `else => ...`.** Partial dispatch is a parse error.
- **Contracts run pure.** Pre, post, and `when` guards cannot call effectful primitives.
- **`when` guards execute before the candidate body.** A bind (`<-`) is part of the body — the bound name doesn't exist yet when `when` runs. This fails:
  ```
  cand
    label <- moderate(message)   # body — runs after guard
    when   eq(label, "unsafe")   # guard — runs first; label unbound
    "blocked"
  ```
  Error: `unknown callable: 'label'`. Fix: single cand, bind in body, `if/then/else` to route.
- **`bottom` propagates.** An unhandled `bottom` raises `RefusalError`.
- **`bottom "reason"` (v3.0).** `bottom` accepts an optional string payload: `bottom "confidence below threshold"`. The reason is propagated through `RefusalError` for diagnostics. Bare `bottom` still works — the reason is optional.
- **`believe` arm values may be on the same line as `=>` or on the next indented line (v3.0+).** Both forms work.
- **Multi-line expressions are fine** as long as brackets are balanced.
- **Bind-before-when is now a parse error (v2.0).** The parser catches it at
  parse time and emits a `ParseError` with a one-line fix hint. You will not
  see the confusing runtime error anymore.

## Content-addressed imports

Individual symbol imports do not carry transitive dependencies. If
`route_message` calls `moderate` internally, you must also import `moderate`
explicitly — or use an index.

```
import classify_content = sha256:<hash>
import moderate         = sha256:<hash>
import route_message    = sha256:<hash>
```

Both runtimes support `from`-import as of v2.0:

```
from sha256:<index-hash> import symbol_a, symbol_b
```

**RPC API (v2.0+):** You can also publish and retrieve symbols via HTTP instead
of the CLI ceremony. Start the server with `python3 -m codifide serve`, then
`POST /symbols` with the canonical form to get back a content identity. See
`docs/RPC_API.md` for the full workflow.

**Remote symbol resolution (v3.0):** Push a local symbol to a remote registry
and resolve it from any machine:

```bash
# Push to a remote registry
python3 -m codifide store push sha256:<hash> --registry https://registry.example.com

# Run with remote resolution enabled
python3 -m codifide run pipeline.cod --registry https://registry.example.com

# Start a read-only public registry server
python3 -m codifide serve --read-only
```

---

## RESOURCE 3 — Capability manifest

Manifest identity: `sha256:d900fe7e6d91300424b226cda0fd404bf281c4362a70131dbec116548b310ff2`

```json
{
  "codifide_capability": "0.1",
  "codifide_schema": "0.1",
  "generator": "codifide-python-3.0.0",
  "docs": {
    "capability": "https://codifide.com/capability.json",
    "capability_cbor": "https://codifide.com/capability.cbor",
    "cookbook": "https://codifide.com/docs/AGENT_COOKBOOK.md",
    "for_agents": "https://codifide.com/docs/FOR_AGENTS.md",
    "quickref": "https://codifide.com/docs/AGENT_QUICKREF.md"
  },
  "literal_types": ["Any","Bool","Clock","Float","Image","Int","Label","List","Number","String","Unit"],
  "effects": ["clock.read","io.stdout","model.vision"],
  "errors": [
    {"name": "CodifideError",       "fatal": false, "when": "Base class. Not raised directly."},
    {"name": "ParseError",          "fatal": true,  "when": "Surface syntax does not parse."},
    {"name": "EffectViolation",     "fatal": true,  "when": "Primitive effect not in budget."},
    {"name": "ContractViolation",   "fatal": true,  "when": "Pre or post clause did not hold."},
    {"name": "DispatchError",       "fatal": true,  "when": "No candidate guard matched."},
    {"name": "RefusalError",        "fatal": true,  "when": "bottom escaped with no handler."},
    {"name": "RecursionLimitError", "fatal": true,  "when": "Call depth exceeded."},
    {"name": "PrimitiveError",      "fatal": true,  "when": "Primitive call failed in host."},
    {"name": "BottomPropagationError","fatal": true, "when": "bottom reached a primitive that cannot consume it."}
  ],
  "primitives": [
    {"name": "abs",            "effect": null,          "returns": "Number"},
    {"name": "add",            "effect": null,          "returns": "Number"},
    {"name": "and",            "effect": null,          "returns": "Bool"},
    {"name": "append",         "effect": null,          "returns": "List"},
    {"name": "at",             "effect": null,          "returns": "Any"},
    {"name": "belief",         "effect": null,          "returns": "Any"},
    {"name": "ceil",           "effect": null,          "returns": "Int"},
    {"name": "char_at",        "effect": null,          "returns": "String"},
    {"name": "clock.now",      "effect": "clock.read",  "returns": "Clock"},
    {"name": "conf",           "effect": null,          "returns": "Float"},
    {"name": "contains",       "effect": null,          "returns": "Bool"},
    {"name": "contains_item",  "effect": null,          "returns": "Bool"},
    {"name": "div",            "effect": null,          "returns": "Number"},
    {"name": "ends_with",      "effect": null,          "returns": "Bool"},
    {"name": "eq",             "effect": null,          "returns": "Bool"},
    {"name": "escalate",       "effect": "model.vision","returns": "String"},
    {"name": "floor",          "effect": null,          "returns": "Int"},
    {"name": "ge",             "effect": null,          "returns": "Bool"},
    {"name": "gt",             "effect": null,          "returns": "Bool"},
    {"name": "head",           "effect": null,          "returns": "Any"},
    {"name": "host_image",     "effect": null,          "returns": "Image"},
    {"name": "host_sorted",    "effect": null,          "returns": "List"},
    {"name": "indexof",        "effect": null,          "returns": "Int"},
    {"name": "io.say",         "effect": "io.stdout",   "returns": "String"},
    {"name": "is_bottom",      "effect": null,          "returns": "Bool",
     "note": "Returns true for both bare bottom and bottom with a reason string. Cannot catch a bottom that propagated through a bind."},
    {"name": "is_permutation", "effect": null,          "returns": "Bool"},
    {"name": "is_sorted",      "effect": null,          "returns": "Bool"},
    {"name": "join",           "effect": null,          "returns": "String"},
    {"name": "le",             "effect": null,          "returns": "Bool"},
    {"name": "len",            "effect": null,          "returns": "Int"},
    {"name": "list",           "effect": null,          "returns": "List"},
    {"name": "lower",          "effect": null,          "returns": "String"},
    {"name": "lt",             "effect": null,          "returns": "Bool"},
    {"name": "max",            "effect": null,          "returns": "Number"},
    {"name": "max_of",         "effect": null,          "returns": "Any"},
    {"name": "min",            "effect": null,          "returns": "Number"},
    {"name": "min_of",         "effect": null,          "returns": "Any"},
    {"name": "mod",            "effect": null,          "returns": "Int"},
    {"name": "mul",            "effect": null,          "returns": "Number"},
    {"name": "ne",             "effect": null,          "returns": "Bool"},
    {"name": "neg",            "effect": null,          "returns": "Number"},
    {"name": "not",            "effect": null,          "returns": "Bool"},
    {"name": "or",             "effect": null,          "returns": "Bool"},
    {"name": "pow",            "effect": null,          "returns": "Number"},
    {"name": "replace",        "effect": null,          "returns": "String"},
    {"name": "reverse",        "effect": null,          "returns": "Any"},
    {"name": "round",          "effect": null,          "returns": "Int"},
    {"name": "slice",          "effect": null,          "returns": "Any"},
    {"name": "split",          "effect": null,          "returns": "List"},
    {"name": "starts_with",    "effect": null,          "returns": "Bool"},
    {"name": "str",            "effect": null,          "returns": "String"},
    {"name": "sub",            "effect": null,          "returns": "Number"},
    {"name": "sum",            "effect": null,          "returns": "Number"},
    {"name": "tail",           "effect": null,          "returns": "List"},
    {"name": "trim",           "effect": null,          "returns": "String"},
    {"name": "upper",          "effect": null,          "returns": "String"},
    {"name": "vision.classify","effect": "model.vision","returns": "Label"}
  ],
  "surface_keywords": {
    "keywords": [
      {"canonical": "believe",  "ascii": ["believe"],  "glyphs": ["⊨"]},
      {"canonical": "bottom",   "ascii": ["bottom"],   "glyphs": ["⊥"]},
      {"canonical": "cand",     "ascii": ["cand"],     "glyphs": ["ƒ"]},
      {"canonical": "cost",     "ascii": ["cost"],     "glyphs": []},
      {"canonical": "def",      "ascii": ["def"],      "glyphs": ["≡"]},
      {"canonical": "effects",  "ascii": ["effects"],  "glyphs": ["⚡"]},
      {"canonical": "else",     "ascii": ["else"],     "glyphs": []},
      {"canonical": "intent",   "ascii": ["intent"],   "glyphs": ["⟡"]},
      {"canonical": "post",     "ascii": ["post"],     "glyphs": ["⊣"]},
      {"canonical": "pre",      "ascii": ["pre"],      "glyphs": ["⊢"]},
      {"canonical": "sig",      "ascii": ["sig"],      "glyphs": ["σ"]},
      {"canonical": "when",     "ascii": ["when"],     "glyphs": ["¿"]}
    ],
    "operators": [
      {"canonical": "arm",    "ascii": ["=>"], "glyphs": ["⇒"]},
      {"canonical": "arrow",  "ascii": ["->"], "glyphs": ["→"]},
      {"canonical": "bind",   "ascii": ["<-"], "glyphs": ["←"]},
      {"canonical": "concat", "ascii": ["++"], "glyphs": ["⊕"]}
    ]
  }
}
```

---

## RESOURCE 4 — Task spec (AGENT_TASK_SPEC.md)

# Codifide Agent Task Spec — Content Moderation Pipeline

## What you are being asked to do

Build a working content-moderation pipeline in Codifide. The pipeline
classifies text as safe, unsafe, or uncertain; refuses to classify when
confidence is too low; and escalates uncertain cases to a human-review
queue. Every program you write must run without error using the Codifide
interpreter.

This is not a toy exercise. The pipeline should reflect how you would
actually structure a belief-dispatched classification system in a
language designed for agents.

---

### Program 1 — Keyword classifier

**File:** `content_classifier.cod`

Write a pure function `classify_content` that:
- Takes a `String` message
- Returns a `Label` (`"safe"`, `"unsafe"`, or `"uncertain"`)
- Uses belief dispatch — each candidate returns `belief(label, confidence)`
- Classifies as `"unsafe"` with confidence ≥ 0.90 when the message contains any of: `"spam"`, `"hate"`, `"violence"` (use `lower()` — `contains` is case-sensitive)
- Classifies as `"safe"` with confidence ≥ 0.90 when the message contains `"approved"` or `"verified"` (use `lower()` here too)
- Falls back to `"uncertain"` with confidence 0.75 when no keyword matches

Add a `main` function that calls `classify_content` with a test message of your choice.

**Run it:** `python3 -m codifide run content_classifier.cod`

---

### Program 2 — Confidence-gated refusal

**File:** `moderation_gate.cod`

Write a function `moderate` that:
- Takes a `String` message
- Calls `classify_content` (inline or imported)
- Uses a `believe` block to gate on confidence
- Returns the label when confidence ≥ 0.70
- Returns `bottom` (refuses) when confidence < 0.70
- Declares `effects {}`

Add these two test entry points:

```
def main_unsafe
  intent "test the unsafe path"
  sig    () -> Label
  effects {}
  cand
    moderate("this message contains spam")

def main_uncertain
  intent "test the uncertain path — hello world has no keywords, returns uncertain"
  sig    () -> Label
  effects {}
  cand
    moderate("hello world")
```

**Run it:**
```bash
python3 -m codifide run moderation_gate.cod --entry main_unsafe

# Should return "uncertain" (confidence 0.75 clears the 0.70 gate)
python3 -m codifide run moderation_gate.cod --entry main_uncertain
```

---

### Program 3 — Escalation router

**File:** `escalation_router.cod`

Write a function `route_message` that:
- Takes a `String` message
- Calls `moderate` (inline or imported)
- Returns `"blocked"` when the label is `"unsafe"`
- Returns `"approved"` when the label is `"safe"`
- Returns `"escalate-to-human"` when the label is `"uncertain"`
- Refuses (`bottom`) when `moderate` refuses
- Declares `effects {}`

Add a `main` that calls `route_message` with two test messages.

**Effects reminder:** Check the `effects` declaration on every `def` you write,
including `main`. If `main` calls `io.say` for testing, it must declare
`effects {io.stdout}`. The runtime enforces effect declarations transitively
and raises `EffectViolation` if one is missing — even on a test harness function.

**Run it:** `python3 -m codifide run escalation_router.cod`

---

### Program 4 — Pipeline with I/O

**File:** `moderation_pipeline.cod`

Write a function `run_pipeline` that:
- Takes a `String` message
- Calls `route_message` (inline or imported)
- Uses `io.say` to print the routing decision
- Returns the decision string
- Declares `effects {io.stdout}`

Add a `main` with no arguments that calls `run_pipeline` with a test message.

**Run it:** `python3 -m codifide run moderation_pipeline.cod`

---

### Program 5 — Content-addressed composition

**File:** `pipeline_composed.cod`

```bash
python3 -m codifide store put content_classifier.cod
python3 -m codifide store put escalation_router.cod
python3 -m codifide store hash content_classifier.cod
python3 -m codifide store hash escalation_router.cod
```

Write `pipeline_composed.cod` that imports by hash:

```
import classify_content = sha256:<hash-from-above>
import route_message    = sha256:<hash-from-above>
```

Define a `composed_pipeline` function and a `main` that runs it.

**Run it:** `python3 -m codifide run pipeline_composed.cod`

---

## One note on intent

Every `def` must declare `intent`. The parser rejects definitions without it.
Write it as a decision, not a procedure.

Good: `intent "refuse classification when confidence is too low"`
Not good: `intent "calls classify_content and checks confidence"`

---

## Important note for this session

You cannot actually run the interpreter — you don't have access to the
filesystem or shell. Instead:

1. Write each program as you would if you could run it
2. Reason through what the output would be
3. Identify any errors you think you would hit and how you would fix them
4. Produce the final working version of each program
5. At the end, write the Quill readout and Glyph dispatch as specified

The goal is to see how you reason about the language from the docs alone.
