# T1-1 — Pipeline Task Spec Filed

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 1

---

## What happened

Task T1-1 of the Agent Adoption Initiative is complete. The pipeline
task spec has been written and filed at `docs/AGENT_TASK_SPEC.md`.

The spec defines five programs an external agent must build, in order:

1. **Keyword classifier** — pure function, belief dispatch, three-label
   output (`safe`, `unsafe`, `uncertain`), confidence-annotated
2. **Confidence-gated refusal** — `believe` block, refuses below 0.70,
   `bottom` propagates
3. **Escalation router** — candidate dispatch on label value, routes to
   `blocked`, `approved`, or `escalate-to-human`
4. **Pipeline with I/O** — adds `io.say`, introduces `effects {io.stdout}`
5. **Content-addressed composition** — publishes to the store, imports
   by hash, demonstrates the full content-addressing workflow

Each program has a run command and expected output. The spec also
defines the dispatch output format (Quill readout + Glyph YAML) that
each agent session must produce.

## One correction made during drafting

The initial draft used `--args` as a CLI flag for passing arguments to
a named entry point. That flag does not exist — the interpreter only
supports `--entry` to select a named zero-arg function. The spec was
corrected: Programs 1–3 now require the agent to write `main`-style
wrapper functions for each test case, which is actually better signal
— it tests whether the agent can write multiple `def` blocks in one
module.

## What this enables

The spec is now ready to hand to GPT-4o (T1-2), Gemini 2.5 Pro (T1-3),
and Claude (T1-4). Each session starts with a fresh context, the three
agent-facing docs, and this spec. The output of each session is a
working pipeline plus a paired Quill/Glyph dispatch documenting every
failure and fix.

## Assessment

The spec is tight. Five programs, each one a natural extension of the
last, covering every major Codifide feature an agent needs to know:
belief dispatch, `believe` blocks, `bottom`, candidate guards, I/O
effects, and content-addressed imports. The documentation requirement
(first attempt, first error, fix, final code) is the most important
part — that's the adoption evidence the project needs.
