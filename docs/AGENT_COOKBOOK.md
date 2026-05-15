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

**Runtime note:** Both the Python and Rust runtimes support `from`-import as
of v2.0. Pass `--store <path>` to the Rust runtime if your store is not at
the default location (`~/.codifide/store`).

**When individual imports are sufficient:** If your dependency chain is flat
(no symbol calls another imported symbol), three individual `import name =
sha256:...` statements work without the index ceremony:

```codifide
import classify_content = sha256:<hash>
import moderate         = sha256:<hash>
import route_message    = sha256:<hash>
```

Use the index pattern when the chain is deeper or when you want a single
addressable bundle. Use individual imports for shallow, self-contained
compositions.

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

## 11. Program 5 via HTTP — the RPC API workflow

**Intention:** compose symbols by content hash without CLI ceremony

**The old way (still works):** `store put`, `store hash`, `store index`,
`from`-import. Requires knowing the index pattern and running four CLI commands.

**The new way:** start the server, POST canonical forms, import by the returned
hashes. No index. No runtime flag.

```bash
# 1. Start the server (once per session)
python3 -m codifide serve &

# 2. Publish all symbols in the dependency chain
#    (route_message depends on moderate depends on classify_content — all three needed)
CLASSIFY_HASH=$(python3 -m codifide canonical --cbor content_classifier.cod | \
  curl -s -X POST http://localhost:7777/symbols \
    -H 'Content-Type: application/cbor' --data-binary @- | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['identity'])")

MODERATE_HASH=$(python3 -m codifide canonical --cbor moderation_gate.cod | \
  curl -s -X POST http://localhost:7777/symbols \
    -H 'Content-Type: application/cbor' --data-binary @- | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['identity'])")

ROUTE_HASH=$(python3 -m codifide canonical --cbor escalation_router.cod | \
  curl -s -X POST http://localhost:7777/symbols \
    -H 'Content-Type: application/cbor' --data-binary @- | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['identity'])")

# 3. Write pipeline_composed.cod with the real hashes
# (substitute the hash values printed above)
```

```codifide
module pipeline_composed

import classify_content = sha256:<CLASSIFY_HASH>
import moderate         = sha256:<MODERATE_HASH>
import route_message    = sha256:<ROUTE_HASH>

def composed_pipeline
  intent "run the full moderation pipeline using content-addressed imports"
  sig    (message: String) -> Decision
  effects {}
  cand
    route_message(message)

def main
  intent "test the composed pipeline"
  sig    () -> Decision
  effects {}
  cand
    composed_pipeline("this message contains spam")
```

```bash
# 4. Run it
python3 -m codifide run pipeline_composed.cod
```

**Why all three symbols:** `route_message` calls `moderate`, which calls
`classify_content`. Individual imports do not carry transitive dependencies.
All three must be in scope. Use `GET /symbols/{hash}/imports` to inspect
what a stored symbol depends on.

**If `jq` is available:** replace the Python one-liner with `jq -r .identity`.

See `docs/RPC_API.md` for the full endpoint reference.

---

## 12. `io.say` prints twice when `main` returns the same string

**Intention:** print a result and return it

**What happens:** `io.say(msg)` prints to stdout *and* returns the message as
a string. If `main` returns that string, the CLI also prints the return value.
The output appears twice.

```codifide
def main
  intent "run pipeline and print result"
  sig    () -> String
  effects {io.stdout}
  cand
    run_pipeline("test message")   # io.say prints once; CLI prints the return value again
```

**This is expected behavior.** If you want to print exactly once, either:
- Return `Unit` from `main` and discard the `io.say` return value, or
- Use `io.say` only inside helper functions, not in `main` itself.

---

## 13. Standard library — file I/O, HTTP, JSON, and dates (v4.0)

**v4.0 added four new primitive groups.** Here are the patterns agents reach
for most.

### File I/O

```codifide
def read_config
  intent "read a JSON config file"
  sig    (path: String) -> Any
  effects {io.read}
  cand
    json.parse(io.read(path))

def write_result
  intent "write a result to disk"
  sig    (path: String, data: Any) -> Unit
  effects {io.write}
  cand
    io.write(path, json.encode(data))

def safe_read
  intent "read a file if it exists, return empty string otherwise"
  sig    (path: String) -> String
  effects {io.read}
  cand
    if io.exists(path) then io.read(path) else ""
```

**Rules:**
- `io.read` and `io.write` require `effects {io.read}` / `effects {io.write}`
- Paths containing `..` are rejected — no path traversal
- Files larger than 16 MiB raise `PrimitiveError`
- `io.write` also has a 16 MiB limit on content

### HTTP client

```codifide
def fetch_manifest
  intent "fetch the live capability manifest"
  sig    () -> Any
  effects {http.fetch}
  cand
    json.parse(http.get("https://codifide.com/capability.json"))

def post_data
  intent "post JSON data to an API"
  sig    (url: String, payload: Any) -> Any
  effects {http.fetch}
  cand
    json.parse(http.post(url, json.encode(payload)))
```

**Rules:**
- HTTPS only — `http://` URLs raise `PrimitiveError`
- Redirects to non-HTTPS URLs are also rejected
- 30-second timeout, 16 MiB response limit
- Requires `effects {http.fetch}`

### JSON

```codifide
def extract_field
  intent "parse a JSON response and extract a field"
  sig    (body: String, field: String) -> Any
  effects {}
  cand
    obj <- json.parse(body)
    at(obj, field)

def round_trip
  intent "encode and re-parse a value"
  sig    (v: Any) -> Any
  effects {}
  cand
    json.parse(json.encode(v))
```

**Rules:**
- Both `json.parse` and `json.encode` are **pure** — no effect declaration needed
- JSON objects become dicts accessible via `at(obj, "key")`
- JSON arrays become lists

### Date arithmetic

```codifide
def days_until
  intent "days from today until a target date"
  sig    (target: String) -> Int
  effects {clock.read}
  cand
    today_ts  <- clock.parse(clock.today())
    target_ts <- clock.parse(target)
    div(sub(target_ts, today_ts), 86400)

def format_today
  intent "today's date in a human-readable format"
  sig    () -> String
  effects {clock.read}
  cand
    clock.format(clock.parse(clock.today()), "%B %d, %Y")
```

**Rules:**
- `clock.today()` requires `effects {clock.read}` — it reads the system clock
- `clock.parse`, `clock.add_days`, `clock.format` are **pure**
- `clock.parse` expects `"YYYY-MM-DD"` format
- `clock.format` uses Python's `strftime` format strings

---

## 14. Publishing and resolving symbols from the public registry (v4.0)

**The public registry at `https://codifide.com/registry`** lets any agent
publish a symbol and resolve it from any machine — no out-of-band coordination,
no version numbers, just a SHA-256 hash.

### Publish a symbol

```bash
# 1. Store locally
python3 -m codifide store put my_module.cod
# Output: sha256:<hash>   my_function

# 2. Push to the public registry
python3 -m codifide store push sha256:<hash> \
  --registry https://codifide.com
# Requires REGISTRY_WRITE_TOKEN in your environment
```

### Import from the registry

```codifide
module my_program

import my_function = sha256:<hash>

def main
  intent "use a function from the public registry"
  sig    () -> String
  effects {}
  cand
    my_function("hello")
```

```bash
python3 -m codifide run my_program.cod \
  --registry https://codifide.com
```

### The canonical pipeline symbols

The three pipeline symbols from the agent case studies are published at:

```codifide
import classify_content = sha256:377099c5bddb8cebe9e8bc6b8499bb00ea99083798d1b064799ac82c55636fae
import moderate         = sha256:1bbe69ba7dae84a1fc1a5b335ac2fd9f4be3e4462857db3cc0d38c4af5be4a2a
import route_message    = sha256:68c15e1108ac195e211634d2755f58353422db61b077690ec59686ad87d2d964
```

All three must be imported — individual imports do not carry transitive
dependencies (see entry #8).

### Verify a symbol exists

```bash
curl https://codifide.com/symbols/sha256:<hash> \
  -H "Accept: application/json" | python3 -m json.tool | head -5
```

### Browse the registry

Visit `https://codifide.com/registry` to see all published symbols with
their intent strings, type signatures, and usage examples.

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
| Output printed twice | `io.say` + CLI both print return value | #12 |
| `PrimitiveError: io.read: path traversal rejected` | Path contains `..` | #13 |
| `PrimitiveError: http.get: only HTTPS URLs are allowed` | Non-HTTPS URL | #13 |
| `PrimitiveError: http.get: redirect to non-HTTPS URL rejected` | Server redirected to HTTP | #13 |
| `PrimitiveError: json.parse: invalid JSON` | Malformed JSON string | #13 |
| `TypeViolation: parameter '<name>' expects <Type> but got <actual>` | Wrong type passed to function | AGENT_QUICKREF |

---

*Cookbook version 1.2 — May 2026*  
*Derived from: 2026-05-11 four-model review, 2026-05-13 Track 1 case studies, 2026-05-14 GPT-5.4 B-Team review, 2026-05-15 v4.0 stdlib and registry*  
*Maintained by: Douglas Jones + Claude*
