# GPT-5.4 Case Study — Content Moderation Pipeline (Live Run)

**Date:** 2026-05-14  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 1, Task T1-2 (B-Team governance review)  
**Model:** GPT-5.4 (ChatGPT, deep thinking mode)

---

## What happened

GPT-5.4 was given the B-Team review package: `FOR_AGENTS.md`, `AGENT_QUICKREF.md`,
the capability manifest, and the pipeline task spec. Unlike GPT-4o and Gemini,
GPT-5.4 did not follow the "no shell access" fallback instruction. Instead it
discovered the local Codifide repository at `CodifideProgrammingLanguage`, installed
the interpreter from source via `pip install -e .`, and ran all five programs for
real.

This is the first B-Team run with live interpreter access. It changes what the
results mean: failures are real runtime errors, not predicted ones.

---

## Program-by-program results

### Program 1 — Keyword classifier ✅ First attempt pass

Used `lower()` before `contains()`, `or(...)` for multi-keyword unsafe detection,
`belief(label, confidence)` in each candidate body. Structure correct on first
attempt. Ran without error, returned `"safe"` for a verified message.

**Surprise noted by GPT-5.4:** `belief("safe", 0.90)` under a `-> Label` signature
returned a plain label at the CLI. It assumed Codifide handles this correctly —
which it does. The uncertainty was honest and the assumption was right.

### Program 2 — Confidence-gated refusal ❌ First attempt fail → ❌ Second attempt fail → ✅ Fixed

**First attempt:** `main_refuse` returned `bottom` at the top level.

**First error (real):**
```
runtime error: 'main_refuse' returned ⊥ (refusal) and no caller chose to handle it.
```

**First fix attempt:** Changed `main_refuse` to bind the result and use a `believe`
block to map low confidence to `"uncertain"`.

**Second error (real):**
```
Runtime error: primitive 'conf' received ⊥ (refusal) as an argument.
```

This is the `BottomPropagationError` path. Binding a refused value and then calling
`conf(...)` on it feeds `⊥` into a primitive before the `believe` arm can help.
The AGENT_QUICKREF documents this failure mode, but GPT-5.4 still hit it — the
fix it reached for first was the wrong one.

**Final fix:** Used `is_bottom(moderate("hello world"))` as a direct-call check
(no bind), then `if/then/else` to return `"uncertain"` or the real result. This
short-circuits before the refusing value is bound.

**Final working code for `main_refuse`:**
```codifide
cand
  if is_bottom(moderate("hello world")) then "uncertain" else moderate("hello world")
```

Run results: `main_unsafe` → `"unsafe"`, `main_refuse` → `"uncertain"`.

**New finding:** Direct-call `is_bottom(function_that_refuses())` works. The
AGENT_QUICKREF only documents the failure mode (bind then `is_bottom`), not the
working pattern (direct-call `is_bottom`). This is a documentation gap.

### Program 3 — Escalation router ✅ First attempt pass

Used a single `cand` body with nested `if/then/else` for routing — same approach
as Gemini, different from GPT-4o's multi-`cand` pattern. Ran correctly, returned
`['blocked', 'approved']` for the two test messages.

**Spec gap confirmed:** GPT-5.4 independently identified that the `"uncertain"`
route is dead code. `classify_content` assigns `"uncertain"` confidence 0.40;
`moderate` refuses below 0.70. The `"escalate-to-human"` path is structurally
unreachable. This is the same finding GPT-4o made in T1-2 and the same finding
Gemini made in T1-3.

**Note on routing approach:** GPT-5.4 used `is_bottom(moderate(message))` as a
`when` guard in one candidate, then bound `label <- moderate(message)` in a
second candidate. This calls `moderate` twice — once for the guard check and once
for the bind. This is correct but inefficient. The idiomatic Codifide pattern
would be a single `cand` with a bind and `if/then/else`, which GPT-5.4 used in
the body of the second candidate anyway.

### Program 4 — Pipeline with I/O ✅ First attempt pass

`effects {io.stdout}` on both `run_pipeline` and `main`. `io.say` used correctly.
Ran without error.

**Surprise noted by GPT-5.4:** The program printed twice — once from `io.say` and
once from the CLI printing `main`'s return value. This is expected behavior but
not documented anywhere in the agent-facing docs.

### Program 5 — Content-addressed composition ❌ First attempt fail → ✅ Fixed

**First attempt:** Imported only `classify_content` and `route_message` by hash.

**First error (real):**
```
runtime error: unknown callable: "moderate".
```

**Fix:** Added a third import for `moderate` by hash. The program then ran
correctly, returning `"approved"`.

**Finding confirmed:** Content-addressed symbol imports are not closed over sibling
dependencies. This is the same finding GPT-4o and Gemini made. GPT-5.4 hit it as
a real runtime error rather than a predicted one.

**Note:** GPT-5.4 did not use the index + from-import pattern. It used three
individual `import name = sha256:...` statements. This works for this pipeline
because all three symbols are pure and have no further transitive dependencies.
The index pattern is still the right approach for deeper dependency chains.

---

## What GPT-5.4 got right

- Found and installed the local interpreter rather than simulating
- `lower()` on input — case-sensitive matching avoided
- `belief(label, confidence)` in candidate bodies — correct
- `believe` block shape with `else => bottom` — correct
- `effects {}` on pure functions, `effects {io.stdout}` at I/O boundary
- Avoided bind-before-when error (used single `cand` + `if/then/else`)
- Identified the unreachable `"uncertain"` route independently
- Identified the double-print behavior of `io.say` + CLI return
- Identified the transitive dependency gap in content-addressed imports

## What GPT-5.4 missed or got wrong

- **Program 2, first fix:** Reached for bind + `believe` to handle refusal —
  the wrong pattern. The AGENT_QUICKREF documents this failure mode but GPT-5.4
  still hit it. The working pattern (direct-call `is_bottom`) is not documented.
- **Program 3:** Called `moderate` twice in `route_message` — once for the guard
  check and once for the bind. Correct but inefficient.
- **Program 5:** Did not use the index + from-import pattern. Works for this
  pipeline but won't scale to deeper dependency chains.

## New findings for the A-Team

**FIND-B1 — Direct-call `is_bottom` is undocumented:**  
`is_bottom(function_that_refuses())` works as a direct-call check. The
AGENT_QUICKREF only documents the failure mode (bind then `is_bottom`). The
working pattern should be added as an explicit example.

**FIND-B2 — Double-print behavior undocumented:**  
`io.say` prints to stdout and the CLI also prints `main`'s return value. Programs
with `io.say` in `main` print twice. This should be noted in the I/O section of
the quickref.

**FIND-B3 — Unreachable `"uncertain"` route (third confirmation):**  
GPT-4o, Gemini, and GPT-5.4 all independently identified this. The task spec
confidence thresholds need to be fixed before the next case study.

**FIND-B4 — Individual hash imports work for shallow pipelines:**  
Three individual `import name = sha256:...` statements work when the dependency
chain is flat. The index pattern is only required for deeper chains. The docs
should clarify when each approach is appropriate.

---

## Four-model comparison

| Dimension | GPT-4o | Gemini 2.5 Pro | Claude | GPT-5.4 |
|---|---|---|---|---|
| Ran interpreter | ✗ (simulated) | ✗ (simulated) | ✅ (direct) | ✅ (found + installed) |
| Program 1 | ✅ first | ✅ first | ✅ first | ✅ first |
| Program 2 | ✅ first | ✅ first | ✅ first | ❌ → ❌ → fixed |
| Program 3 | ✅ first | ✅ first | ❌ → fixed | ✅ first |
| Program 4 | ✅ first | ✅ first | ✅ first | ✅ first |
| Program 5 | ❌ → fixed | ❌ → fixed | ✅ first | ❌ → fixed |
| `lower()` usage | ✅ | ❌ (latent) | ✅ | ✅ |
| Bind-before-when | avoided | avoided | ❌ real error | avoided |
| Unreachable route found | ✅ | ✅ | — | ✅ |
| Index pattern | learned | learned | knew | not used |
| Double-print noted | ✗ | ✗ | ✗ | ✅ |
| Direct-call `is_bottom` | ✗ | ✗ | ✗ | ✅ (discovered) |

---

## Assessment

GPT-5.4 is the first B-Team model to find and run the interpreter rather than
simulate. That changes the signal: its failures are real runtime errors, not
predictions. The two-step failure on Program 2 is the most informative result —
it hit the exact failure mode the AGENT_QUICKREF warns about, then reached for
the wrong fix, then found the right one. The working pattern (direct-call
`is_bottom`) is not documented anywhere. That's a real gap.

The unreachable `"uncertain"` route has now been independently identified by
three models. It is no longer a finding — it is a confirmed spec bug that must
be fixed before the next case study.

GPT-5.4's overall performance is strong: 4/5 programs on first attempt (with
real interpreter runs), correct effects discipline, correct `believe` shape,
and two new findings the prior models missed. The Program 2 failure is the
only meaningful regression against the prior baseline.

What I'm not yet sure of: whether the direct-call `is_bottom` pattern is
intentional and stable, or an implementation detail that happens to work. It
needs an explicit interpreter test before it goes into the docs.

