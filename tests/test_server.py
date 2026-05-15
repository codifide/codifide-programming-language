"""RPC API server tests.

Covers the three endpoints specified in ``docs/RPC_API.md``:

    POST /symbols                    — publish a symbol, get its hash
    GET  /symbols/<identity>         — retrieve a symbol by hash
    GET  /symbols/<identity>/imports — resolve the import graph
    GET  /health                     — liveness check

Also covers:
    HEAD /symbols/<identity>         — existence check
    Error responses (400, 404, 413, 405)
    Concurrent POST safety
    CBOR and JSON wire formats
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from codifide import parse
from codifide.projection.canonical import from_canonical, to_canonical
from codifide.projection.cbor import canonical_cbor
from codifide.projection.cbor_decoder import decode_canonical_cbor
from codifide.server import make_server
from codifide.store import SymbolStore, symbol_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tiny_module(name: str = "greet", intent: str = "greet a user"):
    return parse(f"""
def {name}
  intent "{intent}"
  sig    (name: String) -> String
  effects {{}}
  cand
    "hello, " ++ name
""")


def _single_symbol_cbor(sym_name: str = "greet", intent: str = "greet a user") -> bytes:
    """Return canonical CBOR for a single-symbol module."""
    module = _tiny_module(sym_name, intent)
    return canonical_cbor(to_canonical(module))


def _single_symbol_json(sym_name: str = "greet", intent: str = "greet a user") -> bytes:
    """Return canonical JSON bytes for a single-symbol module."""
    module = _tiny_module(sym_name, intent)
    return json.dumps(to_canonical(module), separators=(",", ":"), sort_keys=True).encode()


class _ServerFixture(unittest.TestCase):
    """Base class that starts a server on a random port for each test."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SymbolStore(self._tmpdir.name)
        self.server = make_server(self.store, host="127.0.0.1", port=0)
        self.port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(timeout=2)
        self._tmpdir.cleanup()

    def _post(self, path: str, body: bytes, content_type: str = "application/cbor"):
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=body,
            method="POST",
            headers={"Content-Type": content_type},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def _get(self, path: str, accept: str = "application/cbor"):
        req = urllib.request.Request(
            f"{self.base}{path}",
            headers={"Accept": accept},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, resp.read(), resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers.get("Content-Type", "")

    def _get_json(self, path: str):
        status, body, ct = self._get(path, accept="application/json")
        return status, json.loads(body)

    def _head(self, path: str):
        req = urllib.request.Request(
            f"{self.base}{path}",
            method="HEAD",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class HealthTests(_ServerFixture):
    def test_health_returns_ok(self) -> None:
        status, body, _ = self._get("/health", accept="application/json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ok"})

    def test_health_no_store_access(self) -> None:
        # Health should return 200 even if the store is empty.
        status, body, _ = self._get("/health", accept="application/json")
        self.assertEqual(status, 200)


# ---------------------------------------------------------------------------
# POST /symbols
# ---------------------------------------------------------------------------

class PostSymbolTests(_ServerFixture):
    def test_post_cbor_returns_identity(self) -> None:
        body = _single_symbol_cbor()
        status, resp = self._post("/symbols", body, "application/cbor")
        self.assertEqual(status, 200)
        self.assertIn("identity", resp)
        self.assertTrue(resp["identity"].startswith("sha256:"))
        self.assertEqual(resp["name"], "greet")

    def test_post_json_returns_identity(self) -> None:
        body = _single_symbol_json()
        status, resp = self._post("/symbols", body, "application/json")
        self.assertEqual(status, 200)
        self.assertIn("identity", resp)
        self.assertTrue(resp["identity"].startswith("sha256:"))

    def test_post_stores_symbol(self) -> None:
        body = _single_symbol_cbor()
        status, resp = self._post("/symbols", body, "application/cbor")
        self.assertEqual(status, 200)
        identity = resp["identity"]
        self.assertTrue(self.store.has(identity))

    def test_post_identity_matches_store_hash(self) -> None:
        module = _tiny_module()
        defn = module.symbols[0]
        expected = symbol_hash(defn.name, defn)
        body = canonical_cbor(to_canonical(module))
        status, resp = self._post("/symbols", body, "application/cbor")
        self.assertEqual(status, 200)
        self.assertEqual(resp["identity"], expected)

    def test_post_idempotent(self) -> None:
        body = _single_symbol_cbor()
        status1, resp1 = self._post("/symbols", body, "application/cbor")
        status2, resp2 = self._post("/symbols", body, "application/cbor")
        self.assertEqual(status1, 200)
        self.assertEqual(status2, 200)
        self.assertEqual(resp1["identity"], resp2["identity"])

    def test_post_multi_symbol_rejected(self) -> None:
        module = parse("""
def foo
  intent "foo"
  sig    () -> String
  effects {}
  cand
    "foo"

def bar
  intent "bar"
  sig    () -> String
  effects {}
  cand
    "bar"
""")
        body = canonical_cbor(to_canonical(module))
        status, resp = self._post("/symbols", body, "application/cbor")
        self.assertEqual(status, 400)
        self.assertEqual(resp["error"], "multi_symbol")

    def test_post_empty_module_rejected(self) -> None:
        # A module with no symbols — construct manually.
        from codifide.core.types import Module
        empty = Module(name="empty", symbols=(), imports=())
        body = canonical_cbor(to_canonical(empty))
        status, resp = self._post("/symbols", body, "application/cbor")
        self.assertEqual(status, 400)
        self.assertEqual(resp["error"], "invalid_body")

    def test_post_invalid_body_rejected(self) -> None:
        status, resp = self._post("/symbols", b"not cbor at all", "application/cbor")
        self.assertEqual(status, 400)
        self.assertEqual(resp["error"], "invalid_body")

    def test_post_invalid_json_rejected(self) -> None:
        status, resp = self._post("/symbols", b"{bad json", "application/json")
        self.assertEqual(status, 400)
        self.assertEqual(resp["error"], "invalid_body")

    def test_post_body_too_large_rejected(self) -> None:
        # 17 MiB of zeros — over the 16 MiB limit.
        big = b"\x00" * (17 * 1024 * 1024)
        status, resp = self._post("/symbols", big, "application/cbor")
        self.assertEqual(status, 413)
        self.assertEqual(resp["error"], "body_too_large")

    def test_post_negative_content_length_rejected(self) -> None:
        # AUD-RPC-01: negative Content-Length must not cause unbounded read.
        # urllib refuses to send negative Content-Length, so we test via
        # the _read_body function directly.
        import io
        from codifide.server import _read_body

        class _FakeHandler:
            class headers:
                @staticmethod
                def get(key, default=""):
                    if key == "Content-Length":
                        return "-1"
                    return default
            rfile = io.BytesIO(b"some data")

        result = _read_body(_FakeHandler())
        self.assertIsNone(result, "negative Content-Length should return None")


# ---------------------------------------------------------------------------
# GET /symbols/<identity>
# ---------------------------------------------------------------------------

class GetSymbolTests(_ServerFixture):
    def setUp(self) -> None:
        super().setUp()
        # Pre-store a symbol.
        module = _tiny_module()
        self.defn = module.symbols[0]
        self.identity = self.store.put(self.defn.name, self.defn)

    def test_get_cbor_returns_bytes(self) -> None:
        status, body, ct = self._get(f"/symbols/{self.identity}", "application/cbor")
        self.assertEqual(status, 200)
        self.assertIn("cbor", ct)
        # Body should decode to a valid canonical object.
        obj = decode_canonical_cbor(body)
        self.assertIn("symbols", obj)

    def test_get_json_returns_object(self) -> None:
        status, resp = self._get_json(f"/symbols/{self.identity}")
        self.assertEqual(status, 200)
        self.assertIn("symbols", resp)

    def test_get_default_is_cbor(self) -> None:
        # No Accept header — should default to CBOR.
        req = urllib.request.Request(f"{self.base}/symbols/{self.identity}")
        with urllib.request.urlopen(req) as resp:
            ct = resp.headers.get("Content-Type", "")
            self.assertIn("cbor", ct)

    def test_get_not_found(self) -> None:
        fake = "sha256:" + "a" * 64
        status, resp = self._get_json(f"/symbols/{fake}")
        self.assertEqual(status, 404)
        self.assertEqual(resp["error"], "not_found")

    def test_get_malformed_identity(self) -> None:
        status, resp = self._get_json("/symbols/not-a-hash")
        self.assertEqual(status, 400)
        self.assertEqual(resp["error"], "invalid_identity")

    def test_get_roundtrip(self) -> None:
        # GET the stored symbol and verify it round-trips to the same module.
        status, resp = self._get_json(f"/symbols/{self.identity}")
        self.assertEqual(status, 200)
        recovered = from_canonical(resp)
        self.assertEqual(recovered.symbols[0].name, self.defn.name)
        self.assertEqual(recovered.symbols[0].intent, self.defn.intent)


# ---------------------------------------------------------------------------
# HEAD /symbols/<identity>
# ---------------------------------------------------------------------------

class HeadSymbolTests(_ServerFixture):
    def setUp(self) -> None:
        super().setUp()
        module = _tiny_module()
        self.defn = module.symbols[0]
        self.identity = self.store.put(self.defn.name, self.defn)

    def test_head_present(self) -> None:
        status = self._head(f"/symbols/{self.identity}")
        self.assertEqual(status, 200)

    def test_head_absent(self) -> None:
        fake = "sha256:" + "b" * 64
        status = self._head(f"/symbols/{fake}")
        self.assertEqual(status, 404)


# ---------------------------------------------------------------------------
# GET /symbols/<identity>/imports
# ---------------------------------------------------------------------------

class GetImportsTests(_ServerFixture):
    def test_imports_empty(self) -> None:
        # A symbol with no imports.
        module = _tiny_module()
        identity = self.store.put(module.symbols[0].name, module.symbols[0])
        status, resp = self._get_json(f"/symbols/{identity}/imports")
        self.assertEqual(status, 200)
        self.assertEqual(resp["identity"], identity)
        self.assertEqual(resp["imports"], [])
        self.assertEqual(resp["missing"], [])

    def test_imports_with_present_dependency(self) -> None:
        # Store a dependency, then store a module that imports it.
        dep_module = _tiny_module("dep", "a dependency")
        dep_identity = self.store.put(dep_module.symbols[0].name, dep_module.symbols[0])

        # Build a module with an imports table pointing at dep.
        from codifide.core.types import Module
        index_module = Module(
            name="consumer",
            symbols=(),
            imports=(("dep", dep_identity),),
        )
        index_cbor = canonical_cbor(to_canonical(index_module))
        import hashlib
        index_identity = f"sha256:{hashlib.sha256(index_cbor).hexdigest()}"
        self.store._write_atomic(index_identity, index_cbor, suffix=".cbor")

        status, resp = self._get_json(f"/symbols/{index_identity}/imports")
        self.assertEqual(status, 200)
        self.assertEqual(len(resp["imports"]), 1)
        self.assertEqual(resp["imports"][0]["name"], "dep")
        self.assertEqual(resp["imports"][0]["identity"], dep_identity)
        self.assertTrue(resp["imports"][0]["present"])
        self.assertEqual(resp["missing"], [])

    def test_imports_with_missing_dependency(self) -> None:
        missing_id = "sha256:" + "c" * 64
        from codifide.core.types import Module
        index_module = Module(
            name="consumer",
            symbols=(),
            imports=(("missing_dep", missing_id),),
        )
        index_cbor = canonical_cbor(to_canonical(index_module))
        import hashlib
        index_identity = f"sha256:{hashlib.sha256(index_cbor).hexdigest()}"
        self.store._write_atomic(index_identity, index_cbor, suffix=".cbor")

        status, resp = self._get_json(f"/symbols/{index_identity}/imports")
        self.assertEqual(status, 200)
        self.assertFalse(resp["imports"][0]["present"])
        self.assertIn(missing_id, resp["missing"])

    def test_imports_not_found(self) -> None:
        fake = "sha256:" + "d" * 64
        status, resp = self._get_json(f"/symbols/{fake}/imports")
        self.assertEqual(status, 404)
        self.assertEqual(resp["error"], "not_found")


# ---------------------------------------------------------------------------
# Concurrent POST safety
# ---------------------------------------------------------------------------

class ConcurrentPostTests(_ServerFixture):
    def test_concurrent_posts_same_symbol(self) -> None:
        """Concurrent POSTs of the same symbol must all return the same identity."""
        body = _single_symbol_cbor()
        results = []
        errors = []

        def post_once():
            try:
                status, resp = self._post("/symbols", body, "application/cbor")
                results.append((status, resp.get("identity")))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=post_once) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"errors during concurrent POST: {errors}")
        self.assertEqual(len(results), 10)
        statuses = {r[0] for r in results}
        identities = {r[1] for r in results}
        self.assertEqual(statuses, {200})
        self.assertEqual(len(identities), 1, "all concurrent POSTs must return the same identity")

    def test_concurrent_posts_different_symbols(self) -> None:
        """Concurrent POSTs of different symbols must all succeed."""
        bodies = [_single_symbol_cbor(f"sym{i}", f"intent {i}") for i in range(5)]
        results = []
        errors = []

        def post_one(b):
            try:
                status, resp = self._post("/symbols", b, "application/cbor")
                results.append((status, resp.get("identity")))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=post_one, args=(b,)) for b in bodies]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"errors during concurrent POST: {errors}")
        self.assertEqual(len(results), 5)
        statuses = {r[0] for r in results}
        self.assertEqual(statuses, {200})
        identities = {r[1] for r in results}
        self.assertEqual(len(identities), 5, "each symbol must get a distinct identity")


# ---------------------------------------------------------------------------
# Route coverage
# ---------------------------------------------------------------------------

class RoutingTests(_ServerFixture):
    def test_unknown_path_404(self) -> None:
        status, resp = self._get_json("/unknown/path")
        self.assertEqual(status, 404)

    def test_symbols_root_get_404(self) -> None:
        # GET /symbols (no identity) is not a valid route.
        status, resp = self._get_json("/symbols")
        self.assertEqual(status, 404)

    def test_post_unknown_path_404(self) -> None:
        # POST to an unknown path must return 404, not 500.
        status, resp = self._post("/unknown/path", b"{}", "application/json")
        self.assertEqual(status, 404)
        self.assertEqual(resp["error"], "not_found")

    def test_head_malformed_identity_404(self) -> None:
        # HEAD /symbols/not-a-hash — falls through to bare 404.
        # Regression: must not 500 or hang.
        status = self._head("/symbols/not-a-hash")
        self.assertEqual(status, 404)

    def test_head_valid_identity_absent_404(self) -> None:
        fake = "sha256:" + "e" * 64
        status = self._head(f"/symbols/{fake}")
        self.assertEqual(status, 404)


# ---------------------------------------------------------------------------
# Adversarial: corrupt store object in /imports endpoint
# ---------------------------------------------------------------------------

class CorruptStoreTests(_ServerFixture):
    def test_imports_corrupt_stored_object_returns_500(self) -> None:
        """GET /symbols/<id>/imports where the stored object is not a valid module."""
        import hashlib
        # Write raw bytes that are valid CBOR but not a valid canonical module.
        garbage = b"\xa1\x63foo\x63bar"  # {"foo": "bar"} — valid CBOR, invalid module
        identity = f"sha256:{hashlib.sha256(garbage).hexdigest()}"
        self.store._write_atomic(identity, garbage, suffix=".cbor")

        status, resp = self._get_json(f"/symbols/{identity}/imports")
        self.assertEqual(status, 500)
        self.assertEqual(resp["error"], "store_error")


if __name__ == "__main__":
    unittest.main()
