"""Content-addressed symbol store.

The store's job is to turn the spec's "content addressing" property into
something operational: agents can put a symbol and get back its identity,
then pull it back by identity and verify what they get is what was put.
These tests pin down the properties that make that useful — especially
idempotency and integrity checking, because without them "content
addressed" is a claim rather than a capability.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from noema import parse
from noema.store import (
    IntegrityError,
    NotFound,
    StoreError,
    SymbolStore,
    symbol_bytes,
    symbol_hash,
)


def _tiny_module():
    return parse(
        """
def greet
  intent "greet"
  sig    (name: String) -> String
  effects {}
  cand
    "hello, " ++ name
"""
    )


class SymbolHashingTests(unittest.TestCase):
    def test_same_module_same_hash(self) -> None:
        a = _tiny_module()
        b = _tiny_module()
        self.assertEqual(
            symbol_hash("greet", a.symbols[0]),
            symbol_hash("greet", b.symbols[0]),
        )

    def test_intent_change_changes_hash(self) -> None:
        # Spec says intent is part of identity — security audit P3-1.
        a = _tiny_module()
        b = parse(
            """
def greet
  intent "welcome"
  sig    (name: String) -> String
  effects {}
  cand
    "hello, " ++ name
"""
        )
        self.assertNotEqual(
            symbol_hash("greet", a.symbols[0]),
            symbol_hash("greet", b.symbols[0]),
        )

    def test_rename_changes_hash(self) -> None:
        # A renamed symbol is a different symbol by identity.
        a = _tiny_module()
        b = parse(
            """
def wave
  intent "greet"
  sig    (name: String) -> String
  effects {}
  cand
    "hello, " ++ name
"""
        )
        self.assertNotEqual(
            symbol_hash("greet", a.symbols[0]),
            symbol_hash("wave", b.symbols[0]),
        )


class SymbolStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = SymbolStore(self._tmp.name)
        self.module = _tiny_module()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- Core put/get ---------------------------------------------------

    def test_put_then_get_round_trips(self) -> None:
        identity = self.store.put("greet", self.module.symbols[0])
        data = self.store.get_bytes(identity)
        # The bytes we get back must be identical to what symbol_bytes
        # would compute fresh — the store does not reformat.
        self.assertEqual(data, symbol_bytes("greet", self.module.symbols[0]))

    def test_put_is_idempotent(self) -> None:
        a = self.store.put("greet", self.module.symbols[0])
        b = self.store.put("greet", self.module.symbols[0])
        self.assertEqual(a, b)
        # Only one object on disk.
        self.assertEqual(list(self.store.iter_identities()), [a])

    def test_get_missing_raises_notfound(self) -> None:
        bogus = "sha256:" + "0" * 64
        with self.assertRaises(NotFound):
            self.store.get_bytes(bogus)

    # -- Integrity ------------------------------------------------------

    def test_tampered_bytes_raise_integrity_error(self) -> None:
        identity = self.store.put("greet", self.module.symbols[0])
        # Find the file on disk and corrupt it.
        digest = identity.removeprefix("sha256:")
        path = Path(self._tmp.name) / "sha256" / digest[:2] / f"{digest[2:]}.json"
        original = path.read_bytes()
        path.write_bytes(original + b" /* tampered */")
        with self.assertRaises(IntegrityError) as cm:
            self.store.get_bytes(identity)
        self.assertEqual(cm.exception.expected, identity)

    def test_malformed_identity_is_rejected(self) -> None:
        with self.assertRaises(StoreError):
            self.store.get_bytes("sha256:not-a-hex-digest")
        with self.assertRaises(StoreError):
            self.store.get_bytes("md5:deadbeef")

    # -- Module-level --------------------------------------------------

    def test_put_module_stores_every_symbol(self) -> None:
        src = """
def a
  intent "first"
  sig () -> Int
  effects {}
  cand
    1

def b
  intent "second"
  sig () -> Int
  effects {}
  cand
    2
"""
        m = parse(src)
        pairs = self.store.put_module(m)
        self.assertEqual([p[0] for p in pairs], ["a", "b"])
        for name, identity in pairs:
            self.assertTrue(self.store.has(identity))

    def test_parsed_get_matches_symbol_bytes(self) -> None:
        # get() returns a dict; its canonical re-serialization must match
        # the bytes symbol_bytes would produce fresh.
        import json

        identity = self.store.put("greet", self.module.symbols[0])
        obj = self.store.get(identity)
        reserialized = json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        self.assertEqual(
            reserialized,
            symbol_bytes("greet", self.module.symbols[0]),
        )


class StoreVerifyTests(unittest.TestCase):
    """`noema store verify <hash>` closes Sable's P3-1 from the index audit.

    The capability: given a stored module (especially an index), walk
    its imports and report any pointees missing from the store. The
    subcommand is opt-in because requiring this at parse time is a DoS
    vector; requiring it at audit/publish time is cheap and correct.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = SymbolStore(self._tmp.name)
        m = _tiny_module()
        self.hello_id = self.store.put("greet", m.symbols[0])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        import sys
        return subprocess.run(
            [sys.executable, "-m", "noema", "store", "--store", self._tmp.name, *args],
            capture_output=True,
            text=True,
        )

    def test_verify_reports_ok_when_all_pointees_are_present(self) -> None:
        # Mint an index referencing the stored symbol. Its identity is
        # whatever the canonical bytes hash to; we compute that via the
        # public CLI so the test never couples to internal helpers.
        result = self._run_cli(
            "index", "--name", "good", f"greet={self.hello_id}"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        index_id = result.stdout.split("\t")[0]

        verify = self._run_cli("verify", index_id)
        self.assertEqual(verify.returncode, 0, verify.stderr)
        self.assertIn("OK", verify.stdout)
        self.assertIn("1 import", verify.stdout)

    def test_verify_reports_missing_pointees_and_exits_nonzero(self) -> None:
        # Build an index that points at a non-existent identity; `put`
        # the index directly so we can control exactly which pointees
        # are or are not present.
        from noema.core.types import Module
        from noema.projection.canonical import to_canonical

        ghost_id = "sha256:" + "0" * 64
        bad_index = Module(
            name="bad",
            symbols=(),
            imports=(("ghost", ghost_id),),
        )
        import hashlib
        import json as _json
        data = _json.dumps(
            to_canonical(bad_index),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        bad_index_id = f"sha256:{hashlib.sha256(data).hexdigest()}"
        self.store._write_atomic(bad_index_id, data)

        verify = self._run_cli("verify", bad_index_id)
        self.assertEqual(verify.returncode, 1)
        self.assertIn("problem", verify.stderr)
        self.assertIn(ghost_id, verify.stderr)


class StoreRustConformance(unittest.TestCase):
    """The Rust canonical CLI hashes the same envelope the store does.

    The store's envelope is a single-entry module; the Rust binary accepts
    arbitrary canonical JSON and returns a hash over its canonical bytes.
    Handing one the other's output must produce the same hash. If this
    test disagrees, content addressing has silently drifted and the whole
    premise of the store is compromised.
    """

    REPO_ROOT = Path(__file__).resolve().parent.parent
    RUST_BIN = REPO_ROOT / "target" / "release" / "noema-canonical"

    @classmethod
    def setUpClass(cls) -> None:
        if not cls.RUST_BIN.exists():
            raise unittest.SkipTest(
                "rust binary not built; skipping cross-impl hash conformance"
            )

    def test_rust_binary_agrees_with_python_store_hash(self) -> None:
        import json

        m = _tiny_module()
        defn = m.symbols[0]
        python_hash = symbol_hash("greet", defn)
        # Write the same envelope Python hashed, then hand it to Rust.
        envelope_json = symbol_bytes("greet", defn).decode("utf-8")
        envelope = json.loads(envelope_json)
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(envelope, tmp)
            tmp_path = Path(tmp.name)
        try:
            result = subprocess.run(
                [str(self.RUST_BIN), "hash", str(tmp_path)],
                capture_output=True,
                check=True,
                text=True,
            )
        finally:
            tmp_path.unlink(missing_ok=True)
        self.assertEqual(python_hash, result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
