"""Canonical CBOR (RFC 8949 §4.2) encoder and decoder.

Two layers of testing:

1. The encoder matches RFC 8949 Appendix A test vectors byte-for-byte.
   These are the authoritative correctness tests for any CBOR
   implementation that claims to be deterministic.
2. Encode/decode round-trip for every value we expect to appear in a
   canonical Codifide document (arrays, maps, strings, numbers, booleans,
   null, Unicode), with the decoder also rejecting non-canonical
   payloads (non-shortest heads, unsorted maps, indefinite-length
   strings). The decoder's strictness is what stops an adversary from
   slipping a same-semantics-different-bytes encoding past content
   addressing.
"""
from __future__ import annotations

import math
import struct
import unittest

from codifide.projection.cbor import canonical_cbor
from codifide.projection.cbor_decoder import decode_canonical_cbor


class RFC8949VectorsTests(unittest.TestCase):
    """Appendix A of RFC 8949 — the canon test vectors for CBOR."""

    def assertCbor(self, value, hex_expected):
        got = canonical_cbor(value).hex()
        self.assertEqual(
            got,
            hex_expected,
            f"canonical_cbor({value!r}) = {got} (expected {hex_expected})",
        )

    def test_integers(self):
        self.assertCbor(0, "00")
        self.assertCbor(1, "01")
        self.assertCbor(10, "0a")
        self.assertCbor(23, "17")
        self.assertCbor(24, "1818")
        self.assertCbor(25, "1819")
        self.assertCbor(100, "1864")
        self.assertCbor(1000, "1903e8")
        self.assertCbor(1_000_000, "1a000f4240")
        self.assertCbor(1_000_000_000_000, "1b000000e8d4a51000")
        self.assertCbor(-1, "20")
        self.assertCbor(-10, "29")
        self.assertCbor(-100, "3863")
        self.assertCbor(-1000, "3903e7")

    def test_floats(self):
        self.assertCbor(0.0, "f90000")
        # Half preserves signed zero.
        self.assertCbor(-0.0, "f98000")
        self.assertCbor(1.0, "f93c00")
        self.assertCbor(1.5, "f93e00")
        # 1.1 is not exactly representable in any binary float;
        # encoded as f64.
        self.assertCbor(1.1, "fb3ff199999999999a")
        self.assertCbor(65504.0, "f97bff")
        # Doesn't fit in f16, does fit in f32.
        self.assertCbor(100000.0, "fa47c35000")
        # Max finite f32.
        self.assertCbor(3.4028234663852886e38, "fa7f7fffff")
        # Smallest f16 subnormal.
        self.assertCbor(5.960464477539063e-8, "f90001")
        # Smallest positive f16 normal.
        self.assertCbor(6.103515625e-05, "f90400")

    def test_simple_values(self):
        self.assertCbor(False, "f4")
        self.assertCbor(True, "f5")
        self.assertCbor(None, "f6")

    def test_strings(self):
        self.assertCbor("", "60")
        self.assertCbor("a", "6161")
        self.assertCbor("IETF", "6449455446")
        self.assertCbor('"\\', "622 2 5c".replace(" ", ""))
        self.assertCbor("\u00fc", "62c3bc")
        self.assertCbor("\u6c34", "63e6b0b4")

    def test_arrays(self):
        self.assertCbor([], "80")
        self.assertCbor([1, 2, 3], "83010203")

    def test_maps(self):
        self.assertCbor({}, "a0")
        # Canonical order: keys "a" (0x6161) < "b" (0x6162) < "c" (0x6163).
        self.assertCbor({"a": 1, "b": [2, 3]}, "a26161016162820203")

    def test_nan_and_infinity_refused(self):
        with self.assertRaises(ValueError):
            canonical_cbor(float("nan"))
        with self.assertRaises(ValueError):
            canonical_cbor(float("inf"))
        with self.assertRaises(ValueError):
            canonical_cbor(float("-inf"))


class RoundTripTests(unittest.TestCase):
    """Encode then decode returns the original value."""

    def _round(self, v):
        return decode_canonical_cbor(canonical_cbor(v))

    def test_primitive_round_trips(self):
        for v in [None, True, False, 0, 1, -1, 2**63 - 1, "a", "", [], {}]:
            with self.subTest(v=v):
                self.assertEqual(self._round(v), v)

    def test_float_round_trips(self):
        for v in [0.0, 1.0, 1.5, 1.1, 65504.0, 100000.0, 3.14]:
            with self.subTest(v=v):
                self.assertEqual(self._round(v), v)

    def test_negative_zero_preserved(self):
        got = self._round(-0.0)
        self.assertEqual(math.copysign(1.0, got), -1.0)

    def test_deeply_nested_structure_round_trips(self):
        # Simulates a canonical Codifide module's shape: nested arrays and
        # maps, string keys, numeric and string values. Tests the
        # encoder and decoder together on something closer to the real
        # payload than the RFC vectors.
        v = {
            "codifide": "0.1",
            "module": "example",
            "symbols": {
                "f": {
                    "kind": "definition",
                    "intent": "do a thing",
                    "signature": {
                        "params": [],
                        "returns": "Int",
                        "effects": [],
                    },
                    "pre": [],
                    "post": [],
                    "candidates": [
                        {
                            "kind": "candidate",
                            "intent": "default",
                            "guard": None,
                            "body": {
                                "kind": "lit",
                                "value": 42,
                                "type": "Int",
                                "conf": 1.0,
                                "provenance": "literal",
                            },
                        }
                    ],
                }
            },
        }
        self.assertEqual(self._round(v), v)


class DecoderRejectsNonCanonicalTests(unittest.TestCase):
    """The decoder's strictness is part of the content-addressing contract.

    If an adversary can encode the same abstract value in two different
    byte forms, and both decode cleanly, the ``hash → bytes`` mapping is
    not one-to-one and content addressing is compromised. These tests
    confirm the decoder refuses non-canonical payloads that a
    permissive CBOR library would accept.
    """

    def test_rejects_non_shortest_integer_head(self):
        # 24 is the smallest value requiring a 1-byte argument; encoding
        # it with a 2-byte argument is legal CBOR but not canonical.
        non_canonical = bytes([0x19, 0x00, 0x18])  # 2-byte head for 24
        with self.assertRaises(ValueError):
            decode_canonical_cbor(non_canonical)

    def test_rejects_unsorted_map_keys(self):
        # Map with keys "b", "a" in that order — legal CBOR, not canonical.
        non_canonical = bytes.fromhex("a2616201616101")  # {"b": 1, "a": 1}
        with self.assertRaises(ValueError):
            decode_canonical_cbor(non_canonical)

    def test_rejects_indefinite_length(self):
        # Major type 2 with additional 31 (0x5F) starts an indefinite-
        # length byte string; canonical CBOR forbids it.
        non_canonical = bytes([0x5F, 0xFF])
        with self.assertRaises(ValueError):
            decode_canonical_cbor(non_canonical)

    def test_rejects_trailing_bytes(self):
        # Valid integer 1 followed by a stray byte.
        with self.assertRaises(ValueError):
            decode_canonical_cbor(b"\x01\x00")

    def test_rejects_nan_and_infinity(self):
        # f64 encodings of NaN and +inf. Canonical CBOR forbids them
        # even though CBOR itself allows them.
        nan_f64 = b"\xfb" + struct.pack(">d", float("nan"))
        with self.assertRaises(ValueError):
            decode_canonical_cbor(nan_f64)
        inf_f64 = b"\xfb" + struct.pack(">d", float("inf"))
        with self.assertRaises(ValueError):
            decode_canonical_cbor(inf_f64)


class DecoderAllocationBoundTests(unittest.TestCase):
    """The decoder refuses to honor adversarial length prefixes.

    Sable's CBOR audit named this as a hardening gap: a payload that
    claims a 1 GiB byte string and honestly delivers 1 GiB of content
    would be accepted, happily allocating a 1 GiB buffer at attacker
    direction. The decoder now caps single-payload lengths at
    MAX_PAYLOAD_BYTES by default, and refuses claims above the cap
    without touching the buffer.
    """

    def test_huge_byte_string_claim_is_rejected_without_allocation(self) -> None:
        # Head: major 2 (byte string), additional 27 (8-byte length
        # follows), then claim a value that genuinely requires the
        # 8-byte encoding (above 2^32). The payload itself is only the
        # 9-byte head — we never reach the "byte string runs past end
        # of input" branch because the length claim exceeds the cap.
        # Using 5 GiB: above 2^32 so the 8-byte head is canonical,
        # well above our 64 MiB default cap so the bound triggers.
        huge_claim = bytes([0x5b]) + (5 * 1024 * 1024 * 1024).to_bytes(8, "big")
        with self.assertRaises(ValueError) as cm:
            decode_canonical_cbor(huge_claim)
        self.assertIn("exceeds max_payload", str(cm.exception))

    def test_huge_text_string_claim_is_rejected(self) -> None:
        # Same pattern for text strings (major 3). Use 5 GiB so the
        # 8-byte head is canonical.
        huge_claim = bytes([0x7b]) + (5 * 1024 * 1024 * 1024).to_bytes(8, "big")
        with self.assertRaises(ValueError) as cm:
            decode_canonical_cbor(huge_claim)
        self.assertIn("exceeds max_payload", str(cm.exception))

    def test_huge_array_claim_refused_against_remaining_bytes(self) -> None:
        # An array claiming 2^32 items with no body cannot possibly be
        # valid — an N-item array takes at least N bytes. The decoder
        # rejects the claim against available bytes rather than trying
        # to pre-allocate a 4-billion-item list.
        huge_array = bytes([0x9a]) + (0xFFFF_FFFF).to_bytes(4, "big")
        with self.assertRaises(ValueError) as cm:
            decode_canonical_cbor(huge_array)
        msg = str(cm.exception).lower()
        # Either the bounds check on items-vs-remaining-bytes, or the
        # "unexpected end of CBOR input" path; both are fine.
        self.assertTrue(
            "claims" in msg or "unexpected end" in msg,
            f"expected typed rejection, got: {cm.exception!r}",
        )

    def test_caller_can_raise_the_cap(self) -> None:
        # Encoder produces a 100-byte string; decoder with a 50-byte
        # cap refuses it, with a 200-byte cap accepts it. The cap is a
        # policy knob, not a hardcoded constant.
        encoded = canonical_cbor("a" * 100)
        with self.assertRaises(ValueError):
            decode_canonical_cbor(encoded, max_payload=50)
        self.assertEqual(decode_canonical_cbor(encoded, max_payload=200), "a" * 100)


if __name__ == "__main__":
    unittest.main()
