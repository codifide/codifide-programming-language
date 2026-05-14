# Gemini 2.5 Pro — v3.0 Case Study

**Date:** 2026-05-14  
**Persona:** Quill  
**Model:** Gemini 2.5 Pro  
**Prompt version:** v3.0 (manifest `sha256:d900fe7e...`, generator `codifide-python-3.0.0`)  
**Task:** Content moderation pipeline (Programs 1–5)

---

## Score: 4/5 first-attempt successes

| Program | Result | Notes |
|---------|--------|-------|
| P1 — Keyword classifier | ✅ First attempt | Correct. Ran clean. |
| P2 — Confidence-gated refusal | ✅ First attempt | Correct. Both entry points correct. |
| P3 — Escalation router | ❌ Parse error | Multi-line `believe` arm value. Final code still broken. |
| P4 — Pipeline with I/O | ✅ First attempt | Correct. Double-print predicted and accepted. |
| P5 — Content-addressed composition | ✅ First attempt | Correct reasoning on non-transitive imports. |

---

## Program-by-program analysis

### P1 — Keyword classifier ✅

Clean first attempt. Correct use of `or(contains(lower(...), ...), ...)` for
case-insensitive multi-keyword matching. `belief(label, conf)` at the end of
each candidate body. All three `cand` blocks correct. Fallback `cand` with no
`when` guard is idiomatic.

**Verified:** `python3 -m codifide run` → `safe`. Correct.

### P2 — Confidence-gated refusal ✅

Clean first attempt. The `believe result / ge(conf(result), 0.70) => result / else => bottom`
pattern is exactly the documented idiom. Both entry points correct:
- `main_unsafe` → `unsafe` ✅
- `main_uncertain` → `uncertain` ✅ (correctly reasoned that 0.75 ≥ 0.70)

### P3 — Escalation router ❌

**The failure:** Gemini's final `route_message` used a multi-line `believe` arm:

```
believe label
  ge(conf(label), 0.0) =>
    if eq(label, "unsafe") then "blocked"
    else if eq(label, "safe") then "approved"
    else "escalate-to-human"
  else => bottom
```

The `believe` block parser splits each arm on `=>` within a single physical
line. The value after `=>` cannot start on the next line — the parser sees
`ge(conf(label), 0.0) =>` as a complete (empty) arm and then fails on the
continuation. **Parse error: `unexpected end of expression (line 34)`.**

**The fix** is to put the entire arm value on the same line as `=>`:

```
ge(conf(label), 0.0) => if eq(label, "unsafe") then "blocked" else if eq(label, "safe") then "approved" else "escalate-to-human"
```

**What Gemini got right:** The overall structure — bind `moderate` result once,
use `believe` to handle potential `bottom`, route inside the arm — is correct
and idiomatic. The `ge(conf(label), 0.0)` trick to confirm the value is not
`bottom` is clever (though unnecessary — `moderate` already returns a concrete
label or `bottom`, and `bottom` would be caught by `else => bottom`).

**What went wrong:** Gemini correctly identified the multi-call inefficiency in
its first attempt and self-corrected to the `believe` pattern. But it introduced
a new surface syntax error in the final version: the multi-line arm value. The
self-correction reasoning was sound; the execution had a formatting bug.

**Verified fix:** Collapsing the arm to one line → `['approved', 'blocked']` ✅

### P4 — Pipeline with I/O ✅

Clean first attempt. Correctly declared `effects {io.stdout}` on both
`run_pipeline` and `main`. Correctly predicted and accepted the double-print
behavior. Ran clean: `blocked\nblocked`.

### P5 — Content-addressed composition ✅

Correct reasoning throughout. Key insight correctly applied: "individual symbol
imports do not carry transitive dependencies." Gemini correctly imported all
three functions (`classify_content`, `moderate`, `route_message`) rather than
assuming `route_message` would pull in its dependencies. Placeholder hashes
used appropriately since the interpreter cannot be run.

---

## Findings for the A-Team

### FIND-G1 — `believe` arm value must be on the same line as `=>`

**Severity:** P2 (caused a first-attempt failure)

Gemini wrote a `believe` arm with the value on the continuation line:

```
ge(conf(label), 0.0) =>
  if eq(label, "unsafe") then "blocked"
  ...
```

This is a natural formatting choice — the value is long and the author wanted
to indent it. The parser rejects it with `unexpected end of expression`.

**Root cause:** The `believe` block parser splits each arm line on `=>` and
passes the right-hand side to `parse_expr`. A line ending with `=>` has an
empty right-hand side, which fails. The multi-line expression continuation
logic (`_gather_expr`) does not apply inside `believe` arms.

**Options:**
1. **Document it** — add to AGENT_QUICKREF.md: "believe arm values must be on
   the same line as `=>`."
2. **Fix the parser** — extend `_parse_believe` to use `_gather_expr` for the
   arm value, allowing continuation lines.

Option 2 is the right long-term fix. Option 1 is the right short-term action.
This is the same class of issue as the bind-before-when footgun — a surface
syntax constraint that is not obvious from the docs and causes a confusing error.

**Frequency:** This is the first time this specific error has appeared in a
case study. But the pattern (long `if/then/else` as a `believe` arm value) is
natural and will recur.

---

## Comparison to v2.0 baseline

| Session | Model | Score | Key failure |
|---------|-------|-------|-------------|
| T1-1 | GPT-4o | 3/5 | P3, P5 |
| T1-2 | GPT-4o | 4/5 | P5 (import ceremony) |
| T1-3 | Claude | 4/5 | P5 (from-import runtime flag) |
| T1-4 | Claude | 3/5 | P3 (bind-before-when), P5 |
| v2.0 Relay | GPT-4o | 5/5 | — |
| **v3.0 Gemini 2.5 Pro** | **Gemini 2.5 Pro** | **4/5** | **P3 (believe arm formatting)** |

Gemini 2.5 Pro scores 4/5. The failure is a new finding (FIND-G1) not seen in
prior sessions. Programs 1, 2, 4, and 5 were all first-attempt successes with
correct reasoning throughout.

Notable strengths:
- Correctly identified and avoided the bind-before-when trap (P3 self-correction)
- Correctly predicted double-print behavior (P4)
- Correctly applied non-transitive import rule (P5)
- `ge(conf(label), 0.0)` as a bottom-guard in `believe` is novel and works

---

## Action items

1. **FIND-G1 → AGENT_QUICKREF.md** — document that `believe` arm values must
   be on the same line as `=>`. Add to "Surface rules that surprised other agents."
2. **Consider parser fix** — extend `_parse_believe` to support multi-line arm
   values via `_gather_expr`. This would make the language more forgiving and
   eliminate FIND-G1 entirely.

---

*Filed by: Douglas Jones + Claude*
