"""CBOR-backed symbol store.

The store accepts either JSON or CBOR wire form, producing distinct
identities for each (content addressing is a property of bytes, and the
wire forms differ). These tests pin down three things:

1. ``put_cbor`` writes bytes whose hash matches the returned identity,
   and a subsequent ``get_bytes`` returns identical bytes.
2. JSON and CBOR identities for the same Module differ.
3. Tampering with a CBOR object on disk surfaces as ``IntegrityError``
   on the next read, not a silent load.
"""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from noema import parse
from noema.store import (
    IntegrityError,
    SymbolStore,
    symbol_cbor_bytes,
    symbol_hash,
    symbol_hash_cbor,
)


_SRC = """
def hello
  intent "greet"
  sig    (name: String) -> String
  effects {}
  cand
    "Hello, " ++ name
"""


class CborStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = SymbolStore(self._tmp.name)
        self.defn = parse(_SRC).symbols[0]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_put_cbor_then_get_bytes_round_trips(self) -> None:
        identity = self.store.put_cbor("hello", self.defn)
        data = self.store.get_bytes(identity)
        self.assertEqual(data, symbol_cbor_bytes("hello", self.defn))
        # Sanity: the data is actually CBOR, not JSON.
        self.assertNotEqual(data[:1], b"{")

    def test_json_and_cbor_produce_different_identities(self) -> None:
        # Content addressing is a property of bytes; different bytes →
        # different identities even for the same abstract Module. This
        # is the correct behavior — collapsing them would make the
        # ``hash → bytes`` mapping non-injective.
        json_id = self.store.put("hello", self.defn)
        cbor_id = self.store.put_cbor("hello", self.defn)
        self.assertNotEqual(json_id, cbor_id)
        # And both are fetchable.
        self.assertTrue(self.store.has(json_id))
        self.assertTrue(self.store.has(cbor_id))

    def test_symbol_hash_and_store_agree_on_cbor_identity(self) -> None:
        # The free function and the store method must produce the same
        # identity for the same inputs; if they drifted, hashing a
        # symbol before putting it would not match what the store
        # later reports.
        h_direct = symbol_hash_cbor("hello", self.defn)
        h_store = self.store.put_cbor("hello", self.defn)
        self.assertEqual(h_direct, h_store)

    def test_symbol_hash_and_cbor_variant_differ(self) -> None:
        # Same sanity check for the pair of free functions.
        self.assertNotEqual(
            symbol_hash("hello", self.defn),
            symbol_hash_cbor("hello", self.defn),
        )

    def test_tampered_cbor_bytes_raise_integrity_error(self) -> None:
        identity = self.store.put_cbor("hello", self.defn)
        digest = identity.removeprefix("sha256:")
        # The CBOR file lives alongside the would-be JSON file with a
        # .cbor suffix.
        path = Path(self._tmp.name) / "sha256" / digest[:2] / f"{digest[2:]}.cbor"
        self.assertTrue(path.exists())
        path.write_bytes(path.read_bytes() + b"\x00")
        with self.assertRaises(IntegrityError):
            self.store.get_bytes(identity)

    def test_get_decodes_cbor_automatically(self) -> None:
        # ``get()`` returns the parsed canonical object regardless of
        # wire form. For a CBOR-stored symbol, the returned dict must
        # be shape-identical to what a JSON-stored counterpart would
        # produce.
        cbor_id = self.store.put_cbor("hello", self.defn)
        obj = self.store.get(cbor_id)
        self.assertEqual(obj["noema"], "0.1")
        self.assertIn("hello", obj["symbols"])

    def test_cbor_is_smaller_than_json_on_realistic_payload(self) -> None:
        # Not a correctness test per se, but the property is one of
        # CBOR's reasons for existing; if we ever regressed it (by
        # e.g. shipping strings as base64), the alert should fire.
        from noema.store import symbol_bytes
        json_bytes = symbol_bytes("hello", self.defn)
        cbor_bytes = symbol_cbor_bytes("hello", self.defn)
        self.assertLess(len(cbor_bytes), len(json_bytes))


if __name__ == "__main__":
    unittest.main()
