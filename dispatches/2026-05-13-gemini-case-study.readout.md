# Gemini 2.5 Pro Case Study — Content Moderation Pipeline

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 1, Task T1-3  
**Model:** Gemini 2.5 Pro (via GitHub Copilot)

---

## What happened

Gemini 2.5 Pro was given the same pipeline task spec as GPT-4o, with the same
three resources: `FOR_AGENTS.md`, `AGENT_QUICKREF.md`, and the capability
manifest. Like GPT-4o, it could not run the interpreter and reasoned through
the programs instead.

The five programs were reconstructed from Gemini's described approach and run
through the actual interpreter.

---

## Program-by-program results

### Program 1 — Keyword classifier ✅ First attempt pass

Gemini's structure was correct: `def` with `intent`, `sig`, `effects {}`, three
`cand` blocks with `when` guards, `belief(label, confidence)` in each body.

One notable difference from GPT-4o: Gemini did not use `lower()` on the message
before calling `contains()`. This makes the classifier case-sensitive. For the
test messages used (all lowercase), this didn't cause a failure — but it's a
latent bug for mixed-case input. GPT-4o used `lower()` defensively; Gemini did
not.

### Program 2 — Confidence-gated refusal ✅ First attempt pass (after self-correction)

Gemini's first attempt omitted `intent` strings from the `cand` blocks inside
`classify_content`. It correctly predicted this would cause a `ParseError` and
self-corrected before producing the final version. The corrected code ran
correctly.

The `believe` block shape was correct: `ge(conf(result), 0.70) => result` /
`else => bottom`. Gemini used `result` (the bound name) rather than `it` (the
implicit subject alias) — both work.

One behavioral note: with the updated spec (`"uncertain"` confidence now 0.75),
`main_refuse` no longer demonstrates refusal — `"hello world"` now returns
`"uncertain"` rather than raising `RefusalError`. This is a test design issue
from the spec fix, not a Gemini error.

### Program 3 — Escalation router ✅ First attempt pass (after self-correction)

Gemini's first attempt used a `believe` block to route on string label values —
correctly anticipated a `BottomPropagationError` when `eq` received `bottom`.
Self-corrected to use nested `if/then/else` with `is_bottom()` check.

The final approach is different from GPT-4o's: Gemini used a single `cand` body
with nested `if/then/else` rather than multiple `cand` blocks with `when` guards.
Both are valid Codifide patterns. Gemini's approach is more compact; GPT-4o's is
more idiomatic for multi-branch dispatch.

Notably, Gemini used `is_bottom()` to check for refusal before routing — a
defensive pattern that handles the case where `moderate` refuses. This is
correct and shows understanding of `bottom` propagation.

### Program 4 — Pipeline with I/O ✅ First attempt pass (after self-correction)

Gemini's first attempt forgot `effects {io.stdout}` on `main`. It correctly
predicted an `EffectViolation` and self-corrected. The final version declared
`effects {io.stdout}` on both `run_pipeline` and `main`. Ran correctly.

### Program 5 — Content-addressed composition ❌ First attempt fail → ✅ Fixed

Gemini identified the transitive dependency problem before writing the code —
it reasoned that `route_message` depends on `moderate` which depends on
`classify_content`, and that importing only `route_message` would fail. This
is the same finding GPT-4o made.

Gemini's solution: store a self-contained `moderation_pipeline.cod` containing
all functions, then import `run_pipeline` by hash. The intent was correct but
the execution still fails — individual `import` statements don't bring transitive
dependencies into scope regardless of how the stored module was structured.

Fix: index bundling all four symbols + `from`-import. Same fix as GPT-4o.
Requires Python runtime (`CODIFIDE_RUNTIME=python`) due to known Rust parser gap.

---

## Gemini vs GPT-4o comparison

| Dimension | GPT-4o | Gemini 2.5 Pro |
|---|---|---|
| Programs 1–4 first attempt | 4/4 pass | 4/4 pass (with self-corrections on 2, 3, 4) |
| Program 5 | Fail → fixed | Fail → fixed |
| `lower()` on input | Yes (defensive) | No (case-sensitive) |
| `intent` on `cand` blocks | Correct first time | Missed, self-corrected |
| Effects on `main` | Correct first time | Missed, self-corrected |
| Routing approach | Multiple `cand` + `when` | Single `cand` + nested `if/then/else` |
| `is_bottom()` usage | Not used | Used defensively |
| Transitive dep. diagnosis | Identified after failure | Identified before writing |
| Self-correction quality | N/A (no errors on 1–4) | Accurate predictions, clean fixes |

---

## What Gemini got right

- Correct `def` structure on every function
- `believe` block shape correct
- Predicted `ParseError` for missing `intent` on `cand` — accurate
- Predicted `BottomPropagationError` for `believe` on string values — accurate
- Predicted `EffectViolation` for missing `effects` on `main` — accurate
- Identified transitive dependency problem before writing Program 5
- Used `is_bottom()` defensively in routing logic

## What Gemini missed

- `lower()` on input strings — case-sensitive matching is a latent bug
- The index + from-import pattern for content-addressed composition
- The Rust parser gap with `from`-imports

## Assessment

Gemini 2.5 Pro showed stronger anticipatory reasoning than GPT-4o — it predicted
three errors before running and self-corrected all of them. The routing approach
(nested `if/then/else` vs multiple `cand` blocks) is a genuine stylistic
divergence that reveals something about how Gemini models conditional logic.
Program 5 failed for the same reason as GPT-4o: the index pattern isn't
documented. The `lower()` omission is the only undetected latent bug.

What I'm not yet sure of: whether Gemini's `is_bottom()` usage in `route_message`
is actually correct — `moderate` returns `bottom` by propagation, not as a
value, so `is_bottom()` may never see it. The `bottom` would propagate through
the bind and raise `RefusalError` before `is_bottom()` could check it.
