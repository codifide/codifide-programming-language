"""Canonical CBOR decoder.

This decoder accepts the subset of CBOR that our canonical encoder produces
and rejects everything else. It does not try to be a general-purpose CBOR
library — indefinite-length strings, tagged values other than bignums,
simple values other than true/false/null, and any input that is not in
canonical form (non-shortest heads, unsorted map keys, non-shortest floats)
all raise ``ValueError``.

The symmetric test — encode, decode, re-encode, compare bytes — is what
the conformance test uses to prove the encoder produces the form the
decoder insists on.
"""
from __future__ import annotations

import math
import struct
from typing import Any, Tuple


# Maximum bytes the decoder will honor for a single length-prefixed
# payload (byte string, text string, or any single allocation it would
# perform). 64 MiB matches the Rust CLI's input cap and is generously
# larger than any legitimate Codifide module. Without this bound, an
# adversarial payload honestly claiming a 1 GiB length and delivering
# 1 GiB of content would be accepted — Sable's CBOR audit called this
# out as a hardening gap. A principled production value would come
# from observed P99 module sizes; 64 MiB is a conservative guess for v0.
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024


def decode_canonical_cbor(data: bytes, *, max_payload: int = MAX_PAYLOAD_BYTES) -> Any:
    """Decode ``data`` as canonical CBOR. Rejects non-canonical input.

    ``max_payload`` bounds the largest individual length prefix the
    decoder will honor. Use a smaller value for untrusted input; use a
    larger value only when you control the producer. A payload that
    claims a length greater than the bound is rejected with a
    ``ValueError`` — the decoder never allocates arbitrarily-large
    buffers at adversary direction.
    """
    value, consumed = _decode(data, 0, max_payload)
    if consumed != len(data):
        raise ValueError(
            f"trailing bytes after CBOR value: consumed {consumed} of {len(data)}"
        )
    return value


def _decode(data: bytes, i: int, max_payload: int) -> Tuple[Any, int]:
    if i >= len(data):
        raise ValueError("unexpected end of CBOR input")
    head = data[i]
    major = head >> 5
    additional = head & 0x1F

    if major == 0:
        # Unsigned integer.
        n, i = _read_argument(data, i, additional)
        return n, i
    if major == 1:
        # Negative integer: value is -1 - n.
        n, i = _read_argument(data, i, additional)
        return -1 - n, i
    if major == 2:
        # Byte string.
        n, i = _read_argument(data, i, additional)
        if n > max_payload:
            raise ValueError(
                f"byte string claims {n} bytes, exceeds max_payload {max_payload}"
            )
        if i + n > len(data):
            raise ValueError("byte string runs past end of input")
        body = data[i : i + n]
        return body, i + n
    if major == 3:
        # Text string (UTF-8).
        n, i = _read_argument(data, i, additional)
        if n > max_payload:
            raise ValueError(
                f"text string claims {n} bytes, exceeds max_payload {max_payload}"
            )
        if i + n > len(data):
            raise ValueError("text string runs past end of input")
        body = data[i : i + n]
        try:
            return body.decode("utf-8"), i + n
        except UnicodeDecodeError as exc:
            raise ValueError(f"invalid UTF-8 in text string: {exc}") from exc
    if major == 4:
        # Array.
        n, i = _read_argument(data, i, additional)
        # An array claiming N items with one byte per item consumes at
        # least N bytes of remaining input. Treat the claim as bounded
        # by the remaining-input length so we don't pre-allocate a list
        # for an impossible count.
        if n > len(data) - i:
            raise ValueError(
                f"array claims {n} items but only {len(data) - i} bytes remain"
            )
        items = []
        for _ in range(n):
            item, i = _decode(data, i, max_payload)
            items.append(item)
        return items, i
    if major == 5:
        # Map.
        n, i = _read_argument(data, i, additional)
        # A map with N pairs needs at least 2N bytes.
        if n * 2 > len(data) - i:
            raise ValueError(
                f"map claims {n} pairs but only {len(data) - i} bytes remain"
            )
        out: dict = {}
        last_key_bytes: bytes | None = None
        for _ in range(n):
            key_start = i
            key, i = _decode(data, i, max_payload)
            key_end = i
            value, i = _decode(data, i, max_payload)
            # Enforce canonical key ordering: each key's encoded bytes
            # must be strictly greater than the previous key's. We
            # compare the raw slice rather than re-encoding to keep the
            # decoder fast and to catch encoder non-determinism at the
            # exact byte boundary.
            key_bytes = data[key_start:key_end]
            if last_key_bytes is not None and not (key_bytes > last_key_bytes):
                raise ValueError(
                    "map keys not in canonical order"
                )
            last_key_bytes = key_bytes
            if key in out:
                raise ValueError("duplicate map key in canonical CBOR")
            out[key] = value
        return out, i
    if major == 6:
        # Tagged. Only bignums (tags 2, 3) are allowed in our canonical form.
        tag, i = _read_argument(data, i, additional)
        inner, i = _decode(data, i, max_payload)
        if tag == 2 or tag == 3:
            if not isinstance(inner, (bytes, bytearray)):
                raise ValueError("bignum body must be byte string")
            body = bytes(inner)
            # RFC 8949 §3.4.3: bignum body MUST NOT have a leading zero
            # byte. A zero bignum would itself violate canonicity
            # (0 fits in a single byte head), so any zero-length or
            # leading-zero body is non-canonical.
            if len(body) == 0 or body[0] == 0:
                raise ValueError("non-canonical bignum encoding")
            n = int.from_bytes(body, "big")
            # Bignum must be outside the uint64 range or it would have
            # been encoded as a plain head.
            if n < 0x10000000000000000:
                raise ValueError(
                    "bignum used for value that fits in plain head"
                )
            return (n if tag == 2 else -1 - n), i
        raise ValueError(f"unsupported CBOR tag in canonical form: {tag}")
    if major == 7:
        # Simple values and floats.
        if additional == 20:
            return False, i + 1
        if additional == 21:
            return True, i + 1
        if additional == 22:
            return None, i + 1
        if additional == 25:
            # Half-precision float.
            if i + 3 > len(data):
                raise ValueError("truncated half float")
            f = struct.unpack(">e", data[i + 1 : i + 3])[0]
            if math.isnan(f) or math.isinf(f):
                raise ValueError("NaN/infinity not allowed in canonical CBOR")
            return f, i + 3
        if additional == 26:
            if i + 5 > len(data):
                raise ValueError("truncated single float")
            f = struct.unpack(">f", data[i + 1 : i + 5])[0]
            if math.isnan(f) or math.isinf(f):
                raise ValueError("NaN/infinity not allowed in canonical CBOR")
            return f, i + 5
        if additional == 27:
            if i + 9 > len(data):
                raise ValueError("truncated double float")
            f = struct.unpack(">d", data[i + 1 : i + 9])[0]
            if math.isnan(f) or math.isinf(f):
                raise ValueError("NaN/infinity not allowed in canonical CBOR")
            return f, i + 9
        raise ValueError(
            f"unsupported major-7 additional in canonical CBOR: {additional}"
        )
    raise ValueError(f"unreachable major type: {major}")


def _read_argument(data: bytes, i: int, additional: int) -> Tuple[int, int]:
    """Read a head's argument, enforcing shortest-form encoding.

    The canonical form requires the argument to use the smallest
    encoding that fits. A 1-byte value encoded as a 4-byte argument is
    non-canonical and rejected.
    """
    if additional < 24:
        return additional, i + 1
    if additional == 24:
        if i + 2 > len(data):
            raise ValueError("truncated 1-byte argument")
        n = data[i + 1]
        if n < 24:
            raise ValueError("non-canonical: 1-byte argument used for small value")
        return n, i + 2
    if additional == 25:
        if i + 3 > len(data):
            raise ValueError("truncated 2-byte argument")
        n = int.from_bytes(data[i + 1 : i + 3], "big")
        if n < 0x100:
            raise ValueError("non-canonical: 2-byte argument used for small value")
        return n, i + 3
    if additional == 26:
        if i + 5 > len(data):
            raise ValueError("truncated 4-byte argument")
        n = int.from_bytes(data[i + 1 : i + 5], "big")
        if n < 0x10000:
            raise ValueError("non-canonical: 4-byte argument used for small value")
        return n, i + 5
    if additional == 27:
        if i + 9 > len(data):
            raise ValueError("truncated 8-byte argument")
        n = int.from_bytes(data[i + 1 : i + 9], "big")
        if n < 0x100000000:
            raise ValueError("non-canonical: 8-byte argument used for small value")
        return n, i + 9
    raise ValueError(f"indefinite-length or reserved form not allowed: {additional}")
