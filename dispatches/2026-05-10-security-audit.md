# Noema — security and soundness audit, v0.1-dev

*By Sable. 10 May 2026.*

Scope: Python reference (`noema/`), Rust canonical crate
(`crates/noema-canonical/`), specification (`docs/CANONICAL.md`),
conformance test (`tests/test_conformance.py`). Methodology: eleven
adversarial probes run against the implementations, plus a read of the
spec with a red pen.

I did not test supply-chain integrity, cryptographic agility of the hash
choice, the surface parser against fuzzed input, or the CLI against hostile
file paths. Those are listed at the end.

Severity scale: see `.kiro/steering/personas/sable.md`. Every P0 finding
has a reproducing probe and a named fix.

## Findings

### P0-1 — Effect discipline is not enforced across user-function calls

**What.** A definition with `effects {}` can call a user-defined function
with `effects {io.stdout}` and execute I/O. The "effects are in the type"
claim — the entire premise of principle #4 — does not hold today.

**Probe.**
```noema
def launder
  intent "claims pure but calls an impure callee"
  sig    () -> String
  effects {}
  cand
    impure()

def impure
  intent "actually does I/O"
  sig    () -> String
  effects {io.stdout}
  cand
    io.say("pwned")
```
`run(parse(src), "launder")` prints `pwned` and returns `"pwned"`. No
exception.

**Why it matters.** This is the core soundness claim of the language.
The README says "No expression may perform an effect not declared in its
signature." Today, any caller can reset the effect set by delegating. An
agent reasoning globally about side effects on this basis is reasoning
on false evidence.

**Where it lives.** `noema/runtime/interpreter.py::_call_primitive` only
checks the primitive-call site against `frame.defn.signature.effects`.
User-function calls go through `_invoke_internal`, which rebuilds a new
frame with the *callee's* effects and never compares callee-effects to
caller-effects.

**Fix.** Add the transitive effect check `docs/CANONICAL.md §Effect
algebra` already declares REQUIRED. At call-site before invocation, or
as a static pass at module load: verify `callee.signature.effects ⊆
caller.signature.effects`. Prefer the static pass — it rejects
ill-typed modules before they run.

**Spec status.** Spec already declares the rule. Implementation bug.

### P0-2 — Rust and Python disagree on canonical bytes for non-ASCII content

**What.** The conformance test only covers ASCII-clean examples. On a
program whose intent string contains non-ASCII, Python canonical bytes
and Rust canonical bytes are **not equal**. Therefore content hashes are
not equal. The "two implementations agree" claim in the last dispatch is
stronger than the evidence supports.

**Probe.**
```
module unicode_probe
def cafe
  intent "café with non-ASCII content"
  sig    () -> String
  effects {}
  cand
    "café"
```
Python `canonical_bytes` emits `caf\\u00e9` (ASCII-escaped — correct per
spec). Rust `canonical_bytes` emits `caf\xc3\xa9` (raw UTF-8 — wrong per
spec).

Worse: because `python3 -m noema canonical` writes the JSON with default
Python `json.dumps`, which escapes non-ASCII, but then that JSON is
*parsed back* by `serde_json` into a Rust `String` (already unescaped
UTF-8), and re-serialized by `serde_json::to_vec` (which does NOT escape
non-ASCII by default) — the round-trip loses the escape. The Rust intent
string also shows double-UTF-8 encoding (`caf\xc3\x83\xc2\xa9`), meaning
`python -m noema canonical` itself is emitting
UTF-8-interpreted-as-Latin-1 somewhere. Two bugs, not one.

**Why it matters.** Content addressing is meaningless if implementations
disagree on the bytes a symbol hashes to. Two agents cannot exchange
symbols by identity. The foundation the language was just claimed to
stand on is only solid for ASCII.

**Where it lives.**
- `noema/__main__.py::cmd_canonical` uses `json.dumps(..., indent=2)` —
  default `ensure_ascii=True` — but the *bytes* a Python consumer hashes
  are produced by `canonical_bytes` which also uses `ensure_ascii=True`,
  so the Python side is internally consistent.
- The Rust side in `crates/noema-canonical/src/canonical.rs::canonical_bytes`
  uses `serde_json::to_vec` which does not escape non-ASCII by default,
  and does not match.
- Separately, the double-UTF-8 in the Rust-parsed intent suggests the CLI
  JSON output path is corrupting non-ASCII at emit time.

**Fix.** Two changes.
1. Make Rust `canonical_bytes` use an ASCII-escaping serializer (either
   `serde_json::Serializer` with a custom formatter, or manual escaping).
   Match Python's `\uXXXX` output byte for byte.
2. Audit the Python `cmd_canonical` emission path for mojibake. Likely a
   missing `ensure_ascii` on the pretty-printed output, combined with
   whatever is re-reading it; repro suggests the file is being written
   UTF-8 and read as Latin-1 somewhere in the chain.
3. Add a non-ASCII conformance fixture — a `.nm` file with non-ASCII in
   intent, string literal, and (eventually) identifier — and require
   byte equality.

**Spec status.** Spec §Canonical serialization says "control bytes
`\u00XX` escaped" but does not explicitly mandate ASCII-escaping for all
non-ASCII. Spec gap — tighten the spec and fix both implementations to
match.

### P1-1 — Host-language exceptions leak through the typed error surface

**What.** Arithmetic, collection, and sentinel operations raise raw Python
exceptions (`ZeroDivisionError`, `TypeError`, `IndexError`) that are not
subclasses of `NoemaError`. A host embedding Noema cannot reliably
distinguish Noema-level failures from runtime bugs. Error classification
is a language feature; it is broken.

**Probes.**
```
div(1, 0)             -> ZeroDivisionError: division by zero
add(1, bottom)        -> TypeError: expected a number, got _BottomType
head(list())          -> IndexError: list index out of range
```

**Why it matters.** Principle: "Boolean is the special case where P=1.
Exact arithmetic is delegated to verified primitives." Verified
primitives need to report failure in the language's error vocabulary, not
in Python's. Today, a host has to `except Exception` and guess.

**Fix.** Wrap primitive invocation in `_call_primitive` with a try/except
that maps Python exceptions to a new `PrimitiveError(NoemaError)` carrying
`fn`, `args`, and the underlying cause. Update `add`/`sub`/`div` and
collection primitives to raise early with typed errors where meaningful
(e.g., `div` raising on `b == 0` before Python does). Propagating `bottom`
into arithmetic should be a typed `BottomPropagationError`, not a
`TypeError`.

**Spec status.** Spec does not enumerate primitive error classes. Spec
gap — §Errors section needed.

### P1-2 — Deep recursion crashes the host

**What.** A module with ~500 chained single-call definitions exhausts the
Python interpreter stack and raises `RecursionError`.

**Probe.** Generated module of 500 `f_i calls f_{i+1}` definitions →
`RecursionError: maximum recursion depth exceeded`.

**Why it matters.** A hostile or simply careless `.nm` input can crash a
host that embeds Noema. It is not currently possible to limit recursion
depth from the host side without monkey-patching `sys.setrecursionlimit`,
which affects the whole process.

**Fix.** The tree-walking interpreter can enforce its own call-depth
limit independent of the Python stack: count frames in
`_invoke_internal` and raise `DispatchError("recursion limit")` past a
configurable bound (default 1000). Phase 2: trampoline the evaluator.
Phase 3 (v0.3 Rust runtime): this concern disappears.

**Spec status.** Spec does not address resource bounds. Spec gap.

### P2-1 — Preconditions, postconditions, and guards may perform effects
the signature declared, but not all types of "implicit effect" are considered

**Partial false alarm, partial finding.** The effect system DOES correctly
reject a `post` clause that calls an undeclared primitive (probe 4
returned `EffectViolation` as expected — good). But pre/post/guard
expressions still execute with full effect-budget of the surrounding
signature, meaning a postcondition CAN legitimately perform I/O or model
calls so long as the signature declares them.

**Why it matters.** A postcondition that reads a clock is fine; a
postcondition that writes to stdout is fine per current rules but
conceptually smells. Contracts should be pure by default: they describe
state, they do not modify it. A function that declares
`effects {io.stdout}` and puts `io.say(...)` in its `post` does not
violate any rule today, but the emitted stdout will be attributed to the
contract check, not the body.

**Fix.** Spec decision: declare contracts pure. Enforce by evaluating
pre/post/guard with a reduced effect set = ∅ (the current declared
effects subtracted down). Implementation: a local override of the frame's
declared effect set during contract evaluation.

**Spec status.** Spec does not say. Spec gap — §Contracts should state
"pre, post, and guard expressions must be pure; their effect set is ∅."

### P2-2 — Module name is parsed as an unrestricted free-form string

**What.** `module foo; import os; os.system(...)` parses without complaint
and the module's `name` field becomes the full string including the
injection attempt. No code executes (the parser does not eval the
payload), so this is not a P0 or P1, but the canonical form now contains
content that looks like code to every downstream tool that displays it.

**Probe.** The file parsed cleanly; `m.name` returned
`'foo; import os; os.system("touch /tmp/NOEMA_PWNED")'`. No file was
created.

**Why it matters.** Tools that render `module` in UIs, logs, error
messages, or dispatches will present injection-looking strings to humans
without distinguishing "parsed identifier" from "accidentally plausible
Python."

**Fix.** Restrict module names to `[A-Za-z_][A-Za-z0-9_.-]*` at parse
time. Reject with a `ParseError` otherwise.

**Spec status.** Spec does not define the module-name grammar. Spec gap.

### P3-1 — Intent is included in the content hash today by accident, not by rule

**What.** Two definitions with identical bodies but different intents
produce different content hashes. Renaming a symbol also changes the
hash. Both behaviors are probably correct, but neither is specified.

**Probe.** `content_hash` of two definitions identical except for intent
differs (`sha256:48d7... vs sha256:f8f0...`). Same for rename
(`sha256:48d7... vs sha256:291b...`).

**Why it matters.** Content-addressing behavior is currently
"whatever `json.dumps` happens to hash." If intent is truly first-class
and preserved forever, the rule should be: hash is taken over
(name, intent, signature, pre, post, candidates). This is what we have,
but it should be by choice, not by accident.

**Fix.** Write the rule into `docs/CANONICAL.md §Content addressing`.
No code change.

**Spec status.** Spec gap.

## Not-findings (explicitly cleared)

- **Sandboxing via attr chains.** `io.say.__globals__.os.system(...)` is
  rejected as `unknown callable` — the interpreter looks up the dotted
  path in the primitive registry and the module symbols, not in Python
  attributes. Clean.
- **Unknown expression kinds in canonical JSON.** `from_canonical` raises
  `ValueError: unknown expression kind: 'backdoor'`. Validation holds.
- **Adversarial intent strings with format specifiers.** The parser
  rejects a multi-line malformed string literal before it reaches error
  formatting. Error formatters would need separate review if the parser
  ever accepted them.
- **Parameter named `result` shadowing postcondition `result`.**
  Behavior: the parameter wins in user-supplied bindings, but the
  interpreter overwrites `result` with the actual return value before
  running the post clause. Post sees the true result. Correct, though
  spec should state the shadowing rule.
- **Rust CLI on malformed input.** Bad JSON and bad version both exit 1
  with clean error messages. No panics.

## What I did not test

- Supply-chain integrity of Rust dependencies (`serde_json`, `sha2`,
  their transitive set). The crate compiled; nothing was audited for
  known CVEs or typosquatting.
- Surface parser against fuzzed input. The parser is small and
  hand-written; a structured-grammar fuzzer would likely surface panics
  or hangs.
- CLI against hostile file paths (symlinks, `/dev/zero`, very large
  files, files that grow during read).
- Concurrency. The tree-walking interpreter is single-threaded; the
  claim "parallelism is default" is not yet anywhere in the code.
- Cryptographic agility of the hash choice. SHA-256 is a reasonable
  v0 choice; the spec says `sha256:` but does not provide for
  migration to a different algorithm.
- Contract-clause syntax: whether preconditions can shadow primitive
  names and break effect tracking.
- Belief-in-believe nesting — flagged in the original dispatch as an
  unknown and still untested.

## Summary

Two P0 findings, two P1 findings, two P2 findings, one P3. The two P0s
are:

1. Effect discipline does not cross function boundaries (the language's
   main advertised property does not hold).
2. Canonical byte form disagrees between Python and Rust on non-ASCII
   content (the foundation for "two implementations" holds only for
   ASCII input).

Both are spec gaps the spec writers saw and named as future work; the P0
severity is because the language claims today that they are solved. Either
the spec stops claiming them or the implementations start enforcing them.
Ship blocker on both counts for any release that wants to be called stable.

Fix list, for whoever picks it up next:
- Implement transitive effect check (P0-1).
- Fix Rust `canonical_bytes` to emit ASCII-escaped JSON byte-identical to
  Python, plus add non-ASCII conformance fixture (P0-2).
- Wrap primitive errors in typed `NoemaError` subclass (P1-1).
- Interpreter-level recursion limit (P1-2).
- Spec: contracts are pure (P2-1).
- Spec + parser: module-name grammar (P2-2).
- Spec: intent in hash, explicitly (P3-1).
