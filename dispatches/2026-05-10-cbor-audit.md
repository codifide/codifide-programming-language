# Noema — audit note, CBOR and its neighborhood

*By Sable. 10 May 2026.*

Scope: the canonical CBOR encoder/decoder shipped today (Python in
`noema/projection/cbor.py` and `cbor_decoder.py`, Rust in
`crates/noema-canonical/src/cbor.rs`), the store's dual-identity
model for JSON and CBOR wire forms, and the filesystem surface
around the store. Methodology: six probe batteries, ~80 adversarial
inputs total.

I did not fuzz-test the Rust CBOR code with cargo-fuzz or equivalent.
That remains the biggest coverage gap after this audit. I also did
not probe the model-inference primitives, which are stubs in v0 and
will deserve their own audit when they become real.

## Findings

### P1-5 — Store write follows symlinks, leaking bytes outside the store

**What.** If an attacker can plant a symlink at `<store>/sha256/<XX>/`
pointing at a directory they control, the store's atomic-write path
follows that symlink and writes legitimate object bytes into the
attacker's directory instead of into the store. The store's own
invariants (hash-verified reads, idempotent writes, integrity on
retrieval) all hold within the store — but the store's bytes escape
into territory the store does not own, and nothing in the public API
signals that this happened.

**Probe that caught it.** Create temp directory. Inside: an `evil/`
directory and a `store/` directory. Inside `store/sha256/`, create a
symlink `ab → evil`. Compute a legitimate identity for some bytes.
Call `store._write_atomic(identity, data)`. Observation: the bytes
land in `evil/` with a `.json` extension. No error, no warning.

```
SYMLINK WRITE ESCAPES: 1 files leaked into victim dir:
/tmp/.../evil/f61f5b681ce9e65fb3ec87452a47128eea760ccc5a801c4303371d77a4382a.json
```

**Why it matters.** On a multi-user system, the store root is often
a user-writable path (`~/.noema/store`). An attacker who already has
write access there — or who can race a TOCTOU between the store's
`mkdir` and its write — can redirect any subsequent `put` into an
arbitrary directory. The store stops being a store and becomes a
write primitive the attacker aims. This is worse on shared
infrastructure where the store is reached through a mount point the
attacker partially controls.

**Severity: P1.** Not a silent soundness hole — the hash-verified
read path still catches tampering, and an attacker who controls a
victim's write target already has plenty of other primitives. But
writes that escape the store root violate the user's mental model of
what `noema store put` does, and on a shared filesystem this is how
CVEs get written.

**Fix.** Two defenses stacked:

1. Call `path.resolve(strict=False)` on the computed object path and
   refuse to write if the resolved path is not under `self.root`. This
   catches the symlink case above.
2. Set `O_NOFOLLOW` on the open call used by `tempfile.mkstemp`, or
   equivalently `lstat` the parent directory and refuse if it is a
   symlink.

The cheap version (1) catches the attack we found and is sufficient
unless a committed attacker races us during the resolve.

**Where it lives.** `noema/store/symbol_store.py::SymbolStore._write_atomic`.

### P1-6 — `store.get()` leaks `UnicodeDecodeError` on malformed bytes

**What.** `SymbolStore.get()` auto-detects wire form by looking at the
first byte of the stored payload: payloads starting with `{` (0x7B)
route to `json.loads`, everything else to the canonical CBOR decoder.
When bytes stored in a `.cbor` file happen to start with `0x7B` (which
is legal at the byte level in certain pathological CBOR encodings),
`get()` dispatches to `json.loads`, which tries to decode the bytes
as UTF-32-LE before finding them malformed, and raises a bare
`UnicodeDecodeError`. That error escapes the `StoreError` discipline.

**Probe.** Plant bytes starting with `0x7B` in a `.cbor` file whose
identity is valid. Call `store.get(identity)`:

```
get_bytes (stored as .cbor): b'{\x00\x00\x00\x00\x00\x00\x00\x04abcd'
get() correctly refuses: UnicodeDecodeError: 'utf-32-le' codec can't
decode bytes in position 8-11: code point not in range(0x110000)
```

`UnicodeDecodeError` is not a subclass of `StoreError` or `NoemaError`.
A host embedding Noema cannot catch this with the typed-error discipline.

**Why it matters.** Lower severity than P1-5 because it requires an
attacker who already planted content-hash-valid but CBOR-invalid bytes
under a `.cbor` suffix — an adversarial-publisher scenario rather than
a passive one. But the error-type discipline is what every other
caught finding relied on; a hole in it weakens the contract uniformly.

**Severity: P1.**

**Fix.** Route by file suffix, not by first byte. The store already
knows which suffix it wrote (`_path_for(identity, ".json")` vs
`.cbor`); `get()` should check suffix first and only fall back to
byte-sniffing if the suffix is ambiguous. Alternatively: wrap any
exception from either decoder path in a `StoreError` subclass so the
typed-error contract holds uniformly.

**Where it lives.** `noema/store/symbol_store.py::SymbolStore.get`.

### P1-7 — Rust CLI hangs forever on `/dev/zero`

**What.** `noema-canonical bytes-cbor /dev/zero` (or any subcommand)
hangs indefinitely. `std::fs::read_to_string` reads to EOF; `/dev/zero`
never EOFs. A hostile caller who can pass filenames into the Rust
binary can DoS the process.

**Probe.** `subprocess.run([RUST, "bytes-cbor", "/dev/zero"], timeout=2)`
raises `TimeoutExpired`.

**Why it matters.** The Rust CLI is the conformance tool the Python
test suite shells out to. A CI pipeline that runs conformance tests on
user-supplied files (hypothetical but realistic for a future hosted
service) could be wedged by a single crafted input. More generally, a
CLI that hangs forever is a broken CLI.

**Severity: P1.** Denial of service, no privilege escalation, no data
corruption.

**Fix.** Read with a size cap — 64 MiB is reasonable for a canonical
module; anything larger is either a bug or an attack. Use
`std::io::Read::take(cap).read_to_end(&mut buf)`. Past the cap,
surface a clean error and exit non-zero.

**Where it lives.**
`crates/noema-canonical/src/bin/noema_canonical.rs::load_and_emit`.

## Not-findings (explicitly cleared)

### Decoder robustness (P1)

Twenty adversarial CBOR inputs — truncations at every head size,
reserved additional values, unknown simple values, unknown tags,
bignum edge cases (body fits in u64, empty body, leading-zero body),
duplicate map keys, invalid UTF-8 in text strings, and a byte string
with a declared 2^60-byte length — all rejected with a typed
`ValueError` from `decode_canonical_cbor`. The canonical decoder's
strictness is doing its job.

### Python self-consistency (P2)

Twenty-nine pathological values including f64 subnormals, f64 max,
signed zero at every precision, 2^53 and adjacent integers, u64
boundary, negative-bignum boundary, Unicode combining characters,
astral-plane emoji, maps with identical prefixes, string length
boundaries at 24/255/256, and a 100-deep nested array all encode and
re-encode to byte-identical output.

### Python-Rust module-level agreement (P3)

Twenty-one pathological literal values embedded in full canonical
module envelopes produced byte-identical CBOR from Python and from
the Rust binary. Zero disagreements. Numeric edges, signed zero,
astral emoji, combining characters, string length boundaries — all
agree.

### Store identity forgery (P4)

- Writing bytes to the store under an identity those bytes do not
  hash to raises `IntegrityError`. Confirmed.
- Malformed identities (path traversal attempts, absolute paths,
  embedded NUL or newline) are rejected by the store's identity
  validator before the filesystem is touched. Confirmed.
- JSON and CBOR content identities for the same abstract symbol
  differ by construction. Confirmed; would require a SHA-256 preimage
  to violate, which is not on the table.

### Rust CLI on adversarial JSON (P6.1)

The Rust crate's JSON consumer (via `serde_json`) handled every
adversarial JSON input cleanly: empty, truncated, deeply-nested
(rejected at `serde_json`'s own recursion limit), large strings,
wrong schema version, missing required fields. All rejected with
informative messages and non-zero exit codes. Bignum literals
(2^100 inside a lit node) serialize correctly to CBOR with a tag-2
bignum.

## What I did not test

- **`cargo-fuzz` against the Rust CBOR encoder/decoder.** The biggest
  remaining coverage gap. Structured random inputs against
  `canonical_cbor` and the Rust-side JSON path might find a panic we
  haven't.
- **CLI argv handling.** I tested filenames but not exotic argv
  characters, very long arguments, or shell metacharacter injection.
  Low risk given the current CLI, but worth a pass.
- **Concurrent writer races on the new symlink fix.** Once P1-5 is
  patched, the patch itself needs concurrency testing.
- **Resource bounds on CBOR decoding.** The decoder will happily
  allocate memory for whatever length prefix the payload claims.
  P1/huge_length_claim rejects the claim when the buffer is smaller
  than the claimed length, but a payload that claims 1 GiB and
  delivers 1 GiB would be happily accepted. A max-allocation bound
  on the decoder would be prudent before exposing it to untrusted
  input.
- **Tag handling beyond bignums.** The decoder rejects unknown tags.
  I did not verify the encoder refuses to emit tags it should not.
  (In practice the encoder never emits tags other than 2/3 because
  we only call it with JSON-compatible values, but a future
  refactoring could change that.)

## Summary

Three P1 findings. None are P0 — the language's soundness properties
all still hold, content addressing is unbroken, and the cross-
implementation byte agreement is real. But all three findings are the
kind that turn into CVEs on a shared system or a hosted service:

- P1-5 (symlink escape on write) is the most important. Fix before any
  release that ships the store as a service component.
- P1-6 (UnicodeDecodeError leak) is a small crack in the typed-error
  contract the rest of the language relies on.
- P1-7 (CLI hang on `/dev/zero`) is a one-line fix that should not
  wait.

The uncomfortable observation holds, louder than last time: every new
capability increases the attack surface, and filesystem-adjacent
capabilities grow the surface fastest. The store has been added to,
extended, and re-extended across this session. The next audit should
treat the store as the primary subject rather than a neighborhood of
whatever just shipped.
