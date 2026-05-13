# GPT-4o Case Study — Content Moderation Pipeline

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 1, Task T1-2  
**Model:** GPT-4o (via ChatGPT, shared conversation)

---

## What happened

GPT-4o was given the pipeline task spec (`docs/AGENT_TASK_SPEC.md`) along with
`FOR_AGENTS.md`, `AGENT_QUICKREF.md`, and the capability manifest. It could not
run the Codifide interpreter — the environment had no `codifide` module — so it
followed the prompt's fallback instruction: write the programs, reason through
expected behavior, document likely failures and fixes, produce final code.

The five programs were reconstructed from GPT-4o's described approach and run
through the actual interpreter. Results below.

---

## Program-by-program results

### Program 1 — Keyword classifier ✅ First attempt pass

GPT-4o used `contains(lower(message), "...")` for keyword matching, `or(...)` for
multi-keyword unsafe detection, and `belief(label, confidence)` in each candidate.
The structure was correct on the first attempt. Ran without error, returned
`"unsafe"` for a spam message as expected.

One genuine uncertainty GPT-4o flagged: `belief(...)` returns `Any` in the
manifest, but the function signature says `-> Label`. It assumed Codifide handles
this correctly — which it does, `belief` wraps any value and the runtime doesn't
enforce the declared return type against the belief wrapper. The uncertainty was
honest and the assumption was right.

### Program 2 — Confidence-gated refusal ✅ First attempt pass

GPT-4o inlined `classify_content` and wrote the `believe` block correctly:

```
believe result
  ge(conf(result), 0.70) => result
  else                   => bottom
```

Both paths behaved exactly as predicted: `main_unsafe` returned `"unsafe"`,
`main_refuse` raised `RefusalError`. GPT-4o correctly predicted that `bottom`
escaping produces `RefusalError`, not a silent failure.

### Program 3 — Escalation router ✅ First attempt pass (with a real finding)

GPT-4o wrote the routing logic correctly and the program ran. But it also caught
something real: **the `"uncertain"` route is unreachable**. Program 1's fallback
`"uncertain"` has confidence 0.40. Program 2's gate refuses anything below 0.70.
So `moderate` will never return `"uncertain"` — it will always refuse first.

GPT-4o included the `"uncertain"` candidate anyway because the task spec requires
it, and used safe/unsafe test messages in `main` to avoid triggering the refusal
path. That's the right call. But the finding stands: the task spec has a logical
gap. The `"escalate-to-human"` path is dead code under the current confidence
thresholds.

### Program 4 — Pipeline with I/O ✅ First attempt pass

GPT-4o correctly declared `effects {io.stdout}` only on the I/O boundary
(`run_pipeline` and `main`), kept all pure functions as `effects {}`, and used
`io.say` correctly. The program ran and printed `"approved"` to stdout.

One note: `io.say` returns the message as a string, so the final return value of
`run_pipeline` is the decision string — which is what the spec asked for. GPT-4o
got this right without being told.

### Program 5 — Content-addressed composition ❌ First attempt fail → ✅ Fixed

GPT-4o's approach: `import classify_content = sha256:...` and
`import route_message = sha256:...` with placeholder hashes. The structure was
correct in intent but failed in execution for two reasons:

**Failure 1 — Transitive dependency gap.** Individual symbol imports don't carry
their transitive dependencies. `route_message` calls `moderate` internally, but
`moderate` isn't in scope when `route_message` executes. Error:
`unknown callable: "route_message"`. Fix: use an index that bundles all three
symbols (`classify_content`, `moderate`, `route_message`) and `from`-import them
together.

**Failure 2 — Rust parser gap.** `from <hash> import ...` is not yet supported
in the Rust parser. Fix: use `CODIFIDE_RUNTIME=python`. This is a known v2.0
gap, not a user error.

GPT-4o actually anticipated the first failure in its review notes: *"the composed
pipeline only needs `route_message` directly unless the imported router depends on
separately addressable imports."* It identified the dependency problem but didn't
know the correct fix (index + from-import). That's fair — the task spec didn't
explain the index pattern.

---

## What GPT-4o got right

- Every `def` had `intent`, `sig`, and `effects` — no parser rejections
- `effects {}` on pure functions, `effects {io.stdout}` only at the I/O boundary
- `believe` block shape with `else => bottom` — correct on first attempt
- `or(contains(...), contains(...))` for multi-keyword matching — correct
- `belief(label, confidence)` in candidate bodies — correct
- Predicted `RefusalError` for the `bottom` propagation path — correct
- Avoided all arithmetic operator pitfalls (`%`, `+`, `-`, etc.)
- Spotted the unreachable `"uncertain"` route — a real spec gap

## What GPT-4o missed or got wrong

- The transitive dependency problem in content-addressed imports — didn't know
  the index + from-import pattern
- The Rust parser gap with `from`-imports — not documented in the agent-facing
  docs (this is a gap in our docs, not GPT-4o's fault)

## What the task spec got wrong

- The `"uncertain"` route is unreachable given the confidence thresholds. The
  spec should either lower the `moderate` gate to 0.35 (so uncertain passes
  through) or raise the `"uncertain"` confidence to 0.75 (so it clears the gate).
  This needs to be fixed before T1-3 and T1-4.

---

## Assessment

GPT-4o performed well on Programs 1–4 — all correct on first attempt, with
accurate predictions about runtime behavior. Program 5 failed on the transitive
dependency problem, which is a real gap in the task spec and the agent-facing
docs: neither explains the index pattern for multi-symbol composition. The
`"uncertain"` route finding is the most valuable output of the session — it's a
genuine spec bug that would have gone unnoticed without a fresh agent reading the
task with no prior context.

What I'm not yet sure of: whether GPT-4o would have caught the Rust parser gap
if it had been able to run the interpreter. It might have hit it and been confused
by the error message, which doesn't clearly explain that `from`-imports require
the Python runtime.
