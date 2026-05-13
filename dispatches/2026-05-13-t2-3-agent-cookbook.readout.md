# T2-3 — Agent Cookbook Filed

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 2, Task T2-3

---

## What happened

`docs/AGENT_COOKBOOK.md` written and filed. Ten failure modes, each with
intention → wrong attempt → error → working example → explanation.

## Sources

The cookbook draws from two sets of sessions:

**2026-05-11 — four-model v1.0 review (GPT-5.4, Claude Opus 4.7, Gemini 2.5
Pro, Grok Code Fast 1):**
- Infix arithmetic (`%`, `+`, `-`, `*`, `/`)
- Method-shaped string/list names (`str.reverse`, `str.upper`, etc.)
- `clock.hour` / `clock.minute`
- Missing `else` on `believe` blocks
- Missing `intent` and `effects` on `def`

**2026-05-13 — Track 1 case studies (GPT-4o, Gemini 2.5 Pro, Claude):**
- `contains()` case-sensitivity (Gemini)
- `is_bottom()` as propagation catcher (Gemini)
- Bind-before-when footgun (Claude)
- Content-addressed composition — transitive dependency + index pattern
- `belief(...)` return type advisory (GPT-4o uncertainty)

## What's in the cookbook

10 entries covering every observed failure mode:
1. Arithmetic operators don't exist as infix
2. String/list operations are top-level primitives, not methods
3. `contains` is case-sensitive — normalize first
4. Time is read via `clock.now`, not `clock.hour`
5. `believe` blocks require `else` — `else => bottom` is the right refusal
6. `is_bottom()` cannot catch propagated `bottom`
7. Bind-before-when: guards execute before candidate bodies
8. Content-addressed imports require an index for transitive dependencies
9. Every `def` must declare `intent`, `sig`, and `effects`
10. `belief(...)` return type is advisory, not enforced

Each entry includes a quick diagnostics table mapping error messages to
cookbook entries.

## Also updated

`docs/FOR_AGENTS.md` — added `AGENT_COOKBOOK.md` to the "if you get stuck"
section.

## Assessment

The cookbook covers everything observed across five sessions. Entry #8
(content-addressed composition) is the most complex — it requires explaining
the index pattern, the `from`-import syntax, and the Rust runtime gap in one
entry. The quick diagnostics table at the bottom is the most useful part for
an agent that's already hit an error and needs to find the fix fast.

What I'm not yet sure of: whether the cookbook should be linked from the
capability manifest itself (as a `docs` field), or whether the manifest
endpoint is sufficient. An agent that fetches `codifide.com/capability.json`
won't automatically know the cookbook exists.
