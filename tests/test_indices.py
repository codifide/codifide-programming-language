"""Index modules and ``from <identity> import ...``.

An index is a module whose imports table is its export map. The
capability it enables is discovery-by-name once you know an index's
identity: agents agree on one hash (the index), and from that hash
they can reach every symbol the index names without having to share
per-symbol hashes out of band.

These tests pin down the properties that make indices useful and
safe:

- An index is itself content-addressed. Same exports produce the
  same identity; different exports produce a different identity.
- Import order does not affect the index identity (canonical form
  sorts keys).
- ``from <index> import <name>`` resolves through the store at parse
  time to the same per-symbol identity the consumer would have
  written directly, so the rest of the system (effect check, runtime
  resolution, tamper detection) keeps working unchanged.
- A ``from`` import of a name not in the target index is rejected at
  parse time with a clear error.
- Indices compose: a consumer can import through an index into a
  module whose body calls those imports like any local ``def``.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from noema import canonical_bytes, parse, run, to_canonical
from noema.core.types import Module
from noema.runtime.errors import NoemaError, ParseError
from noema.store import SymbolStore


LIB_SRC = """
module greet_lib

def hello
  intent "format a hello"
  sig    (name: String) -> String
  effects {}
  cand
    "Hello, " ++ name

def goodbye
  intent "format a goodbye"
  sig    (name: String) -> String
  effects {}
  cand
    "Goodbye, " ++ name
"""


def _publish_index(store: SymbolStore, name: str, entries: list[tuple[str, str]]) -> str:
    """Helper: mint an index module and store it, returning its identity."""
    index = Module(name=name, symbols=(), imports=tuple(entries))
    canonical = to_canonical(index)
    data = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    identity = f"sha256:{hashlib.sha256(data).hexdigest()}"
    store._write_atomic(identity, data)
    return identity


class IndexIdentityTests(unittest.TestCase):
    """An index is a content-addressed module; its hash is the spec."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = SymbolStore(self._tmp.name)
        lib = parse(LIB_SRC)
        self.hello_id = self.store.put("hello", lib.symbols[0])
        self.goodbye_id = self.store.put("goodbye", lib.symbols[1])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_same_entries_produce_same_identity(self) -> None:
        a = _publish_index(
            self.store,
            "idx",
            [("hello", self.hello_id), ("goodbye", self.goodbye_id)],
        )
        b = _publish_index(
            self.store,
            "idx",
            [("hello", self.hello_id), ("goodbye", self.goodbye_id)],
        )
        self.assertEqual(a, b)

    def test_entry_order_does_not_affect_identity(self) -> None:
        a = _publish_index(
            self.store,
            "idx",
            [("hello", self.hello_id), ("goodbye", self.goodbye_id)],
        )
        b = _publish_index(
            self.store,
            "idx",
            [("goodbye", self.goodbye_id), ("hello", self.hello_id)],
        )
        self.assertEqual(a, b)

    def test_module_name_is_part_of_identity(self) -> None:
        a = _publish_index(
            self.store,
            "idx_a",
            [("hello", self.hello_id)],
        )
        b = _publish_index(
            self.store,
            "idx_b",
            [("hello", self.hello_id)],
        )
        self.assertNotEqual(a, b)

    def test_different_entries_change_identity(self) -> None:
        a = _publish_index(
            self.store,
            "idx",
            [("hello", self.hello_id)],
        )
        b = _publish_index(
            self.store,
            "idx",
            [("hello", self.hello_id), ("goodbye", self.goodbye_id)],
        )
        self.assertNotEqual(a, b)


class FromImportResolutionTests(unittest.TestCase):
    """``from <identity> import ...`` resolves through the index at parse time."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = SymbolStore(self._tmp.name)
        lib = parse(LIB_SRC)
        self.hello_id = self.store.put("hello", lib.symbols[0])
        self.goodbye_id = self.store.put("goodbye", lib.symbols[1])
        self.index_id = _publish_index(
            self.store,
            "greet_library",
            [("hello", self.hello_id), ("goodbye", self.goodbye_id)],
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _consumer(self, names: str) -> str:
        return f"""
module consumer

from {self.index_id} import {names}

def main
  intent "use imports through an index"
  sig    () -> String
  effects {{}}
  cand
    hello("Ada")
"""

    def test_from_import_resolves_and_runs(self) -> None:
        src = self._consumer("hello")
        m = parse(src, store=self.store)
        result = run(m, "main", store=self.store)
        self.assertEqual(result, "Hello, Ada")

    def test_from_import_binds_to_the_indexs_mapping(self) -> None:
        # After parsing, the consumer's imports must contain
        # (hello -> hello_id) — same identity as a direct
        # `import hello = sha256:...` would have produced.
        m = parse(self._consumer("hello"), store=self.store)
        self.assertIn(("hello", self.hello_id), m.imports)

    def test_from_import_requires_store(self) -> None:
        with self.assertRaises(ParseError) as cm:
            parse(self._consumer("hello"))
        self.assertIn("requires a store", str(cm.exception).lower())

    def test_from_import_rejects_missing_name(self) -> None:
        with self.assertRaises(ParseError) as cm:
            parse(self._consumer("nonexistent"), store=self.store)
        self.assertIn("does not export", str(cm.exception).lower())

    def test_from_import_rejects_malformed_identity(self) -> None:
        src = """
module consumer
from sha256:not-a-hex import hello
def main
  intent "x"
  sig () -> String
  effects {}
  cand
    "x"
"""
        with self.assertRaises(ParseError) as cm:
            parse(src, store=self.store)
        self.assertIn("identity", str(cm.exception).lower())

    def test_multiple_names_in_one_from_import(self) -> None:
        src = f"""
module consumer

from {self.index_id} import hello, goodbye

def main
  intent "use both"
  sig    () -> String
  effects {{}}
  cand
    hello("Ada") ++ " " ++ goodbye("Ada")
"""
        m = parse(src, store=self.store)
        result = run(m, "main", store=self.store)
        self.assertEqual(result, "Hello, Ada Goodbye, Ada")

    def test_local_def_shadows_imported_name(self) -> None:
        # Adversarial probe from Sable's review of the index surface.
        # When a local def collides with an imported name, the local
        # wins. This is the documented shadowing rule (spec §Shadowing)
        # and the behavior we want: a consumer's local intent trumps
        # something they imported.
        src = f"""
module consumer

from {self.index_id} import hello

def hello
  intent "locally defined hello wins over the imported one"
  sig    (name: String) -> String
  effects {{}}
  cand
    "local hello to " ++ name

def main
  intent "calls hello; must hit the local def"
  sig    () -> String
  effects {{}}
  cand
    hello("Ada")
"""
        m = parse(src, store=self.store)
        self.assertEqual(run(m, "main", store=self.store), "local hello to Ada")

    def test_from_import_of_non_index_target_rejected(self) -> None:
        # A `from <hash>` where <hash> resolves to a plain symbol (no
        # imports map) must be rejected with a clear error, not
        # silently accept zero names.
        src = f"""
module consumer

from {self.hello_id} import hello

def main
  intent "try to from-import a non-index"
  sig    (n: String) -> String
  effects {{}}
  cand
    hello(n)
"""
        with self.assertRaises(ParseError) as cm:
            parse(src, store=self.store)
        self.assertIn("does not export", str(cm.exception).lower())


class FromImportEffectCheckTests(unittest.TestCase):
    """Effect discipline flows through an index the same as a direct import."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = SymbolStore(self._tmp.name)
        # Impure library symbol.
        lib = parse(
            """
module impure_lib

def shout
  intent "io"
  sig    (m: String) -> String
  effects {io.stdout}
  cand
    io.say(m)
"""
        )
        self.shout_id = self.store.put("shout", lib.symbols[0])
        self.index_id = _publish_index(
            self.store, "impure_idx", [("shout", self.shout_id)]
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pure_consumer_cannot_smuggle_effects_through_index(self) -> None:
        # The index is not an effect laundering tool. A pure consumer
        # importing an impure symbol through an index must still fail
        # the transitive effect check.
        from noema.runtime.errors import EffectViolation

        src = f"""
module consumer

from {self.index_id} import shout

def main
  intent "pure caller"
  sig    () -> String
  effects {{}}
  cand
    shout("x")
"""
        m = parse(src, store=self.store)
        with self.assertRaises(EffectViolation):
            run(m, "main", store=self.store)


if __name__ == "__main__":
    unittest.main()
