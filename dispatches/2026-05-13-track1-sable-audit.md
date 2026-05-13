# Sable Audit — Track 1 Agent Case Studies

**Date:** 2026-05-13  
**Persona:** Sable  
**Scope:** T1-2 (GPT-4o), T1-3 (Gemini 2.5 Pro), T1-4 (Claude baseline)  
**Initiative:** Agent Adoption — Track 1, Task T1-6

---

## Audit scope

Three external agent sessions ran the content-moderation pipeline task. Each
produced five programs. Quill reported on each session. This audit reviews
what Quill reported, probes the claims, and surfaces findings the journalists
missed or understated.

---

## Findings

### AUD-T1-01 (P2) — `is_bottom()` is documented as a refusal helper but cannot catch propagated refusals

**What:** The capability manifest lists `is_bottom` under primitives with no
caveat. The quickref (before the fix) listed it under "Refusal helpers" with
no warning. Gemini used it as a propagation catcher — dead code that silently
does nothing.

**Probe:** `python3 -m codifide run` with a function that binds the result of
a refusing function and calls `is_bottom()` on it. Result: `BottomPropagationError`
— `bottom` propagates through the bind before `is_bottom()` sees it.

**Status:** Fixed. Quickref updated. Runtime hint added. But the capability
manifest still lists `is_bottom` with no caveat. An agent reading only the
manifest (not the quickref) will still fall into this trap.

**Residual fix needed:** Add a `note` field to the `is_bottom` entry in the
capability manifest generator, or add a `caution` section to `docs/CAPABILITY.md`
covering primitives with non-obvious semantics.

**Severity:** P2 — any agent using only the manifest as context will hit this.

---

### AUD-T1-02 (P2) — Bind-before-when is a syntactic trap with no static detection

**What:** Claude hit `unbound name: 'label'` when using a bind before a `when`
guard in the same `cand` block. The pattern is syntactically accepted by the
parser — it is not a parse error. The runtime raises the error only when the
guard evaluates and the name is not in scope.

**Probe:** Write a `cand` block with `name <- expr` followed by `when eq(name, x)`.
Parser accepts it. Runtime raises `unbound name: 'name'`.

**Status:** Fixed. Runtime hint added. Quickref updated. But the parser does
not reject this pattern statically — it is a runtime error, not a parse error.
An agent that writes this pattern and gets the error mid-session loses context
on why it happened.

**Residual fix needed:** The parser could detect bind-before-when statically
and raise a `ParseError` with a clear message. This would surface the error
earlier and with better context than a runtime `unbound name`. Filed as a
future improvement — not blocking, but worth tracking.

**Severity:** P2 — Claude hit it; GPT-4o and Gemini avoided it by accident
(different routing patterns). Any agent that reaches for the idiomatic
multi-branch dispatch shape will hit it.

---

### AUD-T1-03 (P1) — Program 5 requires `CODIFIDE_RUNTIME=python` but this is not surfaced at the task level

**What:** `from`-imports require the Python runtime. The Rust parser does not
support them. The error message is:

```
parse error: from-import requires a store and is not yet supported in the
Rust parser. Use `import name = sha256:<hex>` for direct identity binding.
```

The error message is accurate but the suggested fix (`import name = sha256:...`)
does not work for multi-symbol composition with transitive dependencies. An
agent following the error message's suggestion will hit the transitive
dependency problem next.

**Probe:** Write a `from`-import and run without `CODIFIDE_RUNTIME=python`.
Error fires. Follow the error's suggestion (`import name = sha256:...`). Hit
`unknown callable` for the transitive dependency.

**Status:** Partially fixed. Quickref documents `CODIFIDE_RUNTIME=python`.
The error message's suggested fix is still misleading — it points at a pattern
that doesn't solve the underlying problem.

**Residual fix needed:** Update the Rust parser error message to say: *"Use
`CODIFIDE_RUNTIME=python` to enable from-imports, or use an index to bundle
all transitive dependencies before importing."*

**Severity:** P1 — every agent hits this on Program 5. The current error
message actively misleads.

---

### AUD-T1-04 (P3) — `belief(...)` return type mismatch is silently accepted

**What:** GPT-4o flagged this honestly: `belief(...)` returns `Any` in the
manifest, but function signatures declare `-> Label`. The runtime does not
enforce declared return types against belief wrappers. An agent that declares
`-> Label` and returns `belief("unsafe", 0.90)` gets no error — the belief
value passes through.

**Probe:** Declare `sig () -> Int` and return `belief("not-an-int", 0.90)`.
No error. The belief wrapper bypasses the declared return type.

**Status:** Not fixed. This is a known design choice — belief values are
intentionally typed as `Any` because the confidence annotation is the primary
type information. But it means declared return types on belief-returning
functions are decorative, not enforced.

**Residual fix needed:** Either (a) document explicitly that return types are
not enforced for belief-returning functions, or (b) add a note to the manifest
that `belief(...)` returns `Any` and the declared return type is advisory.
Option (a) is lower cost.

**Severity:** P3 — no agent was confused enough to fail because of this, but
GPT-4o flagged it as a genuine uncertainty. The docs should be honest about it.

---

### AUD-T1-05 (P3) — `main_refuse` test name is misleading after spec fix

**What:** The task spec asks agents to write `main_refuse` to demonstrate the
refusal path. After the spec fix (uncertain confidence raised to 0.75), `"hello
world"` no longer refuses — it returns `"uncertain"`. The test name implies
refusal but the behavior is now "returns uncertain."

**Probe:** Run `main_refuse` with `"hello world"`. Returns `"uncertain"`, not
`RefusalError`.

**Status:** Not fixed. The task spec still has `main_refuse` as the entry name.
This is a test design issue, not a language issue.

**Residual fix needed:** Either rename `main_refuse` to `main_uncertain` in the
task spec, or use a message with no keywords and confidence below 0.70 (which
requires adding a third classifier tier). The simplest fix: rename the entry
point and update the expected output in the spec.

**Severity:** P3 — cosmetic, but misleading for future agents running the spec.

---

### AUD-T1-06 (P3) — No agent tested the `"escalate-to-human"` path end-to-end

**What:** All three agents wrote the `"escalate-to-human"` candidate in
`route_message` but none tested it with a message that actually reaches it.
With the current spec (uncertain confidence 0.75, gate at 0.70), `"uncertain"`
passes through `moderate` and should reach `route_message`. But no agent's
`main` function used a message that produces `"uncertain"`.

**Probe:** Run `route_message` with `"hello world"` (no keywords → uncertain
0.75 → passes gate → should route to `"escalate-to-human"`). Result: `"escalate-to-human"`.
The path works — but no agent verified it.

**Status:** Not fixed. The task spec should require testing all three routing
paths explicitly.

**Residual fix needed:** Add a third test message to the `main` function
requirement in Program 3 — one that produces `"uncertain"` and routes to
`"escalate-to-human"`.

**Severity:** P3 — the path works, but untested paths are unverified claims.

---

### AUD-T1-07 (P2) — `bottom`-adjacent primitives not audited in manifest

**What:** The pre-T1-4 fixes dispatch noted that `is_bottom()` is a trap.
The post-T1-4 fixes dispatch asked whether other `bottom`-adjacent primitives
exist. Sable probed the full primitive registry.

**Probe:** Every primitive that takes a value argument was called with `bottom`
as input. All raise `BottomPropagationError` — the interpreter's pre-call check
catches `bottom` before any primitive lambda runs. This is correct behavior.

**Finding:** No other `bottom`-adjacent traps exist in the primitive registry.
`is_bottom()` is the only primitive that takes `bottom` as a meaningful input
(it returns `True` for it). All others correctly refuse it.

**Status:** No fix needed for the primitives themselves. The `is_bottom()`
documentation gap is the only issue, and it is partially addressed.

**Severity:** P2 for the manifest documentation gap (see AUD-T1-01). P0 for
the primitive behavior itself: none found.

---

## Cross-session patterns

**Pattern 1 — Program 5 is the universal failure point.**
All three agents failed Program 5 on first attempt (GPT-4o and Gemini) or
required runtime-specific knowledge (Claude). The transitive dependency problem
and the Rust parser gap are the two blockers. Both are now documented. The
error message for the Rust parser gap still misleads (AUD-T1-03).

**Pattern 2 — Anticipatory reasoning varies significantly by model.**
GPT-4o: correct on first attempt, no self-corrections. Gemini: predicted three
errors before writing, self-corrected all. Claude: one real error (bind-before-when),
fixed immediately. The models have different failure modes — GPT-4o fails silently
(latent `lower()` bug), Gemini fails loudly but recovers, Claude fails on
execution-order assumptions.

**Pattern 3 — The `believe` block is well-understood; routing after it is not.**
All three agents correctly wrote `believe` blocks. All three struggled with
what to do after `moderate` returns a label — how to route on a string value.
GPT-4o used `believe` on string values (wrong, but self-corrected). Gemini used
`if/then/else` with `is_bottom()` (dead code). Claude used bind-before-when
(runtime error). The routing pattern after a `believe` block is the hardest
part of the task.

**Pattern 4 — Effects are well-understood.**
No agent failed on effect declarations. All correctly identified `effects {}`
for pure functions and `effects {io.stdout}` for I/O. Gemini missed `effects
{io.stdout}` on `main` but predicted the error and self-corrected. This is
the most-documented feature and it shows.

---

## What I did not test

- Whether the Rust interpreter produces the same results as the Python
  interpreter for all five programs across all three sessions. The case studies
  used the default runtime (Rust for Programs 1–4, Python for Program 5).
  Cross-runtime conformance on these specific programs was not verified.
- Whether the `from`-import error message change (AUD-T1-03) would actually
  help — the fix was not applied, so no probe was possible.
- Whether a static bind-before-when check in the parser is feasible without
  a full type system. The parser currently has no scope tracking; adding it
  would be a non-trivial change.
- The `belief(...)` return type enforcement question (AUD-T1-04) — whether
  adding enforcement would break existing programs that rely on the current
  permissive behavior.
