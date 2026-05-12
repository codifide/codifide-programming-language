# Carryover items — decisions (2026-05-11)

User asked why seven items carried forward from prior sessions are
still open. Fair challenge. This readout records the per-item yes/no
with reasoning so the queue is not mysterious.

Paired with `dispatches/2026-05-11-carryover-decisions.yaml`.

## Do in this session

### 1. Numeric-boundary CBOR conformance. YES.

*Why.* Pure test addition. Enumerate f16 bit patterns, selected f32
edges, NaN/infinity rejection; assert Python and Rust produce byte-
identical output through the existing conformance harness. No
behavior change, low risk, closes a coverage claim that today rests
only on the examples the conformance test happens to cover.

*Scope.* New test file `tests/test_cbor_boundaries.py`. No impl
changes expected; if Python and Rust disagree on some edge, that
is a finding to file, not something to silently fix.

### 2. Rust canonical-crate fuzz. YES.

*Why.* The Python fuzz harness exists; the Rust crate has none.
Adversarial canonical JSON input (bad keys, wrong types, huge
numbers, deep nesting) should produce typed errors on the Rust
side, not panics. Same value as the Python fuzzer, different
surface.

*Scope.* A small Rust test module that feeds a battery of hand-
curated and randomly-generated adversarial JSON into
`codifide_canonical::json::from_json_module` and asserts no panic,
errors typed. Not a `cargo-fuzz` harness — too heavy for this
session. A quickcheck-style loop inside `cargo test`.

### 3. CLI filesystem-safety audit. YES.

*Why.* The store was hardened on 2026-05-10 (P1-5 symlink escape,
TOCTOU defense). The Python CLI (`codifide/__main__.py`) itself has
not been audited. Same audit shape Sable used on the CBOR
neighborhood: probe the file-read paths on `codifide run`,
`codifide canonical`, `codifide store put`, `codifide capability`
with adversarial inputs (`/dev/zero`, symlinks, huge files, path
traversal). File findings; fix P1s in-session; surface P0s and
stop for user direction.

*Scope.* `dispatches/2026-05-11-cli-audit.md` with severity-rated
findings; fixes in `codifide/__main__.py` as needed; post-audit
dispatch attesting resolution.

## Hold with explicit rationale

### 4. Primary-hash migration from JSON to CBOR. NO (this session).

*Why not.* Breaking change. Every existing content hash becomes
stale — the capability manifest hash in today's CHANGELOG, every
stored symbol, every dispatch that cites a hash. The roadmap
explicitly schedules this for a v1.0-approaching release because a
breaking change of that scope should ship together with other
breaking changes, not piecemeal.

*What would unblock.* Your explicit go-ahead that now is the right
time, paired with a plan for regenerating all hashes in the repo
in one commit. Not a technical question; a timing question.

### 5. Store GC. NO (this session).

*Why not.* Needs a design pass first. Open questions:
- What is the root set? Time-based? Reachability-based from a
  manifest or index?
- Is `store gc` dry-run-first or opt-in?
- Does GC participate in the three-property contract (hash-verified
  reads/writes, idempotent writes)?

*What would unblock.* A paired Quill/Glyph design dispatch with
answers to those questions and a Sable audit of the proposed
semantics. Then implementation is mechanical.

### 6. Cost-based candidate dispatch. NO (this session).

*Why not.* Extends the canonical form (cost annotations on
candidates) and the dispatch semantics. `GOVERNANCE.md §Decision-
making` requires a dispatch proposal + Sable audit + Douglas's
approval on the spec amendment before implementation. Correct
process; I should not collapse it.

*What would unblock.* A proposal dispatch for the spec amendment.

### 7. CBOR-aware Sable re-audit. NO (this session).

*Why not.* Sable audited CBOR on 2026-05-10 and found three P1s,
all fixed and regression-tested. Since then, no CBOR-touching code
has changed — today's ergonomics pass was parser, primitives, and
error messages only. A re-audit of unchanged surface would produce
the same findings.

*What would unblock.* A CBOR-surface change (e.g., the primary-hash
migration above) that creates new surface to audit.

## What I'm not yet sure of

Whether the CLI audit will surface any P1 findings. If it does, I
will fix them in this session and attest. If it surfaces a P0
(unlikely but possible — e.g., a path that leaks host filesystem
contents into stdout under adversarial input), I will stop and
surface it for explicit direction before fixing, per the
`safety_guardrails` rule on high-risk operations.
