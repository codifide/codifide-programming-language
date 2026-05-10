"""Concurrency invariants for :class:`SymbolStore`.

The store's write path uses ``tempfile.mkstemp`` + ``os.replace`` to move
bytes into place atomically. That pattern only matters if two writers can
race on the same identity without corrupting each other's work. These
tests spawn real OS processes (not threads — GIL would hide races) and
assert the invariants the store advertises:

  1. Many writers ``put``-ing the same symbol end up with exactly one
     object on disk, all of them receive the same identity back, and no
     ``.noema-*.tmp`` temp files are left behind.
  2. Writers operating on distinct symbols never trip over each other —
     every symbol lands in its own shard directory and nothing leaks.

Workers live at module scope so ``multiprocessing`` can pickle them
across the ``fork``/``spawn`` boundary on every supported platform.
"""
from __future__ import annotations

import multiprocessing
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import List

import noema
from noema.store import SymbolStore


# ---------------------------------------------------------------------------
# Top-level workers (must be picklable)
# ---------------------------------------------------------------------------

# A valid single-symbol source that every worker will parse. Using the
# exact same source across workers is the point — it guarantees identical
# canonical bytes and therefore an identical identity.
SAME_SYMBOL_SOURCE = (
    "def hello\n"
    "  intent \"greet\"\n"
    "  sig    (name: String) -> String\n"
    "  effects {}\n"
    "  cand\n"
    "    \"hello, \" ++ name\n"
)


def _worker_put_same_symbol(root: str) -> str:
    """Parse the shared source and put it into the store at ``root``.

    Returns the identity the store produced so the parent can compare
    identities across workers.
    """
    module = noema.parse(SAME_SYMBOL_SOURCE)
    store = SymbolStore(root)
    return store.put("hello", module.symbols[0])


def _worker_put_unique_symbol(args: tuple[str, int]) -> tuple[str, str]:
    """Parse a worker-specific source and put its only symbol.

    Each worker's symbol differs in its intent string so the canonical
    bytes (and therefore the identity) differ. The candidate body is the
    worker id, so the definition is also literally distinct.
    """
    root, worker_id = args
    # Name and intent are both parameterized so the hash is unique per worker.
    name = f"fn_{worker_id}"
    source = (
        f"def {name}\n"
        f"  intent \"worker-{worker_id}\"\n"
        f"  sig    () -> Int\n"
        f"  effects {{}}\n"
        f"  cand\n"
        f"    {worker_id}\n"
    )
    module = noema.parse(source)
    store = SymbolStore(root)
    return name, store.put(name, module.symbols[0])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list_objects(root: Path) -> List[Path]:
    """Return every stored ``.json`` object under ``<root>/sha256``."""
    base = root / "sha256"
    if not base.exists():
        return []
    return sorted(base.glob("*/*.json"))


def _list_temp_files(root: Path) -> List[Path]:
    """Return every leftover ``.noema-*.tmp`` file under ``<root>/sha256``.

    The store writes through ``tempfile.mkstemp(prefix='.noema-',
    suffix='.tmp', ...)`` and renames the result into place. A crashed
    or interrupted write would leave a ``.noema-*.tmp`` behind, so
    finding any after a clean run indicates a bug in the write path.
    """
    base = root / "sha256"
    if not base.exists():
        return []
    # Pattern covers both shard-level and base-level locations so a
    # leaked temp anywhere in the store tree is surfaced.
    return sorted(base.glob("**/.noema-*.tmp"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class StoreConcurrencyTests(unittest.TestCase):
    """SymbolStore behaves correctly under concurrent writers."""

    # Using 'spawn' makes the test behave the same on macOS (default
    # 'spawn'), Linux ('fork' default), and anywhere else. It also makes
    # each worker import noema fresh, which more faithfully exercises
    # the cross-process write path.
    _MP_CONTEXT = multiprocessing.get_context("spawn")
    _N_WORKERS = 8

    def test_concurrent_puts_of_same_symbol_produce_one_object(self) -> None:
        """Eight processes put the same symbol; exactly one object lands."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Initialize the store layout from the parent so workers do
            # not race on the initial mkdir. This matches how real uses
            # open the store once and hand the root to workers.
            SymbolStore(root)

            with ProcessPoolExecutor(
                max_workers=self._N_WORKERS,
                mp_context=self._MP_CONTEXT,
            ) as pool:
                identities = list(
                    pool.map(_worker_put_same_symbol, [str(root)] * self._N_WORKERS)
                )

            # Every worker must return the same identity — content
            # addressing is pointless if identical bytes hash differently.
            self.assertEqual(
                len(set(identities)),
                1,
                f"workers disagreed on identity: {identities}",
            )

            # Exactly one object on disk, even though eight processes
            # wrote concurrently. This is the idempotency invariant.
            objects = _list_objects(root)
            self.assertEqual(
                len(objects),
                1,
                f"expected exactly one stored object, got "
                f"{len(objects)}: {[str(p) for p in objects]}",
            )

            # No leaked temp files. A leak here would indicate the
            # atomic-write path bailed out without cleaning up.
            leaked = _list_temp_files(root)
            self.assertEqual(
                leaked,
                [],
                f"found leftover tempfiles after concurrent puts: "
                f"{[str(p) for p in leaked]}",
            )

    def test_concurrent_puts_of_different_symbols_all_succeed(self) -> None:
        """Eight processes put eight distinct symbols; all land, all unique."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            SymbolStore(root)

            work = [(str(root), worker_id) for worker_id in range(self._N_WORKERS)]
            with ProcessPoolExecutor(
                max_workers=self._N_WORKERS,
                mp_context=self._MP_CONTEXT,
            ) as pool:
                results = list(pool.map(_worker_put_unique_symbol, work))

            names = [name for name, _ in results]
            identities = [identity for _, identity in results]

            # Every worker got a unique identity because every input
            # was unique. If two collided, canonicalization is broken.
            self.assertEqual(
                len(set(identities)),
                self._N_WORKERS,
                f"expected {self._N_WORKERS} unique identities, got "
                f"{len(set(identities))}: {identities}",
            )
            self.assertEqual(len(set(names)), self._N_WORKERS)

            # Exactly N objects on disk — one per worker.
            objects = _list_objects(root)
            self.assertEqual(
                len(objects),
                self._N_WORKERS,
                f"expected {self._N_WORKERS} stored objects, got "
                f"{len(objects)}: {[str(p) for p in objects]}",
            )

            # Each returned identity must actually be present.
            store = SymbolStore(root)
            for identity in identities:
                self.assertTrue(
                    store.has(identity),
                    f"worker reported identity {identity} but it is "
                    f"not on disk",
                )

            # No leftover temp files in any shard.
            leaked = _list_temp_files(root)
            self.assertEqual(
                leaked,
                [],
                f"found leftover tempfiles after concurrent puts: "
                f"{[str(p) for p in leaked]}",
            )


if __name__ == "__main__":
    unittest.main()
