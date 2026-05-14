# Session Close — 2026-05-14 (Gemini v3.0 case study)

**Date:** 2026-05-14  
**Persona:** Quill  
**Tests:** 386 passing, 0 skipped, 0 failed  
**Dispatch check:** exits 0, all pairs complete

---

## What happened this session

Opened from the v3.0 close. Updated the B-Team prompt for v3.0, ran the
Gemini 2.5 Pro case study, and fixed the one finding it surfaced.

### 1. B-Team prompt update (v3.0)

`docs/GPT4O_PROMPT.md` updated: title, manifest hash, generator string,
`bottom "reason"` syntax, `is_bottom` note, V3-2 remote resolution section.
`__version__` bumped from `1.0.0` to `3.0.0` (was never bumped). Capability
manifest and dispatch index regenerated.

Filed: `2026-05-14-bteam-prompt-v3.{readout.md,yaml}`

### 2. Gemini 2.5 Pro v3.0 case study

Score: **4/5** first-attempt successes.

- P1 ✅ — keyword classifier, clean first attempt
- P2 ✅ — confidence-gated refusal, clean first attempt
- P3 ❌ — escalation router: multi-line `believe` arm value caused `ParseError`
- P4 ✅ — pipeline with I/O, double-print correctly predicted
- P5 ✅ — content-addressed composition, non-transitive import rule correctly applied

New finding: **FIND-G1** — `believe` arm value on continuation line after `=>`.

Filed: `2026-05-14-gemini25pro-v3-case-study.{readout.md,yaml}`

### 3. FIND-G1 fix — believe multi-line arm value

Both Python and Rust parsers updated: when a `believe` arm line ends with `=>`
(empty right-hand side), the parser now calls `gather_expr` on the next
indented line to collect the value. Multi-line `if/then/else` expressions work
as arm values. 3 regression tests added.

`docs/AGENT_QUICKREF.md` updated: the constraint note replaced with a
"both forms work" note. `docs/GPT4O_PROMPT.md` updated to match.

Filed: `2026-05-14-find-g1-believe-multiline-arm.{readout.md,yaml}`

---

## State at close

- Tests: **386 passing, 0 skipped** (383 → 386, +3 regression tests)
- Dispatch check: exits 0
- Rust build: clean
- `__version__`: `3.0.0`
- Manifest hash: `sha256:d900fe7e6d91300424b226cda0fd404bf281c4362a70131dbec116548b310ff2`

## Comparison to prior case studies

| Session | Model | Score | Key failure |
|---------|-------|-------|-------------|
| T1-1 | GPT-4o | 3/5 | P3, P5 |
| T1-2 | GPT-4o | 4/5 | P5 |
| T1-3 | Claude | 4/5 | P5 |
| T1-4 | Claude | 3/5 | P3, P5 |
| v2.0 Relay | GPT-4o | 5/5 | — |
| v3.0 Gemini 2.5 Pro | Gemini 2.5 Pro | 4/5 | P3 (FIND-G1, now fixed) |

## Handoff for next session

FIND-G1 is fixed. The `believe` multi-line arm constraint is gone. The next
case study should score 5/5 on this task spec if the model reads the docs.

Options:
1. Run another model against the v3.0 prompt to confirm 5/5 is achievable
2. Assess v4.0 scope based on accumulated findings
3. Update the task spec to include a Program 6 that exercises `bottom "reason"`
   and the new `believe` multi-line syntax
