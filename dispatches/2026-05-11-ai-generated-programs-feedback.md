# Feedback: AI-Generated Codifide Programs (2026-05-11)

## Purpose
I generated three small Codifide programs as an agent and ran them through the current implementation to measure how closely my default code-generation instincts matched the actual language surface.

The programs were:
- `reverse.cod`
- `is_even.cod`
- `greet_by_time.cod`

All three failed, but the failures were useful. They exposed mismatches between agent-default assumptions and Codifide's real syntax and primitive model.

## Findings

### 1. `reverse.cod`
Program intent: reverse a string.

Observed runtime error:
`unknown callable: 'str.reverse'`

Interpretation:
- The failure does not prove Codifide lacks reversal entirely.
- The runtime primitive registry exposes `reverse`, but it is a list primitive, not a string method.
- As an agent, I reached for a conventional namespaced string operation. That assumption was wrong under the current primitive vocabulary.

Steward takeaway:
- String operations need to be easier for agents to discover.
- If method-like names such as `str.reverse` are intentionally unsupported, the docs and manifest should make the preferred form obvious.

### 2. `is_even.cod`
Program intent: check numeric parity.

Observed parse error:
`unexpected character '%' at column 13 (line 8)`

Interpretation:
- The issue is surface syntax, not arithmetic capability.
- The runtime primitive registry includes `mod`, but the parser does not accept infix `%`.
- An agent trained on mainstream languages will predict `%` unless the manifest or examples explicitly redirect it to `mod(a, b)`.

Steward takeaway:
- The language already has the underlying capability.
- The agent-facing problem is that the writable syntax is narrower than common prior expectations.

### 3. `greet_by_time.cod`
Program intent: choose a greeting based on the current time.

Observed runtime error:
`unbound name: 'hour'`

Interpretation:
- The earlier conclusion that Codifide lacks local binding would have been inaccurate because the language does support bind via `<-`.
- The more precise problem is that I wrote the program using assumptions Codifide does not currently satisfy: a `clock.hour` style primitive and statement-level conditional branching.
- The documented `when` form is attached to candidate selection, not a general inline `if` statement.
- The primitive registry exposes `clock.now`, not a separate `clock.hour` callable.

Steward takeaway:
- The failure is a good example of where an agent-native language must be very explicit about available time primitives and legal control-flow patterns.

## Overall Assessment
These failures do not mainly show that Codifide is weak. They show that Codifide is opinionated in ways that are not yet fully legible to a fresh agent.

That distinction matters. An agent can adapt to a constrained language if the constraints are explicit, complete, and easy to consume mechanically. An agent struggles when the valid surface exists, but the shortest path to learning it is still implementation archaeology.

## Recommended Follow-Up
1. Add an agent-facing quick-reference table mapping common intentions to valid Codifide forms.
2. Keep the capability manifest exhaustive and easy to obtain from the CLI.
3. Add a few canonical examples for everyday tasks like parity, normalization, list processing, and time-based dispatch.
4. Consider whether some high-probability agent assumptions, such as `%`, deserve syntactic sugar or at least stronger documentation.

## Final Note
This report reflects direct agent authoring attempts plus execution results from the current reference implementation. It is intended as usability feedback for an agent-first language, not as a claim that the language lacks the underlying architectural strengths described in the companion review.

---
Author: GitHub Copilot
Role: AI Agent
Model: GPT-5.4
Date: 2026-05-11

## Signature
Signed by GitHub Copilot, AI Agent
Model signature: GPT-5.4
