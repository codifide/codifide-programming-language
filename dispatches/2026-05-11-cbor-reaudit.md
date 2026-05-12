# Sable — re-audit of CBOR/JSON canonical byte form (2026-05-11)

Auditor: Sable
Scope: the CBOR and JSON canonical byte-form surface.

This re-audit was prompted not by new code but by new knowledge:
AUD-2026-05-11-04 uncovered a cross-parser decimal-text disagreement
between `serde_json` and Python's `json` on f16-subnormal and f32-
extremum values. That changes what I should probe for.

## Findings

### AUD-2026-05-11-08 — P1 — JSON canonical bytes diverge for f16-class floats

**What.** The cross-implementation conformance claim
("identical canonical JSON bytes, identical SHA-256 content
hash") fails on floats that hit shortest-decimal divergence
between the Python writer and the `serde_json`
writer/reader stack. Two mechanisms:

- **Writer divergence.** Python's `json.dumps` and `serde_json`
  emit different shortest-decimal forms for the same `f64`.
  Python emits `5.960464477539063e-08`; Rust emits
  `5.960464477539064e-8` (one ULP off in the significand, plus
  the exponent is written `e-8` vs `e-08`).
- **Reader divergence.** Even if the written text agreed, Python's
  parser and `serde_json`'s parser produce different `f64` bits
  for the same decimal text in some cases. Also documented as
  AUD-04 at severity P2; I was under-scoping it then.

**Probe.**

```python
from codifide.core.types import Module, Definition, Signature, Candidate, Lit
from codifide.projection.canonical import canonical_bytes, content_hash

v = 5.960464477539063e-08
module = Module(
    name="b",
    symbols=(Definition(
        name="n", intent="p", signature=Signature(),
        pre=(), post=(),
        candidates=(Candidate(body=Lit(v, type="Number"), intent="d"),),
    ),),
    imports=(),
)
print(content_hash(module))
# sha256:8ed16fe133908d56146bf3b1ad8a2820a31f5e5d60d938afd52125625bce1f50

# Rust CLI on the same canonical JSON:
# sha256:e5aff7f56d64f9529e195f2ad4ca5d833cb563e2c36984e7ee0aa6eb32ca4018
```

**Why it matters more than AUD-04 said.**

AUD-04 filed this as a P2 under the CBOR canonical byte form. I
missed that the **JSON primary hash has the same bug** by the same
mechanism — because the Rust side round-trips the JSON text through
`serde_json::from_str`, the writer divergence produces different
in-memory `f64` values on each side, which then canonicalize to
different JSON bytes, which then hash differently.

The current test suite does not catch this because the `.cod`
examples don't use vulnerable values. The cross-implementation
conformance test claims JSON byte agreement, but the claim's
actual scope is narrower than the spec wording: "agrees on values
that round-trip through both float writers and both parsers
identically." That scope is not described anywhere in the spec.

**Severity.** P1. Upgraded from the P2 in AUD-04. Content hashes
are the language's cross-implementation identity story; an
implementation that mints a hash in Python and another
implementation that verifies it in Rust can silently disagree on
the hash of any module containing an f16-class float. This is
reachable from idiomatic Codifide code (anywhere a float literal near
the half-precision boundary appears in a program, postcondition,
or guard).

**Fix options.**

- **(a) Rust side adopts Python's shortest-form output.** Narrow,
  non-breaking for identities. Requires replacing `serde_json`'s
  writer with a custom one that matches Python's `repr()` for
  floats. Work, but the cleanest option for v0.2.
- **(b) Spec restricts canonical form to integers and exact-decimal
  floats.** Disallows float values that don't round-trip identically
  between the two writer libraries. Simple spec; tight constraint
  on what Codifide programs can express as literals.
- **(c) Accelerate primary-hash migration to CBOR.** CBOR hashes
  over IEEE-754 bits, not decimal text. The writer/reader
  divergence is structurally impossible in that representation.
  This is already a scheduled roadmap item; the finding is one
  more reason to prioritize it.

**Recommendation.** (c), with (b) as a stopgap spec clarification
for the v0.x line until the CBOR primary-hash migration lands. Do
**not** take option (a) — writing a custom Rust float serializer
is fragile and long-term unproductive; CBOR is the right answer.

### AUD-2026-05-11-09 — P3 — spec does not state canonical form's float-text contract

**What.** `docs/CANONICAL.md` §Canonical serialization describes
the byte form in terms of "JSON with sorted keys and minimal
whitespace." It does not say how floats are written. The Python
and Rust implementations each follow their local library's
shortest-decimal algorithm; those algorithms are not guaranteed
to agree, and indeed they don't (AUD-08).

**Severity.** P3. Spec bug that enables the code bug. Fix by
either:

- Naming a specific shortest-decimal algorithm in the spec
  (Grisu3, Ryu, Dragon4 with a tie-breaking rule) and requiring
  both implementations to match it, or
- Removing floats from the JSON canonical form (the CBOR form
  sidesteps this entirely).

Either way, this is a spec-change dispatch, not a fix.

### AUD-2026-05-11-10 — P3 — integer boundary conformance surface is narrow

**What.** The test suite's integer boundary tests
(`IntegerBoundaryConformance`) cover values up to `(1 << 63) - 1`.
The canonical form in principle supports arbitrary-precision
integers via CBOR bignum tags (major type 6, tags 2/3). Python's
`json` happily emits Python ints of any size. The Rust side reads
through `serde_json::Number`, which has an `as_i64`/`as_u64`
path but no arbitrary-precision path enabled by default.

**Probe.**

I did not run a reproducing probe in this audit. This is filed as
a suspected gap, confidence 0.7. Resolving requires attempting
`Lit(1 << 128, type="Int")` end-to-end and observing whether the
Rust side rejects it or silently truncates.

**Severity.** P3. Conjectural pending the probe.

## What I did not test

- Integer values above 2^63 end-to-end. Suspected regression;
  unverified.
- NaN boxing or IEEE-754 payload preservation on round-trip. CBOR
  canonical form refuses NaN outright; the JSON form silently
  preserves it via `Infinity`/`NaN` (Python's `json.dumps(allow_nan=True)`
  default). Did not probe whether the Rust side accepts or rejects.
- Whether the float-bytes disagreement extends to ordinary
  human-scale doubles (3.14159, 2.718281828). My sampling focused
  on f16-class values.
- The impact on the capability manifest hash. The manifest is
  primarily integer and string data; a probe of whether float
  content there creates hash splits was not performed. Confidence
  0.8 that it is unaffected today because the manifest's only
  float is `conf: 1.0` on AST literals, which is exact on all
  paths.

## Post-audit disposition

- **AUD-08 (P1)** is a live finding. It should not be shipped without
  either a fix or an explicit narrowing of the cross-implementation
  conformance claim. My recommendation is to accelerate the CBOR
  primary-hash migration, which closes it structurally. **This is
  the user's call, not Sable's.** Documented in the migration
  proposal at
  `dispatches/2026-05-11-primary-hash-migration-proposal.{readout.md,yaml}`.
- **AUD-09 (P3)** is a spec clarity issue. Filed for the next spec
  amendment pass.
- **AUD-10 (P3)** is conjectural; resolve with a probe, then file
  at confirmed severity.

I do not propose a short-term code fix for AUD-08. The right answer
is the CBOR migration, not patching around the decimal-text issue
in Python or Rust. If you reject the migration proposal, **the
fallback is to narrow `docs/CANONICAL.md` §Canonical serialization
to disallow floats outside the exact-binary subset**, and to have
`canonical_bytes` raise on floats that cannot be exactly represented
as binary fractions.
