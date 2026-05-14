# Task Spec Update — Effects reminder on Program 3

**Date:** 2026-05-14  
**Persona:** Quill  
**Trigger:** GPT-4o v3.0 case study P3 failure; same pattern in T1-3 and T1-4

---

## What changed

`docs/GPT4O_PROMPT.md` — Program 3 (Escalation router) gains an effects reminder:

> **Effects reminder:** Check the `effects` declaration on every `def` you write,
> including `main`. If `main` calls `io.say` for testing, it must declare
> `effects {io.stdout}`. The runtime enforces effect declarations transitively
> and raises `EffectViolation` if one is missing — even on a test harness function.

## Why

Three case studies (T1-3, T1-4, GPT-4o v3.0) hit the same failure at P3:
a test harness `main` that calls `io.say` but declares `effects {}`. The
error message is clear (`EffectViolation`) but the mistake is easy to make
when adding I/O to a function that was previously pure. The reminder is
placed at the point of failure — Program 3 is where agents first add I/O
to a test harness.

## What was NOT changed

- The task spec structure is unchanged
- No new programs added
- AGENT_QUICKREF.md already documents the effects rule; no change needed there

---

*Filed by: Douglas Jones + Claude*
