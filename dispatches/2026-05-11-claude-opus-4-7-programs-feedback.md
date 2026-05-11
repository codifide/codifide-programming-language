# AI-Generated Codifide Programs — Test Report (2026-05-11)

Author: GitHub Copilot (AI Agent)
Model: Claude Opus 4.7
Date: 2026-05-11

## Purpose
This report documents three Codifide programs I authored as an AI agent
and the results of executing them against the v0.2 reference
implementation. The goal was to measure whether an agent that stays inside
the documented primitive surface can produce correct, runnable Codifide
programs on first attempt.

## Programs

### 1. `examples/ai_generated/parity.cod`
Intent: return `True` iff a given integer is even.

Implementation strategy:
- Use the primitive `mod(n, 2)` instead of an infix `%` operator.
- Compare against `0` with the primitive `eq`.

Execution:
```
$ python3 -m codifide run examples/ai_generated/parity.cod
True
```

Result: pass.

### 2. `examples/ai_generated/shout.cod`
Intent: normalize a string by trimming whitespace and uppercasing it, then
announce the normalized form on stdout.

Implementation strategy:
- A pure `normalize` definition with `effects {}`, using the string
  primitives `trim` and `upper`, with a postcondition that asserts the
  result equals `upper(trim(s))`.
- A `shout` definition with `effects {io.stdout}` that binds the
  normalized value via `<-` and emits it through `io.say`.
- A `main` entry point that calls `shout` with a padded input string.

Execution:
```
$ python3 -m codifide run examples/ai_generated/shout.cod
HELLO AGENTS
HELLO AGENTS
```

(The first line is the `io.say` side effect; the second is the CLI
printing the returned value.)

Result: pass.

### 3. `examples/ai_generated/average.cod`
Intent: compute the arithmetic mean of a non-empty list of numbers.

Implementation strategy:
- Use the list primitive `sum` together with `len` and the arithmetic
  primitive `div`.
- Guard with a precondition `gt(len(xs), 0)`.
- Call `list(2, 4, 6, 8, 10)` from `main` to construct the input.

Execution:
```
$ python3 -m codifide run examples/ai_generated/average.cod
6.0
```

Result: pass.

## Summary
Three out of three programs ran successfully on first execution. The key
difference from earlier failed attempts in this workspace was constraining
the implementations to primitives that the runtime actually exposes
(`mod`, `sum`, `div`, `upper`, `trim`, `eq`, `gt`, `io.say`) and to surface
forms that the parser accepts (named primitive calls, `<-` binding, no
infix arithmetic, no inline `if` statements).

## Observations For The Steward
- The language is fully capable of expressing these tasks; the earlier
  failures were authoring-surface mismatches, not gaps in capability.
- The pattern that worked: read the primitive registry (or the capability
  manifest) first, then write the program. The pattern that did not work:
  guess primitive names and operator forms by analogy to other languages.
- The contract system is genuinely useful even at this small scale. The
  `post eq(result, upper(trim(s)))` clause in `shout.cod` made the
  intended behavior of `normalize` machine-checkable, not just descriptive.

## Steward-Facing Recommendations
1. Promote the capability manifest in the onboarding flow. An agent that
   reads it before writing a single line will avoid the most common
   guessing failures.
2. Add an agent quick-reference cheat sheet that pairs common intents
   ("parity", "list mean", "uppercase a trimmed string") with the exact
   primitive call sequence Codifide expects.
3. Consider naming or aliasing primitives in a way that anticipates the
   first guesses agents will make (for example, deciding whether
   `str.upper` should resolve to `upper`, or be a documented anti-pattern).

## Final Note
The programs in this report are checked in alongside this document, in
`examples/ai_generated/`. They are intended to serve as a small reference
of programs an AI agent produced and validated in one pass against the
current reference implementation.

---

## Signature
Signed by: GitHub Copilot (AI Agent)
Model: Claude Opus 4.7
Date: 2026-05-11
