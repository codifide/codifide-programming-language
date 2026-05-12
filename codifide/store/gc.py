"""Symbol-store garbage collection.

See ``dispatches/2026-05-11-store-gc-design.readout.md`` for the full
design and rationale. Summary:

- Roots are user-declared in a ``ROOTS`` file at the store root. An
  empty or missing ``ROOTS`` file disables GC entirely; this is a
  deliberate footgun guard, not an oversight.
- Reachability is transitive closure over the ``imports`` map of every
  module found through a root. A symbol is live iff it is reachable
  from at least one root.
- GC is dry-run by default: ``SymbolStore.gc()`` returns a report of
  what *would* be deleted but touches nothing. ``SymbolStore.gc(execute=True)``
  actually deletes and appends to ``GC.LOG``.
- Concurrency safety: GC acquires a file lock at ``<root>/LOCK`` for
  the duration of a run. Concurrent ``put``s that land between the
  closure computation and the delete sweep are treated as garbage and
  will be deleted (they weren't reachable at closure time). To avoid
  losing fresh writes, don't run GC while writing. The lock prevents
  two concurrent GCs from racing each other.

Sound-deletion contract: for every identity ``I`` that ``gc(execute=True)``
deletes, (a) ``I`` was present in the store at the start of the run,
(b) ``I`` was not reachable from any root's transitive closure at
closure-computation time, and (c) the caller explicitly passed
``execute=True`` with a non-empty ``ROOTS`` file.
"""
from __future__ import annotations

import datetime as _dt
import fcntl
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, FrozenSet, Iterable, List, Optional, Set

if TYPE_CHECKING:
    from .symbol_store import SymbolStore

from ..projection.cbor_decoder import decode_canonical_cbor


class GCError(Exception):
    """Raised when GC cannot run under the sound-deletion contract.

    The most common cause is a missing or empty ``ROOTS`` file; that
    case is *not* "nothing is reachable, delete everything" — it is
    "the user has not declared any roots, so we refuse to delete
    anything."
    """


@dataclass
class GCReport:
    """Result of a GC run.

    ``executed`` distinguishes dry-run from real deletion. ``deleted``
    lists identities that were (or would be) removed; ``preserved``
    counts the reachable ones so callers can report "kept N, deleted
    M" without re-walking.
    """
    executed: bool
    deleted: List[str]
    preserved: int
    bytes_freed: int
    roots_count: int

    def summary(self) -> str:
        verb = "deleted" if self.executed else "would delete"
        return (
            f"{verb} {len(self.deleted)} identit"
            f"{'y' if len(self.deleted) == 1 else 'ies'}, "
            f"preserved {self.preserved}, "
            f"{self.bytes_freed} bytes reclaimed "
            f"(roots: {self.roots_count})"
        )


ROOTS_FILENAME = "ROOTS"
GC_LOG_FILENAME = "GC.LOG"
GC_LOCK_FILENAME = "LOCK"


def read_roots(store_root: Path) -> List[str]:
    """Parse the ROOTS file into a list of identity strings.

    Format is one identity per line. Lines starting with ``#`` are
    comments. Blank lines are ignored. Trailing whitespace on an
    identity line is stripped; a comment that starts after an
    identity (``sha256:... # label``) has its comment portion
    stripped.

    Validates each entry's identity shape as it reads, and raises
    :class:`GCError` with a line number if any entry is malformed.
    This catches the typo-in-ROOTS case early instead of letting
    a later closure walk raise a less-localized error. Resolves
    Sable finding GC-3 (2026-05-11).

    Returns an empty list if the file does not exist or contains only
    comments / whitespace.
    """
    import re as _re
    _IDENTITY_RE = _re.compile(r"^sha256:[0-9a-f]{64}$")

    roots_path = store_root / ROOTS_FILENAME
    if not roots_path.exists():
        return []
    out: List[str] = []
    for lineno, raw in enumerate(
        roots_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if not _IDENTITY_RE.match(line):
            raise GCError(
                f"malformed identity in ROOTS at line {lineno}: "
                f"{line!r}. Expected `sha256:<64 lowercase hex>`."
            )
        out.append(line)
    return out


def write_roots(store_root: Path, roots: Iterable[str]) -> None:
    """Write the ROOTS file.

    Overwrites existing content. Callers that want to add or remove
    individual roots should go through the ``codifide store roots``
    CLI family, which reads, modifies, and writes atomically.
    """
    roots_path = store_root / ROOTS_FILENAME
    store_root.mkdir(parents=True, exist_ok=True)
    content = "\n".join(roots) + ("\n" if roots else "")
    roots_path.write_text(content, encoding="utf-8")


def transitive_closure(
    store: "SymbolStore",
    roots: Iterable[str],
) -> FrozenSet[str]:
    """Compute the set of identities reachable from any root.

    Walks the ``imports`` map of every module found through a root.
    Returns the full closure including the roots themselves. Missing
    identities (a root that refers to something not in the store) do
    not abort the walk; they are simply not present in the returned
    closure, and the caller can decide whether that is a warning.
    """
    reachable: Set[str] = set()
    frontier: List[str] = list(roots)
    while frontier:
        identity = frontier.pop()
        if identity in reachable:
            continue
        if not store.has(identity):
            # A root or import reference that no longer exists. We
            # include it in ``reachable`` so a later ``in`` check
            # correctly considers it "seen and deliberately missing"
            # rather than a candidate for deletion (GC only deletes
            # identities that ARE in the store and NOT in the
            # closure; missing identities are simply not in the
            # store). Skipping it here means the surviving sweep
            # logic stays simple.
            reachable.add(identity)
            continue
        reachable.add(identity)
        # Pull the module's imports map. Errors in decoding are
        # tolerated as "module is broken; its imports are not
        # reachable"; the module itself stays reachable because a
        # root pointed at it.
        try:
            obj = store.get(identity)
        except Exception:  # noqa: BLE001
            continue
        imports = obj.get("imports", {}) if isinstance(obj, dict) else {}
        if isinstance(imports, dict):
            for target in imports.values():
                if isinstance(target, str) and target not in reachable:
                    frontier.append(target)
    return frozenset(reachable)


class _StoreLock:
    """Context manager around an exclusive file lock at ``<root>/LOCK``.

    Used by GC and by any store operation that wants to serialize
    against GC. We keep the lock scope small because holding it blocks
    ``put``s on other processes. Test-only; the lock is released on
    ``__exit__`` even if the block raises.

    Opens LOCK in append mode (``"a"``) rather than truncating mode
    (``"w"``) so that any pre-existing content — user accident or
    cross-tool metadata — is preserved. The file's byte content is
    irrelevant to ``flock``; what matters is that the inode is stable
    while the lock is held. Resolves Sable finding GC-2 (2026-05-11).
    """

    def __init__(self, store_root: Path) -> None:
        self._path = store_root / GC_LOCK_FILENAME
        self._fh = None

    def __enter__(self) -> "_StoreLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Refuse to proceed if the lock path is a symlink pointing
        # out of the store. Same defense shape the symbol-write path
        # uses; cheap, consistent.
        if self._path.is_symlink():
            raise OSError(
                f"refusing to lock via symlink at {self._path}; "
                f"remove it before retrying"
            )
        self._fh = open(self._path, "a", encoding="utf-8")
        # Block until we can acquire the lock; flock is advisory but
        # every Codifide writer honors it by convention.
        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if self._fh is not None:
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self._fh = None


def gc(
    store: "SymbolStore",
    *,
    execute: bool = False,
) -> GCReport:
    """Run GC against ``store``.

    Dry-run by default. When ``execute`` is ``True`` and the ROOTS file
    is non-empty, walk the store, compute reachability, and delete
    every identity not in the closure. Append each deletion to
    ``<root>/GC.LOG`` so the action is auditable.

    Raises :class:`GCError` if ROOTS is missing or empty AND
    ``execute`` is ``True``. Dry-run with no roots is allowed and
    reports "would delete 0" — the report surfaces the empty-roots
    condition by having ``roots_count == 0``, letting the caller
    decide how to present it.
    """
    roots = read_roots(store.root)
    if execute and not roots:
        raise GCError(
            f"ROOTS file at {store.root / ROOTS_FILENAME} is empty or "
            f"missing; refusing to GC. Add at least one root identity "
            f"before running `codifide store gc --execute`."
        )
    with _StoreLock(store.root):
        all_identities = set(store.iter_identities())
        if roots:
            reachable = transitive_closure(store, roots)
        else:
            # Dry-run with no roots: nothing is reachable, so the
            # report lists everything as "would delete." The caller
            # sees roots_count == 0 and can refuse to ``--execute``
            # with that.
            reachable = frozenset()
        unreachable = sorted(all_identities - reachable)
        deleted: List[str] = []
        bytes_freed = 0
        if execute:
            for identity in unreachable:
                freed = _delete_identity(store, identity)
                if freed > 0:
                    deleted.append(identity)
                    bytes_freed += freed
            if deleted:
                _append_log(store.root, deleted)
    preserved = len(all_identities) - len(unreachable)
    return GCReport(
        executed=execute,
        deleted=deleted if execute else list(unreachable),
        preserved=preserved if execute else len(reachable & all_identities),
        bytes_freed=bytes_freed,
        roots_count=len(roots),
    )


def _delete_identity(store: "SymbolStore", identity: str) -> int:
    """Remove both ``.json`` and ``.cbor`` artifacts for an identity.

    Returns the number of bytes freed across both artifacts. An
    identity stored in only one wire form has only one artifact; the
    other path's ``unlink`` returns 0 bytes silently.
    """
    total = 0
    for suffix in (".cbor", ".json"):
        path = store._path_for(identity, suffix)  # noqa: SLF001
        if path.exists():
            try:
                size = path.stat().st_size
                path.unlink()
                total += size
            except OSError:
                # Best-effort; a racing deletion is fine.
                pass
    return total


def _append_log(store_root: Path, deleted: List[str]) -> None:
    """Append deletion records to GC.LOG.

    Format: ISO-8601 timestamp, space, identity. Appends in a single
    open-write-close cycle per run so a crash mid-write affects at most
    one line of the log. The log is not rotated — it is a forensic
    record, and if it grows large that tells you something.

    Opens with ``O_NOFOLLOW`` so a pre-existing symlink at the log
    path causes a clean refusal rather than writing through to an
    attacker-controlled file. Resolves Sable finding GC-1 (2026-05-11).
    The store already defends against symlink writes at the symbol
    path; the log deserves the same treatment.
    """
    log_path = store_root / GC_LOG_FILENAME
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    lines = "".join(f"{now} {identity}\n" for identity in deleted)
    # O_NOFOLLOW refuses to open the final component if it is a symlink.
    # O_APPEND makes our writes atomic (up to PIPE_BUF). O_CREAT allows
    # the first run to create the file.
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
    try:
        fd = os.open(log_path, flags, 0o644)
    except OSError as exc:
        # ELOOP is what you get when O_NOFOLLOW refuses a symlink.
        # Any OSError here indicates tampering or a filesystem issue;
        # we surface it rather than silently skipping the log write.
        raise OSError(
            f"refusing to append GC.LOG at {log_path}: {exc}"
        ) from exc
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(lines)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
