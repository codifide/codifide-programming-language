# Sable — CBOR numeric boundary finding (2026-05-11)

Auditor: Sable
Scope: Python ↔ Rust canonical CBOR agreement on numeric values the
existing conformance test suite does not exercise.

## Finding AUD-2026-05-11-04 — P2 — JSON decimal parser disagreement

**What.** Python's ``json`` parser and ``serde_json``'s parser (used
by the Rust canonical binary) can produce different ``f64`` bit
patterns for the same decimal text. When they do, the downstream
canonical CBOR encoder produces different bytes on each side for
what is nominally the same input.

**Probe (reproduction).**

The decimal text ``5.960464477539063e-08`` is the shortest exact
decimal for the smallest f16 subnormal (bit pattern ``0x0001``).

- Python's ``json.loads("5.960464477539063e-08")`` returns the
  ``f64`` with bit pattern ``0x3e70000000000000``.
- ``serde_json::from_str(...)`` on the same text returns the
  ``f64`` with bit pattern ``0x3e70000000000001`` — one ULP higher.

The delta propagates. Python's canonical CBOR encoder produces
``f9 00 01`` (half precision, two bytes). The Rust encoder, seeing a
slightly different double, correctly detects that half-precision is
not exact and falls back to ``fb 3e 70 00 00 00 00 00 01`` (nine
bytes).

Same mechanism applies to the f32 extremum
``3.4028234663852886e+38``: Python reads it as exact f32-max, Rust
reads it as f32-max + 1 ULP and encodes as f64.

A sampling sweep over 2000 f16 bit patterns found **287 mismatches
(14.35%)**, concentrated in subnormals.

**Why it matters.** The cross-implementation conformance claim the
project rests on is: "Python and Rust produce byte-identical
canonical CBOR on identical input." That claim currently holds *only*
because every ``.cod`` example happens to use numeric values whose
decimal text round-trips through both parsers to the same ``f64``.
The existing conformance suite is coverage-theater on the numeric
front: it passes because its inputs are narrow, not because the
claim is robust.

A consumer minting content hashes in Python and a consumer verifying
them in Rust can silently disagree on the hash of a CBOR module
whose canonical form contains a float with a subnormal-class
decimal representation. That is a soundness problem for content
addressing under CBOR.

**Severity.** P2. Not a crash. Not a sandbox escape. Not a silent
data leak. But the cross-implementation conformance claim is
weaker than the spec language suggests, and users planning to mint
content-addressed identities in one implementation and verify them
in another need to know the claim's actual scope.

**Spec bug alongside.** ``docs/CANONICAL.md §Canonical
serialization`` describes the CBOR byte form in terms of the
abstract value being encoded. It does not say "the canonical bytes
depend on how the value was parsed from JSON text." That is silence
on a material point. The spec should either:

- Narrow the claim to values that round-trip through both JSON
  parsers (unsatisfying — the set is hard to describe precisely),
  OR
- State that canonical CBOR is defined over the parsed ``f64``
  bits, not the decimal text, and move the primary content-hash
  path toward CBOR-first (avoiding JSON-text as an intermediate
  entirely). This path aligns with the pending primary-hash
  migration scheduled for v1.0.

**Recommended fix (authoring persona, not me).**

1. **Short term.** Document the limitation in ``docs/CANONICAL.md``.
   Narrow the conformance test's claim to: "identical in-memory
   f64 values produce identical canonical CBOR bytes." State that
   feeding the Rust binary decimal text is not a reliable path for
   values near half-precision subnormals or the f32 extremum.
2. **Medium term.** Add a Rust binary subcommand that accepts a
   binary input (the canonical byte form) rather than JSON text,
   so the Python side can hand the Rust side an exact byte image
   to re-encode. Removes the JSON-parser round-trip as a variable.
3. **Long term.** The pending JSON→CBOR primary-hash migration
   (carryover item, scheduled for v1.0-approach) removes JSON-text
   as an intermediate form on the content-address path, closing
   this finding structurally.

**What I did not test.**

- Whether the same parser disagreement affects the JSON canonical
  byte form (``canonical_bytes`` / ``content_hash``). Likely yes by
  the same mechanism, since the Rust side also round-trips through
  ``serde_json::from_str`` before emitting canonical JSON. The
  existing conformance test passes because the examples don't
  exercise the vulnerable values. I did not exhaustively check.
- Whether bignum-range integers agree (the conformance test covers
  up to ``(1 << 63) - 1`` which is the largest value i64 can hold
  and the largest that fits in a CBOR major-type-0 head without
  bignum tags). Values above that would use tag 2 / tag 3 bignum
  encoding; I did not probe.
- Whether the JSON parser disagreement also manifests for very
  large or very small magnitudes across the f64 dynamic range. The
  probe was concentrated in f16 territory.

## Post-finding expectations

- The boundary test suite (``tests/test_cbor_boundaries.py``)
  narrows its scope to what actually agrees: integers, signed
  zeros, and exact-f16 values with short unambiguous decimals.
- The exhaustive f16 fixture is retained as a skipped diagnostic;
  un-skipping it is the regression signal for "the parser
  divergence closed."
- The primary-hash migration to CBOR (open item from 2026-05-10)
  is now additionally motivated: it removes the JSON-text
  intermediate from the content-address path and makes this
  finding structurally impossible.
