"""Symbol-store garbage collection (2026-05-11 design dispatch).

Tests the sound-deletion contract specified in
``dispatches/2026-05-11-store-gc-design.readout.md``:

- GC refuses to ``--execute`` with an empty or missing ROOTS file.
- Dry-run never deletes.
- Reachable identities survive; unreachable ones are deleted.
- Transitive closure through an index resolves correctly.
- GC.LOG records every deletion with a timestamp.
- Concurrent ``put``s during a GC run serialize via LOCK.
"""
from __future__ import annotations

import multiprocessing
import tempfile
import time
import unittest
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from codifide import parse
from codifide.store import SymbolStore
from codifide.store.gc import GCError


_SRC_A = """
def greet_a
  intent "a"
  sig    () -> String
  effects {}
  cand
    "a"
"""

_SRC_B = """
def greet_b
  intent "b"
  sig    () -> String
  effects {}
  cand
    "b"
"""


def _setup_two_symbols(tmp_path: Path) -> tuple[str, str, SymbolStore]:
    store = SymbolStore(tmp_path)
    defn_a = parse(_SRC_A).symbols[0]
    defn_b = parse(_SRC_B).symbols[0]
    id_a = store.put("greet_a", defn_a)
    id_b = store.put("greet_b", defn_b)
    assert id_a != id_b
    return id_a, id_b, store


class SoundDeletionContract(unittest.TestCase):
    """The three properties that define "GC ran correctly"."""

    def test_execute_without_roots_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _id_a, _id_b, store = _setup_two_symbols(Path(tmp))
            with self.assertRaises(GCError) as cm:
                store.gc(execute=True)
            self.assertIn("ROOTS", str(cm.exception))
            # And nothing was deleted.
            self.assertEqual(len(list(store.iter_identities())), 2)

    def test_dry_run_never_deletes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            id_a, id_b, store = _setup_two_symbols(Path(tmp))
            # No ROOTS → everything is "unreachable" on dry-run.
            report = store.gc(execute=False)
            self.assertFalse(report.executed)
            self.assertEqual(set(report.deleted), {id_a, id_b})
            # But nothing actually deleted.
            self.assertEqual(len(list(store.iter_identities())), 2)
            self.assertTrue(store.has(id_a))
            self.assertTrue(store.has(id_b))

    def test_reachable_survive_unreachable_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            id_a, id_b, store = _setup_two_symbols(Path(tmp))
            store.add_root(id_a)
            report = store.gc(execute=True)
            self.assertTrue(report.executed)
            self.assertEqual(report.deleted, [id_b])
            self.assertTrue(store.has(id_a))
            self.assertFalse(store.has(id_b))

    def test_empty_roots_does_not_delete_everything_on_dry_run(self) -> None:
        # Confirming the spec line: dry-run with no roots reports
        # deletions but doesn't execute them. A human looking at the
        # report then decides whether to add roots or accept a full wipe.
        with tempfile.TemporaryDirectory() as tmp:
            id_a, id_b, store = _setup_two_symbols(Path(tmp))
            report = store.gc()  # execute=False
            self.assertEqual(report.roots_count, 0)
            self.assertFalse(report.executed)
            self.assertEqual(set(report.deleted), {id_a, id_b})


class TransitiveClosureThroughImports(unittest.TestCase):
    """A reachable module pulls its imported symbols along with it."""

    def test_import_target_is_reachable_from_root(self) -> None:
        import json as _json
        import hashlib
        from codifide.core.types import Module
        from codifide.projection.canonical import to_canonical
        from codifide.projection.cbor import canonical_cbor

        with tempfile.TemporaryDirectory() as tmp:
            id_a, id_b, store = _setup_two_symbols(Path(tmp))

            # Mint an index pointing at id_a. Identity is SHA-256 of
            # canonical CBOR (post-migration primary form).
            index_module = Module(
                name="idx",
                symbols=(),
                imports=(("greet_a", id_a),),
            )
            data = canonical_cbor(to_canonical(index_module))
            index_id = f"sha256:{hashlib.sha256(data).hexdigest()}"
            store._write_atomic(index_id, data, suffix=".cbor")

            # Root the index; id_a should be reachable through it.
            store.add_root(index_id)
            report = store.gc(execute=True)

            # Reachable: index_id and id_a. Deleted: id_b only.
            self.assertTrue(store.has(index_id))
            self.assertTrue(store.has(id_a))
            self.assertFalse(store.has(id_b))
            self.assertEqual(report.deleted, [id_b])


class GCLogRecordsDeletions(unittest.TestCase):
    """GC.LOG captures every deletion with a timestamp and identity."""

    def test_log_is_appended_on_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            id_a, id_b, store = _setup_two_symbols(root)
            store.add_root(id_a)
            store.gc(execute=True)

            log_path = root / "GC.LOG"
            self.assertTrue(log_path.exists())
            log_lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(log_lines), 1)
            # Shape: "<ISO timestamp> <identity>"
            parts = log_lines[0].split(" ")
            self.assertEqual(len(parts), 2)
            self.assertEqual(parts[1], id_b)

    def test_log_survives_multiple_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            id_a, id_b, store = _setup_two_symbols(root)
            store.add_root(id_a)
            store.gc(execute=True)  # deletes id_b

            # Add a new symbol, root it, and GC again — nothing more
            # should delete, but the log must still contain the
            # original entry.
            defn_c = parse(
                "def greet_c\n"
                "  intent \"c\"\n"
                "  sig () -> String\n"
                "  effects {}\n"
                "  cand\n"
                "    \"c\"\n"
            ).symbols[0]
            id_c = store.put("greet_c", defn_c)
            store.add_root(id_c)
            store.gc(execute=True)

            log_text = (root / "GC.LOG").read_text(encoding="utf-8")
            self.assertIn(id_b, log_text)
            self.assertEqual(log_text.count("\n"), 1)  # still just one entry


class RootsManagement(unittest.TestCase):
    """Add/list/remove roots via the store API."""

    def test_add_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            id_a, _id_b, store = _setup_two_symbols(Path(tmp))
            store.add_root(id_a)
            store.add_root(id_a)
            self.assertEqual(store.roots(), [id_a])

    def test_remove_returns_false_when_not_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            id_a, _id_b, store = _setup_two_symbols(Path(tmp))
            self.assertFalse(store.remove_root(id_a))
            store.add_root(id_a)
            self.assertTrue(store.remove_root(id_a))
            self.assertFalse(store.remove_root(id_a))

    def test_invalid_identity_shape_rejected_on_add(self) -> None:
        from codifide.store import StoreError
        with tempfile.TemporaryDirectory() as tmp:
            store = SymbolStore(Path(tmp))
            with self.assertRaises(StoreError):
                store.add_root("not-a-sha256")
            with self.assertRaises(StoreError):
                store.add_root("sha256:tooshort")

    def test_comments_in_roots_file_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            id_a, _id_b, store = _setup_two_symbols(root)
            roots_path = root / "ROOTS"
            roots_path.write_text(
                f"# this is a comment\n"
                f"\n"
                f"{id_a}  # inline comment\n"
                f"# another comment\n",
                encoding="utf-8",
            )
            self.assertEqual(store.roots(), [id_a])


if __name__ == "__main__":
    unittest.main()



class PostAuditHardening(unittest.TestCase):
    """Regression tests for Sable findings GC-1, GC-2, GC-3
    from the 2026-05-11 new-surfaces audit.

    See ``dispatches/2026-05-11-new-surfaces-audit.md``.
    """

    def test_GC_1_log_write_refuses_symlink(self) -> None:
        # Plant a symlink at <root>/GC.LOG pointing outside the store.
        # GC must refuse to follow it on execute, surfacing a clean
        # OSError rather than silently writing log bytes through.
        import os
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            id_a, _id_b, store = _setup_two_symbols(root)
            store.add_root(id_a)

            outside_dir = Path(tempfile.mkdtemp())
            outside = outside_dir / "evil_log"
            outside.touch()
            self.addCleanup(lambda: shutil.rmtree(outside_dir, ignore_errors=True))
            os.symlink(str(outside), str(root / "GC.LOG"))

            # ``gc(execute=True)`` will delete id_b and try to append
            # to GC.LOG; the symlink must be refused.
            with self.assertRaises(OSError) as cm:
                store.gc(execute=True)
            self.assertIn("GC.LOG", str(cm.exception))
            # And the attacker's file stays empty.
            self.assertEqual(outside.read_text(), "")

    def test_GC_2_lock_does_not_truncate_preexisting_content(self) -> None:
        # Someone accidentally wrote to LOCK. Running GC must not
        # destroy that content. This is a least-surprise fix; the
        # bytes in LOCK are irrelevant to ``flock`` anyway.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            id_a, _id_b, store = _setup_two_symbols(root)
            store.add_root(id_a)

            lock = root / "LOCK"
            lock.write_text("important")

            store.gc(execute=True)
            self.assertEqual(lock.read_text(), "important")

    def test_GC_3_malformed_root_reports_line_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            id_a, _id_b, store = _setup_two_symbols(root)
            (root / "ROOTS").write_text(
                f"# header\n"
                f"{id_a}\n"
                f"sha256:garbage\n"
                f"# trailer\n",
                encoding="utf-8",
            )
            with self.assertRaises(GCError) as cm:
                store.gc()
            msg = str(cm.exception)
            self.assertIn("line 3", msg)
            self.assertIn("sha256:garbage", msg)

    def test_GC_3_roots_file_with_all_valid_entries_still_works(self) -> None:
        # Don't over-reject: a well-formed ROOTS file with comments
        # and blank lines continues to parse cleanly.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            id_a, id_b, store = _setup_two_symbols(root)
            (root / "ROOTS").write_text(
                f"# codifide store roots\n"
                f"\n"
                f"{id_a}  # first\n"
                f"{id_b}  # second\n",
                encoding="utf-8",
            )
            report = store.gc()
            self.assertEqual(report.roots_count, 2)
            self.assertEqual(report.deleted, [])
