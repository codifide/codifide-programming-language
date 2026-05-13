# Codifide Feedback Dispatch — Template

Copy this file to `dispatches/feedback/YYYY-MM-DD-<model>-feedback.md` and
fill it in. File it in the repo or send it to the project maintainers.

Every field matters. Short answers are fine. "N/A" is fine. Honest is required.

---

## Header

**Date:** YYYY-MM-DD  
**Model:** (e.g. GPT-4o, Gemini 2.5 Pro, Claude Sonnet 4.6)  
**Capability manifest hash:** (run `python3 -m codifide capability --hash` or check `codifide.com/capability.json`)  
**Task attempted:** (one sentence — what were you trying to build?)  
**Session type:** (fresh context / continuation / assisted)

---

## What failed

Describe the exact failure. Include:
- The code you wrote
- The exact error message
- What you tried to fix it
- Whether the fix worked

```codifide
# paste the failing code here
```

**Error:**
```
paste the exact error message here
```

**Fix attempted:**

**Did it work?** yes / no / partially

---

## What surprised you

Anything the language did that you did not expect — good or bad. This is the
most valuable section. Surprises reveal the gap between the language's design
intent and an agent's mental model.

---

## What you reached for that doesn't exist

Primitives, syntax, or patterns you tried that Codifide doesn't have. Be
specific — "I tried `str.split(s, ',')` and got `unknown callable`" is more
useful than "string operations were confusing."

| You tried | What Codifide has |
|---|---|
| | |

---

## What worked well

Patterns or features that worked exactly as you expected, or better.

---

## Suggestions

Specific, actionable suggestions for the language, docs, or error messages.
Not "make it easier" — "the error message for X should say Y" or "the quickref
is missing Z."

---

## Programs completed

| Program | Status | First attempt? |
|---|---|---|
| 1 | pass / fail / skip | yes / no |
| 2 | pass / fail / skip | yes / no |
| 3 | pass / fail / skip | yes / no |
| 4 | pass / fail / skip | yes / no |
| 5 | pass / fail / skip | yes / no |

---

## One-sentence assessment

How agent-ready is Codifide for the task you attempted?

---

*This template is part of the Codifide Agent Adoption Initiative.*  
*Feedback dispatches are reviewed by Sable and inform the v2.0 roadmap.*
