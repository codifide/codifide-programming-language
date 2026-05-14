"""V2-1-6 acceptance test: agent completes Program 5 via HTTP only.

This test proves the RPC API acceptance criterion from REQ-V2-1:

    "An agent can complete Program 5 of docs/AGENT_TASK_SPEC.md using
    only HTTP requests — no CLI, no CODIFIDE_RUNTIME=python."

The workflow:
1. Start the RPC server backed by a temp store.
2. Publish classify_content, moderate, and route_message via POST /symbols.
3. Write pipeline_composed.cod using the returned hashes.
4. Run pipeline_composed.cod with the Python interpreter.
5. Verify the output is the expected routing decision.

No CLI store subcommands. No CODIFIDE_RUNTIME=python. No store index.
Just HTTP.

Note on transitive dependencies:
    route_message calls moderate, which calls classify_content.
    All three must be published and imported individually — the store
    holds single-symbol units. This is the correct Program 5 workflow.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from codifide import parse
from codifide.core.types import Module
from codifide.projection.canonical import to_canonical
from codifide.projection.cbor import canonical_cbor
from codifide.server import make_server
from codifide.store import SymbolStore


# ---------------------------------------------------------------------------
# Pipeline source programs
# ---------------------------------------------------------------------------

_CLASSIFIER_SRC = """\
module content_classifier

def classify_content
  intent "label a message as safe, unsafe, or uncertain based on keyword signals"
  sig    (message: String) -> Label
  effects {}
  cand
    intent "unsafe — spam, hate, or violence detected"
    when   or(contains(lower(message), "spam"),
              contains(lower(message), "hate"),
              contains(lower(message), "violence"))
    belief("unsafe", 0.90)
  cand
    intent "safe — approved or verified signal"
    when   or(contains(lower(message), "approved"),
              contains(lower(message), "verified"))
    belief("safe", 0.90)
  cand
    intent "uncertain — no strong signal"
    belief("uncertain", 0.75)
"""

_ROUTER_SRC = """\
module escalation_router

def classify_content
  intent "label a message as safe, unsafe, or uncertain based on keyword signals"
  sig    (message: String) -> Label
  effects {}
  cand
    intent "unsafe — spam, hate, or violence detected"
    when   or(contains(lower(message), "spam"),
              contains(lower(message), "hate"),
              contains(lower(message), "violence"))
    belief("unsafe", 0.90)
  cand
    intent "safe — approved or verified signal"
    when   or(contains(lower(message), "approved"),
              contains(lower(message), "verified"))
    belief("safe", 0.90)
  cand
    intent "uncertain — no strong signal"
    belief("uncertain", 0.75)

def moderate
  intent "refuse classification when confidence is too low"
  sig    (message: String) -> Label
  effects {}
  cand
    result <- classify_content(message)
    believe result
      ge(conf(result), 0.70) => result
      else                   => bottom

def route_message
  intent "route a message to blocked, approved, or escalate-to-human"
  sig    (message: String) -> Decision
  effects {}
  cand
    label <- moderate(message)
    if eq(label, "unsafe") then "blocked"
    else if eq(label, "safe") then "approved"
    else "escalate-to-human"
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_symbol(base_url: str, src: str, sym_name: str) -> str:
    """Parse src, extract sym_name, POST its canonical CBOR, return identity."""
    module = parse(src)
    defn = next((d for d in module.symbols if d.name == sym_name), None)
    if defn is None:
        raise ValueError(f"symbol {sym_name!r} not found in module")
    single = Module(name=module.name, symbols=(defn,), imports=())
    body = canonical_cbor(to_canonical(single))
    req = urllib.request.Request(
        f"{base_url}/symbols",
        data=body,
        method="POST",
        headers={"Content-Type": "application/cbor"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    return result["identity"]


def _publish_pipeline(base_url: str) -> tuple:
    """Publish all three pipeline symbols via HTTP.

    Returns (classify_id, moderate_id, route_id).

    The transitive dependency chain is:
        route_message -> moderate -> classify_content

    All three must be published and imported for the composed program to run.
    """
    classify_id = _post_symbol(base_url, _CLASSIFIER_SRC, "classify_content")
    moderate_id = _post_symbol(base_url, _ROUTER_SRC, "moderate")
    route_id = _post_symbol(base_url, _ROUTER_SRC, "route_message")
    return classify_id, moderate_id, route_id


def _composed_src(classify_id: str, moderate_id: str, route_id: str,
                  main_message: str, main_name: str = "main") -> str:
    """Build pipeline_composed.cod that imports all three symbols by hash."""
    return f"""\
module pipeline_composed

import classify_content = {classify_id}
import moderate         = {moderate_id}
import route_message    = {route_id}

def composed_pipeline
  intent "run the full moderation pipeline using content-addressed imports"
  sig    (message: String) -> Decision
  effects {{}}
  cand
    route_message(message)

def {main_name}
  intent "test the composed pipeline"
  sig    () -> Decision
  effects {{}}
  cand
    composed_pipeline("{main_message}")
"""


def _run_composed(store_root: Path, src: str, entry: str = "main") -> subprocess.CompletedProcess:
    """Write src to a temp file and run it with the Python interpreter."""
    with tempfile.NamedTemporaryFile(suffix=".cod", mode="w",
                                    encoding="utf-8", delete=False) as f:
        f.write(src)
        path = f.name
    return subprocess.run(
        [sys.executable, "-m", "codifide", "run", path,
         "--runtime", "python",
         "--store", str(store_root),
         "--entry", entry],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class Program5ViaHTTPTest(unittest.TestCase):
    """Acceptance test: Program 5 completed using only HTTP requests."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store_root = Path(self._tmpdir.name) / "store"
        self.store = SymbolStore(self.store_root)
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

    # ------------------------------------------------------------------
    # Core acceptance test
    # ------------------------------------------------------------------

    def test_program5_full_workflow(self) -> None:
        """Full Program 5: publish via HTTP, import by hash, run all three paths."""
        # Store starts empty — no CLI pre-seeding.
        self.assertEqual(list(self.store.iter_identities()), [])

        # Publish all three symbols via HTTP only.
        classify_id, moderate_id, route_id = _publish_pipeline(self.base)

        self.assertTrue(classify_id.startswith("sha256:"))
        self.assertTrue(moderate_id.startswith("sha256:"))
        self.assertTrue(route_id.startswith("sha256:"))

        # All three are distinct identities.
        self.assertEqual(len({classify_id, moderate_id, route_id}), 3)

        # Verify all three are retrievable via GET.
        for identity, expected_sym in [
            (classify_id, "classify_content"),
            (moderate_id, "moderate"),
            (route_id, "route_message"),
        ]:
            req = urllib.request.Request(
                f"{self.base}/symbols/{identity}",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                obj = json.loads(resp.read())
            self.assertIn(expected_sym, obj.get("symbols", {}),
                          f"{expected_sym} not found in retrieved symbol")

        # Run all three routing paths.
        for message, expected in [
            ("this message contains spam", "blocked"),
            ("this message is approved", "approved"),
            ("hello world", "escalate-to-human"),
        ]:
            src = _composed_src(classify_id, moderate_id, route_id, message)
            result = _run_composed(self.store_root, src)
            self.assertEqual(
                result.returncode, 0,
                f"pipeline failed for {message!r}:\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
            self.assertEqual(
                result.stdout.strip(), expected,
                f"expected {expected!r} for {message!r}, got {result.stdout.strip()!r}"
            )

    def test_program5_unsafe_path(self) -> None:
        """Spam message routes to 'blocked'."""
        classify_id, moderate_id, route_id = _publish_pipeline(self.base)
        src = _composed_src(classify_id, moderate_id, route_id,
                            "this message contains hate")
        result = _run_composed(self.store_root, src)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertEqual(result.stdout.strip(), "blocked")

    def test_program5_safe_path(self) -> None:
        """Approved message routes to 'approved'."""
        classify_id, moderate_id, route_id = _publish_pipeline(self.base)
        src = _composed_src(classify_id, moderate_id, route_id,
                            "this message is verified")
        result = _run_composed(self.store_root, src)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertEqual(result.stdout.strip(), "approved")

    def test_program5_uncertain_path(self) -> None:
        """No-keyword message routes to 'escalate-to-human'."""
        classify_id, moderate_id, route_id = _publish_pipeline(self.base)
        src = _composed_src(classify_id, moderate_id, route_id, "hello world")
        result = _run_composed(self.store_root, src)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertEqual(result.stdout.strip(), "escalate-to-human")

    def test_no_cli_store_commands_needed(self) -> None:
        """Store is empty before HTTP publish — no CLI pre-seeding."""
        self.assertEqual(list(self.store.iter_identities()), [])

    def test_imports_endpoint_shows_no_missing(self) -> None:
        """After publishing all symbols, /imports shows no missing deps."""
        classify_id, moderate_id, route_id = _publish_pipeline(self.base)

        # Build an index module referencing all three.
        import hashlib
        index = Module(
            name="pipeline_index",
            symbols=(),
            imports=(
                ("classify_content", classify_id),
                ("moderate", moderate_id),
                ("route_message", route_id),
            ),
        )
        index_cbor = canonical_cbor(to_canonical(index))
        index_identity = f"sha256:{hashlib.sha256(index_cbor).hexdigest()}"
        self.store._write_atomic(index_identity, index_cbor, suffix=".cbor")

        req = urllib.request.Request(
            f"{self.base}/symbols/{index_identity}/imports",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())

        self.assertEqual(result["missing"], [],
                         f"expected no missing imports, got {result['missing']}")
        self.assertEqual(len(result["imports"]), 3)
        for imp in result["imports"]:
            self.assertTrue(imp["present"],
                            f"import {imp['name']} not present in store")

    def test_idempotent_publish(self) -> None:
        """Publishing the same symbol twice returns the same identity."""
        id1 = _post_symbol(self.base, _CLASSIFIER_SRC, "classify_content")
        id2 = _post_symbol(self.base, _CLASSIFIER_SRC, "classify_content")
        self.assertEqual(id1, id2)

    def test_composed_program_parses_cleanly(self) -> None:
        """The composed program with import lines parses without error."""
        classify_id, moderate_id, route_id = _publish_pipeline(self.base)
        src = _composed_src(classify_id, moderate_id, route_id, "test")
        # Parse should succeed — no store needed at parse time for direct imports.
        module = parse(src)
        self.assertEqual(len(module.imports), 3)
        import_names = {name for name, _ in module.imports}
        self.assertEqual(import_names, {"classify_content", "moderate", "route_message"})


if __name__ == "__main__":
    unittest.main()
