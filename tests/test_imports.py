"""Content-addressed imports.

The capability: a module declares ``import <local_name> = sha256:<hex>``,
and at runtime the interpreter resolves that identity through a symbol
store into a full Definition. The imported callee is indistinguishable
from a local ``def`` at the call site — same effect check, same contract
discipline, same candidate dispatch.

These tests pin down the properties that make the capability useful:

- Imports resolve through the store.
- Tampering with the store raises IntegrityError, never returns a value
  (the store's guarantee flowing through to the runtime).
- The transitive effect check treats imported callees exactly like
  local ones — a pure caller cannot launder effects through an imported
  impure callee.
- Modules with imports canonicalize stably regardless of declaration
  order (sorted in canonical form).
- Modules with imports change their canonical bytes when imports
  change, producing different content hashes.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from noema import parse, run, to_canonical, from_canonical
from noema.runtime.errors import EffectViolation, NoemaError, ParseError
from noema.store import IntegrityError, SymbolStore


LIB_SRC = """
module lib

def hello
  intent "format a greeting"
  sig    (name: String) -> String
  effects {}
  cand
    "Hello, " ++ name ++ "."
"""


LIB_EFFECTFUL_SRC = """
module lib

def shout
  intent "write to stdout"
  sig    (msg: String) -> String
  effects {io.stdout}
  cand
    io.say(msg)
"""


def _consumer_src(hash_: str) -> str:
    return f"""
module consumer

import greeting = {hash_}

def main
  intent "consume a library symbol by identity"
  sig    () -> String
  effects {{}}
  cand
    greeting("Ada")
"""


class ImportResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = SymbolStore(self._tmp.name)
        # Stock the store with the library symbol.
        self.lib_module = parse(LIB_SRC)
        self.lib_id = self.store.put("hello", self.lib_module.symbols[0])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_import_resolves_and_executes(self) -> None:
        m = parse(_consumer_src(self.lib_id))
        result = run(m, "main", store=self.store)
        self.assertEqual(result, "Hello, Ada.")

    def test_import_without_store_is_rejected(self) -> None:
        m = parse(_consumer_src(self.lib_id))
        with self.assertRaises(NoemaError) as cm:
            run(m, "main")
        self.assertIn("no store", str(cm.exception).lower())

    def test_import_of_missing_identity_is_rejected(self) -> None:
        bogus = "sha256:" + "0" * 64
        m = parse(_consumer_src(bogus))
        with self.assertRaises(NoemaError) as cm:
            run(m, "main", store=self.store)
        self.assertIn("cannot resolve import", str(cm.exception).lower())

    def test_tampered_imported_symbol_raises_integrity_error(self) -> None:
        # Corrupt the library symbol on disk and verify the interpreter
        # surfaces an integrity error rather than silently loading
        # tampered code.
        digest = self.lib_id.removeprefix("sha256:")
        path = Path(self._tmp.name) / "sha256" / digest[:2] / f"{digest[2:]}.json"
        path.write_bytes(path.read_bytes() + b" /* tampered */")
        m = parse(_consumer_src(self.lib_id))
        with self.assertRaises(NoemaError) as cm:
            run(m, "main", store=self.store)
        # The wrapped cause is an IntegrityError; the outer Noema error
        # carries the message.
        self.assertIsInstance(cm.exception.__cause__, IntegrityError)


class ImportEffectCheckTests(unittest.TestCase):
    """Transitive effect check applies to imports uniformly.

    The point of the spec's "effects are in the type" claim is that a
    caller cannot perform effects it did not declare. Content-addressed
    imports must not create a loophole — if they did, an adversary could
    publish an effectful symbol under a benign-sounding identity and
    smuggle side effects into any consumer that imports it.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = SymbolStore(self._tmp.name)
        # Effectful library symbol: declares io.stdout.
        m = parse(LIB_EFFECTFUL_SRC)
        self.lib_id = self.store.put("shout", m.symbols[0])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pure_caller_cannot_import_effectful_callee(self) -> None:
        # The consumer declares effects {} but imports a symbol that
        # needs effects {io.stdout}. Module load must reject this.
        src = f"""
module consumer

import shout = {self.lib_id}

def main
  intent "pure caller, impure import"
  sig    () -> String
  effects {{}}
  cand
    shout("x")
"""
        m = parse(src)
        with self.assertRaises(EffectViolation) as cm:
            run(m, "main", store=self.store)
        self.assertEqual(cm.exception.fn, "main")
        self.assertEqual(cm.exception.observed, "io.stdout")

    def test_matching_effect_declaration_is_accepted(self) -> None:
        # The mirror: when the caller declares the imported callee's
        # effects, the check passes and the call runs.
        src = f"""
module consumer

import shout = {self.lib_id}

def main
  intent "caller declares what the import uses"
  sig    () -> String
  effects {{io.stdout}}
  cand
    shout("legit")
"""
        m = parse(src)
        run(m, "main", store=self.store)


class ImportCanonicalFormTests(unittest.TestCase):
    """Canonical form handles imports with the same invariants as symbols."""

    def test_round_trip_preserves_imports(self) -> None:
        hash_a = "sha256:" + "a" * 64
        hash_b = "sha256:" + "b" * 64
        src = f"""
module consumer

import beta = {hash_b}
import alpha = {hash_a}

def main
  intent "x"
  sig () -> Int
  effects {{}}
  cand
    1
"""
        m = parse(src)
        j1 = to_canonical(m)
        m2 = from_canonical(j1)
        j2 = to_canonical(m2)
        self.assertEqual(j1, j2)
        # Canonical form emits imports sorted by key.
        self.assertEqual(list(j1["imports"].keys()), ["alpha", "beta"])

    def test_modules_without_imports_omit_the_key(self) -> None:
        src = """
def x
  intent "no imports"
  sig () -> Int
  effects {}
  cand
    1
"""
        m = parse(src)
        j = to_canonical(m)
        self.assertNotIn("imports", j)

    def test_different_imports_produce_different_canonical_bytes(self) -> None:
        # This is what makes import-by-identity safe: a module's
        # canonical bytes (and therefore its hash) depend on which
        # identities it imports. Swapping an import is a new module.
        from noema import canonical_bytes

        hash_a = "sha256:" + "a" * 64
        hash_b = "sha256:" + "b" * 64
        src_a = f"""
module m
import x = {hash_a}
def main
  intent "x"
  sig () -> Int
  effects {{}}
  cand
    1
"""
        src_b = src_a.replace(hash_a, hash_b)
        self.assertNotEqual(
            canonical_bytes(parse(src_a)),
            canonical_bytes(parse(src_b)),
        )


class ImportSurfaceSyntaxTests(unittest.TestCase):
    def test_malformed_identity_is_rejected_at_parse_time(self) -> None:
        src = """
module consumer
import x = sha256:not-a-hex-digest
def main
  intent "x"
  sig () -> Int
  effects {}
  cand
    1
"""
        with self.assertRaises(ParseError) as cm:
            parse(src)
        self.assertIn("identity", str(cm.exception).lower())

    def test_import_without_equals_is_rejected(self) -> None:
        src = """
module consumer
import x sha256:0000000000000000000000000000000000000000000000000000000000000000
def main
  intent "x"
  sig () -> Int
  effects {}
  cand
    1
"""
        with self.assertRaises(ParseError):
            parse(src)


if __name__ == "__main__":
    unittest.main()
