# GPT-4o — v3.0 Case Study

**Date:** 2026-05-14  
**Persona:** Quill  
**Model:** GPT-4o  
**Prompt version:** v3.0 (manifest `sha256:d900fe7e...`, generator `codifide-python-3.0.0`)  
**Task:** Content moderation pipeline (Programs 1–5)

---

## Score: 4/5 first-attempt successes

| Program | Result | Notes |
|---------|--------|-------|
| P1 — Keyword classifier | ✅ First attempt | Correct. Nested `or` → flat `or` was a style note, not a real error. |
| P2 — Confidence-gated refusal | ✅ First attempt | Correct. Both entry points correct. |
| P3 — Escalation router | ❌ EffectViolation | `main` calls `io.say` but declares `effects {}`. |
| P4 — Pipeline with I/O | ✅ First attempt | Correct. Double-print behavior noted. |
| P5 — Content-addressed composition | ✅ First attempt | Correct structure, placeholder hashes appropriate. |

---

## Program-by-program analysis

### P1 — Keyword classifier ✅

Clean first attempt. GPT-4o noted that `or` is variadic and self-corrected
from nested `or(a, or(b, c))` to flat `or(a, b, c)`. Both forms work; the
flat form is idiomatic. Correct use of `lower()` for case normalization.

**Verified:** `python3 -m codifide run` → `safe`. Correct.

### P2 — Confidence-gated refusal ✅

Clean first attempt. Inlined `classify_content` rather than importing it —
correct choice given the task spec. The `believe label / ge(conf(label), 0.70) => label / else => bottom` pattern is exactly right.

- `main_unsafe` → `unsafe` ✅
- `main_uncertain` → `uncertain` ✅ (0.75 ≥ 0.70 correctly reasoned)

### P3 — Escalation router ❌

**The failure:** `main` calls `io.say` but declares `effects {}`:

```codifide
def main
  intent "test route_message with two messages"
  sig    () -> Unit
  effects {}          # ← wrong — io.say requires {io.stdout}
  cand
    io.say(route_message("this message contains spam"))
    io.say(route_message("hello world"))
```

**Runtime error:** `EffectViolation: 'test route_message with two messages' performed effect 'io.stdout' which is not in its declared set []`

**The fix:** `effects {io.stdout}` on `main`. One character change.

**What GPT-4o got right:** `route_message` itself is correctly declared pure
(`effects {}`). The routing logic using `if/then/else` is correct and idiomatic.
The `else bottom` removal was sound reasoning (moderate already propagates bottom).

**What went wrong:** GPT-4o added `io.say` calls to `main` for testing but
forgot to update `main`'s effects declaration. This is the same class of error
as T1-3 and T1-4 — the transitive effect rule is understood in principle but
missed in practice when adding I/O to a test harness.

**Verified fix:** `effects {io.stdout}` on `main` → `blocked\nescalate-to-human`. ✅

### P4 — Pipeline with I/O ✅

Clean first attempt. Correctly declared `effects {io.stdout}` on both
`run_pipeline` and `main`. The `decision <- route_message(message) / io.say(decision) / decision` pattern is correct — bind, print, return. Double-print noted.

**Verified:** `blocked\nblocked`. ✅

### P5 — Content-addressed composition ✅

Correct structure. Imported `classify_content` and `route_message` (skipped
`moderate` — reasonable since `route_message` inlines `moderate` in this
version). Placeholder hashes used appropriately.

---

## Findings for the A-Team

### No new findings

The P3 failure is a known pattern — transitive effect declaration missed when
adding I/O to a test harness. This appeared in T1-3 and T1-4 as well. It is
documented in AGENT_QUICKREF.md under "Every `def` must declare `effects`."

The fix is always the same: add the effect label to the declaring function.
The error message is clear (`performed effect 'io.stdout' which is not in its
declared set []`). No new documentation or parser changes needed.

---

## Comparison to prior case studies

| Session | Model | Score | Key failure |
|---------|-------|-------|-------------|
| T1-1 | GPT-4o | 3/5 | P3, P5 |
| T1-2 | GPT-4o | 4/5 | P5 |
| T1-3 | Claude | 4/5 | P5 |
| T1-4 | Claude | 3/5 | P3, P5 |
| v2.0 Relay | GPT-4o | 5/5 | — |
| v3.0 Gemini 2.5 Pro | Gemini 2.5 Pro | 4/5 | P3 (FIND-G1, fixed) |
| **v3.0 GPT-4o** | **GPT-4o** | **4/5** | **P3 (effects {} on io.say main)** |

GPT-4o scores 4/5 on the v3.0 prompt. The failure is a known pattern, not a
new finding. Programs 1, 2, 4, and 5 were all first-attempt successes.

Notable: GPT-4o's P3 failure is different from Gemini's P3 failure. Gemini
hit a parser constraint (believe arm formatting, now fixed). GPT-4o hit a
runtime constraint (missing effect declaration). Both are P3 failures but
from different root causes.

---

## Assessment

Two consecutive 4/5 runs (Gemini, GPT-4o) with different P3 failure modes
suggests P3 is the hardest program in the task spec. The failures are:

- **Gemini:** believe arm formatting (parser, now fixed)
- **GPT-4o:** missing `effects {io.stdout}` on test harness `main`
- **T1-4 Claude:** bind-before-when (parser, fixed in v2.0)

The common thread: P3 is where agents add complexity (routing logic, I/O,
or multi-step dispatch) and make a small structural mistake. The task spec
may benefit from a note reminding agents to check effect declarations on
every `def` they write, not just the "main" function.

No action items beyond filing this readout.

---

*Filed by: Douglas Jones + Claude*
