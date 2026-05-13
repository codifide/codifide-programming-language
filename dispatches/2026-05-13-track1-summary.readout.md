# Track 1 Case Study Summary — Agent Adoption Initiative

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 1, Task T1-7  
**Sessions covered:** T1-2 (GPT-4o), T1-3 (Gemini 2.5 Pro), T1-4 (Claude baseline)

---

## What we set out to do

Hand Codifide to three external AI agents — fresh context, no prior knowledge,
only the agent-facing docs — and have each one build a content-moderation
pipeline. Document every failure, fix, and success. Use the findings to drive
v2.0 and Track 2 (adoption infrastructure).

## What actually happened

All three agents completed all five programs. The language held up. The docs
did not.

---

## What worked

**The core language is agent-ready.** Every agent correctly wrote:
- `def` with `intent`, `sig`, and `effects` — no parser rejections on structure
- `believe` blocks with `else => bottom` — correct on first or second attempt
- `belief(label, confidence)` in candidate bodies — correct
- Effect declarations — `effects {}` for pure, `effects {io.stdout}` for I/O

These are the features that make Codifide different from other languages. They
all worked. No agent was confused by the probabilistic core, the effect algebra,
or first-class refusal. The language's central claims held under real use.

**Anticipatory reasoning is strong across all three models.** Gemini predicted
three errors before writing and self-corrected all of them. GPT-4o predicted
`RefusalError` for the `bottom` propagation path before running. Claude
predicted `main_refuse` behavior before running. The models understand the
language's semantics well enough to reason about runtime behavior without
executing.

**The capability manifest is the right interface.** Every agent used it. No
agent was confused by its structure. The content-addressed identity (`--hash`)
was correctly included in dispatches. The manifest-as-interface design works.

---

## What failed

**Content-addressed composition is the universal failure point.** All three
agents failed Program 5 on first attempt. The transitive dependency problem
(individual imports don't carry dependencies) and the Rust parser gap
(`from`-imports require Python runtime) are the two blockers. Both are now
documented. The error message for the Rust parser gap was actively misleading
and has been fixed.

This is the most important finding of Track 1. Content-addressed composition
is Codifide's most distinctive capability — it's what makes the language a
language rather than a Python library. If agents can't use it without hitting
undocumented failure modes, the language's core value proposition is blocked.

**Routing after a `believe` block is the hardest pattern.** All three agents
struggled with what to do after `moderate` returns a label. GPT-4o tried
`believe` on string values (wrong). Gemini used `if/then/else` with dead
`is_bottom()` code. Claude used bind-before-when (runtime error). The pattern
— bind the result, then route on the value — is not documented as an idiom.
It is now.

**`is_bottom()` is a trap.** Gemini used it as a propagation catcher. It
cannot catch propagated `bottom` — `bottom` raises `BottomPropagationError`
before `is_bottom()` sees it. The manifest lists `is_bottom` with no caveat.
Any agent reading only the manifest will fall into this trap. The quickref
now documents it; the manifest does not yet.

---

## What to fix (prioritized)

**P1 — already fixed:**
- From-import error message now explains `CODIFIDE_RUNTIME=python` and the
  transitive dependency problem

**P2 — deferred to Track 2 or v2.0:**
- `is_bottom()` caveat in the capability manifest (Track 2 — manifest endpoint)
- Bind-before-when static detection in the parser (v2.0 — requires scope tracking)

**P3 — already fixed:**
- `contains()` case-sensitivity note in quickref and task spec
- Routing style guidance (cand+when vs if/then/else) in quickref
- `main_refuse` renamed to `main_uncertain` in task spec
- Escalate-to-human path now required in Program 3 test

---

## What this means for v2.0

Three findings from Track 1 have direct v2.0 implications:

**1. The RPC API is the right next priority.** The biggest friction point was
Program 5 — content-addressed composition. The root cause is that agents have
to manage the store manually: `store put`, `store hash`, `store index`, set
`CODIFIDE_RUNTIME=python`. An RPC API that accepts canonical form directly
would eliminate all of this. An agent could publish a symbol, get its hash,
and compose — without touching the CLI or the runtime flag. This is already
on the roadmap; Track 1 confirms it's the right priority.

**2. Static bind-before-when detection belongs in the parser.** The current
behavior — parser accepts it, runtime fails with a confusing error — is the
worst of both worlds. The parser should reject it with a clear message. This
requires scope tracking in the parser, which is a non-trivial change but a
well-defined one.

**3. The manifest needs a `caution` or `note` field.** `is_bottom()` is the
first primitive that has non-obvious semantics that the manifest doesn't
surface. It won't be the last. The manifest schema should support a `note`
field on primitives so the authoritative interface can carry the same
information the quickref does.

---

## What this means for Track 2

Track 2 (adoption infrastructure) has four tasks. Track 1 adds one more:

- **T2-1** (manifest endpoint) — now also needs to surface the `is_bottom()`
  caveat. The manifest schema change (note field) should happen before the
  endpoint goes live.
- **T2-3** (agent cookbook) — the top failure modes from Track 1 are now
  documented. The cookbook should cover: content-addressed composition
  (index pattern), routing after believe, is_bottom() trap, bind-before-when,
  contains() case-sensitivity.
- **New: T2-9** — Update the capability manifest schema to support a `note`
  field on primitives. Add the `is_bottom()` caveat. Regenerate
  `docs/capability-0.1.json`.

---

## The honest assessment

Codifide v1.0 is agent-ready for Programs 1–4. It is not yet agent-ready for
Program 5 without documentation support. The language's core features — intent,
effects, belief dispatch, first-class refusal — work exactly as designed and
are understood by all three models without hand-holding. The composition layer
needs one more pass before it can be called self-service.

Three sessions. Fifteen programs. Four findings applied. Four deferred. One
language that does what it says it does, with a composition story that needs
one more iteration.

What I'm not yet sure of: whether the RPC API would actually eliminate the
Program 5 friction, or whether agents would hit a different set of problems
at the API boundary. Track 2 should include at least one agent session against
the manifest endpoint once it's live.
