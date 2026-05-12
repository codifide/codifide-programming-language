# Rust CBOR-input subcommand — post-work (2026-05-11)

Follow-on to the three-migration pass. Closes the residual surface
that remained after the primary-hash migration flipped to CBOR.

## What shipped

Two new Rust CLI subcommands and a strict canonical-CBOR decoder
in the `codifide-canonical` crate:

- `codifide-canonical bytes-cbor-in <file.cbor>` — decode canonical
  CBOR, round-trip through the AST, re-emit canonical CBOR.
- `codifide-canonical hash-cbor-in <file.cbor>` — same path, but
  return the `sha256:<hex>` of the re-encoding.

The decoder (`crates/codifide-canonical/src/cbor_decoder.rs`) is a
direct port of the Python strict decoder. It rejects:

- Non-shortest integer heads.
- Unsorted map keys.
- Duplicate map keys.
- Indefinite-length strings.
- NaN and infinity in any float width.
- Trailing bytes after the value.
- Truncated input.
- Unsupported tags (bignums are named out; we don't use them in
  canonical Codifide modules today).

14 in-crate unit tests cover the round-trip invariants, rejection
paths, and a specific AUD-08 witness (`0x3e70000000000000`, the
smallest f16 subnormal as f64).

## What's closed

**AUD-2026-05-11-08 (P1) is now structurally closed end-to-end.**

Before this pass: the primary-hash migration made the Python side
hash over CBOR bytes, closing AUD-08 on the Python path. But the
Rust CLI still accepted canonical JSON *text* as its only input
format, which meant feeding it the JSON projection of a module
containing an f16-class float went through `serde_json::from_str` —
the decimal parser whose output disagrees with Python's `json.loads`.
The f16 exhaustive diagnostic stayed skipped.

After this pass: the test un-skips and passes. Every finite f16 bit
pattern now produces byte-identical canonical CBOR on both
implementations when the input travels as canonical CBOR bytes. The
residual surface is gone.

The JSON-input subcommands still exist and still have the
decimal-parser limitation when fed JSON text containing f16-class
floats. That limitation is documented in `docs/CANONICAL.md
§Content addressing` and is no longer a P1 because users who care
about byte-identical cross-implementation agreement have a clean
path: produce canonical CBOR in Python, hand it to Rust via
`-in`.

## Evidence

- The AUD-08 witness value (`5.960464477539063e-08`) now hashes
  identically on both sides via the CBOR-input path. Verified by
  manual probe.
- `tests/test_cbor_boundaries.HalfPrecisionAllPatternsDiagnostic`
  previously skipped with a P1-acknowledging reason; now un-skipped
  and passing — all 63488 finite f16 patterns agree.
- Python suite: 166 passing, **0 skipped** (was 1 skipped).
- Rust suite: 28 tests passing (was 14). New:
  - 14 in `cbor_decoder::tests` covering the decoder end-to-end.

## What I did not test

- Huge CBOR inputs that exercise the 64 MiB payload bound on the
  Rust side. The Python decoder has a matching bound but I didn't
  write a paired regression for the Rust side at the limit.
- Bignum paths. Canonical Codifide modules don't use them today; a
  future user who puts an `i128` in a `Lit.value` would hit the
  tag-2/3 path, which the Rust decoder rejects cleanly (typed
  error), but I did not probe the exact error surface.
- Performance. The new decoder is a direct port, not optimized. A
  large module through the CBOR-in path may be slower than the
  JSON path for reasons that don't matter until we benchmark.

## Next

This closes the one remaining known P1. The logical next item is a
Sable re-audit of the new surfaces from today's pass — cost-based
dispatch and store GC — neither of which has been adversarially
probed.
