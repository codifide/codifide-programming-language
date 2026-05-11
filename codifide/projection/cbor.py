"""Canonical CBOR projection.

RFC 8949 (CBOR) §4.2 deterministically-encoded subset. Two implementations
of this subset — Python here, Rust in ``crates/codifide-canonical/src/cbor.rs``
— MUST produce byte-identical output for every input; the conformance test
enforces that.

Rules we implement (RFC 8949 §4.2):

- Integers use the shortest major-type-0/1 head. Integers outside
  ``[-2^64, 2^64)`` use tagged bignum (tag 2 for positive, tag 3 for
  negative) with a shortest-byte-string body.
- Floats use the shortest IEEE-754 binary representation that preserves
  their value: half precision if exact, else single, else double. NaN and
  infinity MUST NOT appear in a canonical document and raise ``ValueError``.
- Byte and text strings use the shortest length prefix.
- Arrays use definite-length encoding.
- Maps use definite-length encoding; keys are sorted by their encoded
  bytes in bytewise lexicographic order (RFC 8949 §4.2.1).
- ``None`` encodes as null (major type 7, additional 22).
- ``True`` / ``False`` encode as major type 7, additional 21 / 20.

Nothing else encodes. Unknown Python types raise ``TypeError``. The
canonical form is the contract; ambiguity is a bug.
"""
from __future__ import annotations

import hashlib
import math
import struct
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def canonical_cbor(value: Any) -> bytes:
    """Encode a JSON-compatible value as deterministic CBOR.

    Accepts ``None``, ``bool``, ``int``, ``float``, ``str``, ``bytes``,
    ``list``, and ``dict`` (with string keys, matching what the canonical
    JSON projection produces). Anything else raises ``TypeError``.
    """
    # ``bool`` is a subclass of ``int`` in Python, so it comes first.
    if value is None:
        return _FIXED_NULL
    if value is True:
        return _FIXED_TRUE
    if value is False:
        return _FIXED_FALSE
    if isinstance(value, bool):
        # Defensive: caught above, but keep the branch explicit.
        return _FIXED_TRUE if value else _FIXED_FALSE
    if isinstance(value, int):
        return _encode_int(value)
    if isinstance(value, float):
        return _encode_float(value)
    if isinstance(value, str):
        return _encode_text(value)
    if isinstance(value, (bytes, bytearray)):
        return _encode_bytes(bytes(value))
    if isinstance(value, list):
        return _encode_array(value)
    if isinstance(value, tuple):
        # Tuples serialize as arrays; no separate CBOR type exists.
        return _encode_array(list(value))
    if isinstance(value, dict):
        return _encode_map(value)
    raise TypeError(f"cannot CBOR-encode {type(value).__name__}: {value!r}")


def content_hash_cbor_bytes(data: bytes) -> str:
    """SHA-256 over canonical CBOR bytes, formatted as ``sha256:<hex>``."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


_FIXED_FALSE = bytes([0xF4])
_FIXED_TRUE = bytes([0xF5])
_FIXED_NULL = bytes([0xF6])


# ---------------------------------------------------------------------------
# Head encoding
# ---------------------------------------------------------------------------


def _encode_head(major: int, n: int) -> bytes:
    """Encode an (major-type, argument) head using the shortest form.

    ``major`` is the 3-bit major type (0..7). ``n`` is the argument value
    (length for strings/arrays/maps, value for integers). We always emit
    the shortest encoding as RFC 8949 §4.2.1 requires.
    """
    assert 0 <= major <= 7
    prefix = major << 5
    if n < 0:
        raise ValueError(f"head argument must be non-negative, got {n}")
    if n < 24:
        return bytes([prefix | n])
    if n < 0x100:
        return bytes([prefix | 24, n])
    if n < 0x10000:
        return bytes([prefix | 25]) + n.to_bytes(2, "big")
    if n < 0x100000000:
        return bytes([prefix | 26]) + n.to_bytes(4, "big")
    if n < 0x10000000000000000:
        return bytes([prefix | 27]) + n.to_bytes(8, "big")
    raise OverflowError(f"CBOR head argument too large: {n}")


# ---------------------------------------------------------------------------
# Integers (including bignums)
# ---------------------------------------------------------------------------


def _encode_int(n: int) -> bytes:
    """Encode an integer, using bignum tags only when out of uint64 range.

    RFC 8949 §4.2.3: integers that fit in a major-type 0/1 head MUST use
    one rather than a bignum tag. We enforce that here.
    """
    if n >= 0:
        if n < 0x10000000000000000:
            return _encode_head(0, n)
        # Positive bignum, tag 2.
        body = _int_to_bytes(n)
        return bytes([0xC2]) + _encode_bytes(body)
    # n < 0: major type 1 encodes -1-n.
    m = -1 - n
    if m < 0x10000000000000000:
        return _encode_head(1, m)
    # Negative bignum, tag 3.
    body = _int_to_bytes(m)
    return bytes([0xC3]) + _encode_bytes(body)


def _int_to_bytes(n: int) -> bytes:
    """Big-endian, shortest unsigned byte representation.

    Zero encodes as a zero-length byte string, which matches what a
    shortest-form encoder would produce (no leading zero bytes). Callers
    of bignum encoding never pass zero — integers of zero fit in a
    single-byte head — but defining the function to handle it keeps the
    contract consistent.
    """
    if n == 0:
        return b""
    return n.to_bytes((n.bit_length() + 7) // 8, "big")


# ---------------------------------------------------------------------------
# Strings and byte strings
# ---------------------------------------------------------------------------


def _encode_text(s: str) -> bytes:
    data = s.encode("utf-8")
    return _encode_head(3, len(data)) + data


def _encode_bytes(b: bytes) -> bytes:
    return _encode_head(2, len(b)) + b


# ---------------------------------------------------------------------------
# Arrays and maps
# ---------------------------------------------------------------------------


def _encode_array(items: list) -> bytes:
    out = bytearray(_encode_head(4, len(items)))
    for item in items:
        out += canonical_cbor(item)
    return bytes(out)


def _encode_map(m: dict) -> bytes:
    """Definite-length map; keys sorted by their encoded bytes.

    RFC 8949 §4.2.1: "The keys in every map MUST be sorted in the
    bytewise lexicographic order of their deterministic encodings."
    Sorting by encoded key rather than by key value matters when keys
    are of mixed types (e.g. integer key 0 vs string key "0"). In the
    canonical Codifide form all keys are strings and the two orderings
    coincide for ASCII keys, but we sort by encoding anyway so the
    implementation is right in general.
    """
    pairs = []
    for k, v in m.items():
        encoded_key = canonical_cbor(k)
        encoded_value = canonical_cbor(v)
        pairs.append((encoded_key, encoded_value))
    pairs.sort(key=lambda p: p[0])
    out = bytearray(_encode_head(5, len(pairs)))
    for ek, ev in pairs:
        out += ek
        out += ev
    return bytes(out)


# ---------------------------------------------------------------------------
# Floats
# ---------------------------------------------------------------------------


def _encode_float(f: float) -> bytes:
    """Encode a float using the shortest IEEE-754 type that preserves it.

    RFC 8949 §4.2.2: "Floating-point values that can be represented as a
    half-precision float MUST be encoded as a half-precision float.
    Floating-point values that cannot be represented as a half-precision
    float but can be represented as a single-precision float MUST be
    encoded as a single-precision float. All other floating-point values
    MUST be encoded as a double-precision float."

    NaN and infinity are not legal in canonical CBOR and raise
    ``ValueError``.
    """
    if math.isnan(f):
        raise ValueError("canonical CBOR: NaN is not representable")
    if math.isinf(f):
        raise ValueError("canonical CBOR: infinity is not representable")

    f16 = _try_half(f)
    if f16 is not None:
        return bytes([0xF9]) + f16

    f32 = _try_single(f)
    if f32 is not None:
        return bytes([0xFA]) + f32

    return bytes([0xFB]) + struct.pack(">d", f)


def _try_half(f: float) -> Optional[bytes]:
    """Return 2-byte IEEE-754 binary16 if it round-trips exactly, else None.

    Python's ``struct`` format ``'e'`` is IEEE-754 binary16, which is
    what CBOR half precision requires. We verify round-trip equality
    because ``struct.pack('>e', ...)`` will silently round values that
    do not fit exactly, and we need exact preservation (or nothing).
    """
    try:
        packed = struct.pack(">e", f)
    except (OverflowError, struct.error):
        return None
    unpacked = struct.unpack(">e", packed)[0]
    # Catch signed zero separately — 0.0 == -0.0 in Python comparison but
    # the sign bit matters for canonical encoding.
    if f == 0.0 and math.copysign(1.0, f) != math.copysign(1.0, unpacked):
        return None
    if unpacked != f:
        return None
    return packed


def _try_single(f: float) -> Optional[bytes]:
    """Return 4-byte IEEE-754 binary32 if it round-trips exactly, else None."""
    try:
        packed = struct.pack(">f", f)
    except (OverflowError, struct.error):
        return None
    unpacked = struct.unpack(">f", packed)[0]
    if f == 0.0 and math.copysign(1.0, f) != math.copysign(1.0, unpacked):
        return None
    if unpacked != f:
        return None
    return packed
