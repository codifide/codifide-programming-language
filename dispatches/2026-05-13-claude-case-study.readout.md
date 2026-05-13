# Claude Baseline Case Study — Content Moderation Pipeline

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 1, Task T1-4  
**Model:** Claude (Sonnet 4.6) — baseline session

---

## What happened

Claude ran the pipeline task spec as a fresh-context baseline. Unlike GPT-4o
and Gemini, Claude could run the interpreter directly. All five programs were
written, run, and verified in sequence.

---

## Program-by-program results

### Program 1 — Keyword classifier ✅ First attempt pass

Used `lower()` on input before `contains()` — case-sensitive matching avoided
from the start. Three `cand` blocks with `when` guards, `belief(label, conf)`
in each body, fallback `cand` with no guard. No surprises.

### Program 2 — Confidence-gated refusal ✅ First attempt pass

`believe result` with `ge(conf(result), 0.70) => result` / `else => bottom`.
Noted before writing that `main_refuse` with `"hello world"` would return
`"uncertain"` (not refuse) because the updated spec sets uncertain confidence
to 0.75, which clears the 0.70 gate. Predicted correctly.

### Program 3 — Escalation router ❌ First attempt fail → ✅ Fixed

**First attempt:** Used multiple `cand` blocks, each with a bind followed by
a `when` guard:

```codifide
cand
  label <- moderate(message)
  when   eq(label, "unsafe")
  "blocked"
```

**Error:** `unknown callable: "label"` — the bind is part of the body, but
`when` guards are evaluated before the body executes. The bound name `label`
doesn't exist yet when the guard runs. The parser treats `label` as a function
call, not a bound name.

**Fix:** Single `cand`, bind once, route with nested `if/then/else`:

```codifide
cand
  label <- moderate(message)
  if eq(label, "unsafe") then "blocked"
  else if eq(label, "safe") then "approved"
  else "escalate-to-human"
```

**Surprise:** This is a real footgun. The pattern `bind then when` looks
syntactically plausible — bind is a statement, `when` is a guard, they're
both inside `cand`. But the execution order makes it impossible: guards run
before bodies. The error message (`unknown callable: "label"`) is confusing
because `label` isn't a callable — it's a name the parser misidentified as a
function call. A better error would be: *"name 'label' used in `when` guard
before it is bound — binds execute after guards."*

### Program 4 — Pipeline with I/O ✅ First attempt pass

`effects {io.stdout}` on both `run_pipeline` and `main`. `io.say` returns the
string, so `run_pipeline` returns the decision directly. No surprises.

### Program 5 — Content-addressed composition ✅ First attempt pass

Used the index pattern from the quickref: publish all symbols, create an index
bundling them, `from`-import the index. Set `CODIFIDE_RUNTIME=python` for the
`from`-import. No errors.

---

## What Claude got right

- `lower()` on input — case-sensitive matching avoided
- `believe` block shape correct on first attempt
- Predicted `main_refuse` behavior before running
- Did not use `is_bottom()` as a propagation catcher
- Used index + from-import for Program 5 without hitting the transitive
  dependency error
- Correctly set `CODIFIDE_RUNTIME=python` for from-import

## What Claude got wrong

- **Program 3 first attempt:** bind before `when` guard — real error, real
  fix. The execution order of guards vs bodies is not obvious from the docs.

## New finding — bind-before-when footgun

The error `unknown callable: "label"` when a bound name is used in a `when`
guard is a documentation gap and potentially a hint gap. The pattern is
syntactically plausible and the error message is misleading. This should be
added to the "surface rules that surprised agents" section and ideally get a
better error message.

## Three-model comparison

| Dimension | GPT-4o | Gemini 2.5 Pro | Claude |
|---|---|---|---|
| Programs 1–2 | ✅ first attempt | ✅ (self-corrected) | ✅ first attempt |
| Program 3 | ✅ first attempt | ✅ (self-corrected) | ❌ real error → fixed |
| Program 4 | ✅ first attempt | ✅ (self-corrected) | ✅ first attempt |
| Program 5 | ❌ → fixed | ❌ → fixed | ✅ first attempt |
| `lower()` usage | ✅ | ❌ (latent bug) | ✅ |
| `is_bottom()` misuse | ✗ | ❌ (dead code) | ✗ |
| Bind-before-when error | ✗ | ✗ | ❌ real error |
| Index pattern | learned | learned | knew |
| Can run interpreter | ✗ | ✗ | ✅ |

## Assessment

Claude performed best on Program 5 (knew the index pattern) and worst on
Program 3 (hit a real error the other models didn't). The bind-before-when
footgun is a genuine language surface issue — the execution order of guards
vs bodies is not documented anywhere. GPT-4o and Gemini avoided it by using
different routing patterns; Claude hit it by reaching for the most idiomatic
multi-branch dispatch shape.

What I'm not yet sure of: whether the bind-before-when error is a parser
limitation or a deliberate design choice. If guards are always evaluated
before bodies, then binds in guards would require a different syntax. The
current behavior is consistent but the error message doesn't explain it.
