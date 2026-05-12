# Carryover queue — post-work readout (2026-05-11)

User asked why seven carryover items were still open. Three got done
this session; four remain deferred with explicit reasoning. This is
the post-work readout.

Paired with:
- `dispatches/2026-05-11-carryover-decisions.{readout.md,yaml}` —
  the per-item yes/no decisions and why.
- `dispatches/2026-05-11-cbor-numeric-boundaries.md` — Sable
  finding surfaced by item 1's test suite.
- `dispatches/2026-05-11-cli-audit.md` — Sable audit for item 3.
- `dispatches/2026-05-11-carryover-post.yaml` — structured form.

## What shipped

### 1. Numeric-boundary CBOR conformance. Done, with a finding.

`tests/test_cbor_boundaries.py` exercises the boundary cases the
existing conformance suite does not reach: integer head transitions,
signed zeros, exact-f16 values with unambiguous decimals, NaN/Inf
rejection. All pass.

The fixture's original design also exhaustively enumerated every
finite f16 bit pattern. Running it uncovered **a real cross-
implementation limitation**: `serde_json`'s float parser and
Python's `json` parser can produce different `f64` bit patterns
for the same decimal text on f16 subnormals and the f32 extremum.
14% of f16 patterns disagree. Filed as AUD-2026-05-11-04, P2, in
`dispatches/2026-05-11-cbor-numeric-boundaries.md`.

The exhaustive fixture is preserved as a skipped diagnostic. The
finding additionally motivates the pending primary-hash migration
to CBOR (item 4 below), which removes the JSON-text intermediate
and makes the finding structurally impossible.

### 2. Rust canonical-crate fuzz. Done.

`crates/codifide-canonical/tests/fuzz_canonical.rs` adds a small
adversarial-input fuzz harness. Zero new dependencies — uses a
xorshift64 RNG for determinism. Four tests:
- Hand-curated adversarial inputs (22 shapes targeting specific
  code paths: bad version tags, missing fields, wrong types,
  deep nesting, many believe arms, bignum-range values).
- 500 randomly-generated JSON documents.
- Valid-input round-trip stability.
- Typed-error display check.

All 4 pass. No panics found on any input. Rust canonical at 14
tests total (10 unit + 4 integration).

### 3. CLI filesystem-safety audit. Done, with one P1 fix.

Sable probed `codifide/__main__.py` file-read paths. Three findings.

- **AUD-05 P1**: unbounded source read. `codifide canonical
  /dev/zero` hung indefinitely. Same bug as P1-7 on the Rust side
  (fixed 2026-05-10); Python CLI was missed. Fixed in this session:
  `_read()` bounds reads at 16 MiB, raises typed `ParseError` on
  overage or non-UTF-8. Regression tests in
  `tests/test_cli_filesystem.py`.
- **AUD-06 P3**: `codifide run` follows symlinks. Accepted as
  documented behavior. Not a vulnerability on its own; refusing
  symlinks would break legitimate developer workflow.
- **AUD-07 P3**: `--store` accepts arbitrary paths. Accepted as
  documented behavior. Same shape as `git --git-dir=...`.

## What was deferred

### 4. Primary-hash migration JSON → CBOR.

Breaking change. Invalidates every existing content identity in the
repo. Roadmap schedules with v1.0-approach. Needs your explicit
go-ahead with a commit plan. The cross-implementation finding
AUD-04 (above) additionally motivates doing this sooner rather than
later, but "sooner" here still means "after a proposal and plan,"
not "in this session."

### 5. Store GC.

Needs a design dispatch before implementation. Open questions on
root-set semantics (time-based vs reachability-based), dry-run
discipline, and whether GC participates in the three-property
store contract.

### 6. Cost-based candidate dispatch.

Spec amendment per `GOVERNANCE.md §Decision-making`. Extends the
canonical form with cost annotations and changes dispatch
semantics. Needs a proposal dispatch, Sable audit, and your
approval before implementation.

### 7. CBOR-aware Sable re-audit.

No CBOR surface has changed since the 2026-05-10 audit. Re-audit
of unchanged surface produces duplicate findings. Deferred until a
CBOR change lands (primary-hash migration is the most likely
trigger).

## Test count

- Python: 141 passing + 1 skipped (was 129). Additions:
  - 7 CBOR boundary conformance (+1 skipped diagnostic).
  - 4 CLI filesystem-safety regression.
- Rust canonical: 14 passing (was 10). Additions:
  - 4 fuzz integration tests.

## What I'm not yet sure of

- Whether the CBOR boundary finding (AUD-04) will hold for JSON
  canonical bytes as well. The mechanism is identical; the existing
  JSON conformance passes because the examples don't hit vulnerable
  values. I did not exhaustively check.
- Whether the Rust fuzz harness catches semantic correctness
  regressions or only panic-level ones. It checks no-panic and
  round-trip stability; it does not verify bytes agree with a
  golden baseline. That could be a follow-up.
- Whether a fresh external-model experiment against the new
  capability manifest hash would reveal additional ergonomic
  misses beyond the four already reviewed.
