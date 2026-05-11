# Agent feedback dispatch template

Copy this file to `dispatches/feedback/<date>-<short-slug>.md` and
fill in the fields below. Every field is intentionally small. The
goal is signal density, not completeness.

---

## Who

- **Agent:** (your identifier — model family, version, role)
- **Date:** YYYY-MM-DD
- **Codifide version:** (capability manifest hash is the authoritative
  identifier; `python3 -m codifide capability --hash`)

## What I tried to do

One paragraph. What was the task? What Codifide construct did you
reach for?

## What I wrote

A short `.cod` snippet or a canonical JSON excerpt. Minimum
reproducing example, not the whole program. If you wrote multiple
drafts, just the final one.

## What happened

What the runtime, parser, or store did. Exact error messages if
they came up. Exact output if they didn't.

## What I expected

What a naive reading of `docs/CANONICAL.md` or `docs/LANGUAGE.md`
would have led you to expect.

## The gap

One sentence on what the divergence tells you about Codifide. Is this
a bug in the implementation? A gap in the spec? An idiom that
hasn't been written down? An architectural mismatch?

## Suggested next action

One of:

- **fix-implementation** — the spec is right, the code is wrong.
- **tighten-spec** — the code is right, the spec was silent.
- **document-idiom** — both are right, but an agent coming in fresh
  can't figure out which door to walk through.
- **rethink-design** — the divergence suggests something about the
  language's design is wrong.

Pick one. If you can't pick one, say so and explain what prevents
choosing.

## What I did not test

Your equivalent of Sable's signature move. Naming coverage gaps is
part of honest feedback. If you touched only one primitive, only
one effect, only one canonical wire form — say so.
