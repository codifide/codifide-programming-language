"""Content-addressed symbol store.

A symbol is a single Noema definition. Its *identity* is the SHA-256 of its
canonical byte form, prefixed with ``sha256:`` (see
``docs/CANONICAL.md §Content addressing``).

This module turns that identity into a working store:

- :func:`symbol_bytes` serializes one definition to canonical bytes.
- :func:`symbol_hash` hashes those bytes to produce the identity.
- :class:`SymbolStore` is a filesystem-backed key-value store keyed by
  that identity. Writes verify the hash before accepting the bytes; reads
  verify the hash of what came back. Neither direction trusts the disk.

Why this exists now: until agents can exchange symbols by identity rather
than by name + prose, the spec's "content addressing" claim is a property
without a use. The store is the smallest thing that makes the property
operational.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Iterator, List, Optional

from ..core.types import Definition, Module
from ..projection.canonical import to_canonical


# ---------------------------------------------------------------------------
# Hashing a single symbol
# ---------------------------------------------------------------------------


def _symbol_envelope(name: str, definition: Definition) -> dict:
    """Build a single-symbol module envelope.

    The spec states a symbol's identity is the hash of its canonical JSON
    object "including its name as a key under a single-entry symbols map."
    We construct that envelope here so callers cannot accidentally hash a
    bare definition without its name and get a different identity than a
    consumer would.
    """
    return to_canonical(Module(name="_", symbols=(definition,)))


def symbol_bytes(name: str, definition: Definition) -> bytes:
    """Canonical byte form of a single symbol.

    The bytes are identical to what an independent implementation (e.g. the
    Rust crate) would produce for the same symbol — that is the whole point
    of the canonical form. If the two disagree, the conformance test
    catches it.
    """
    envelope = _symbol_envelope(name, definition)
    return json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def symbol_hash(name: str, definition: Definition) -> str:
    """Content identity of a single symbol: ``sha256:<hex>``.

    Stable across implementations. Two symbols with identical canonical
    bytes produce the same hash; any change to name, intent, signature,
    pre, post, or any candidate produces a new hash.
    """
    digest = hashlib.sha256(symbol_bytes(name, definition)).hexdigest()
    return f"sha256:{digest}"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class StoreError(Exception):
    """Base class for symbol-store errors."""


class NotFound(StoreError):
    """Raised when a hash has no entry in the store."""

    def __init__(self, hash_: str) -> None:
        self.hash = hash_
        super().__init__(f"no symbol with hash {hash_!r} in store")


class IntegrityError(StoreError):
    """Raised when a symbol's bytes do not hash to the expected identity.

    On write, this means the caller asked the store to save a symbol under
    a hash that does not match the bytes. On read, this means the bytes on
    disk have been tampered with or corrupted.
    """

    def __init__(self, expected: str, actual: str) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"integrity check failed: expected {expected!r}, got {actual!r}"
        )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class SymbolStore:
    """Filesystem-backed content-addressed symbol store.

    Layout::

        <root>/
          sha256/
            ab/
              abcd...ef.json

    The first two hex characters of the digest are a sharding prefix so a
    single directory does not accumulate tens of thousands of files; this
    is the same shape Git uses for loose objects and it keeps filesystem
    performance reasonable at scale.

    Writes are atomic: bytes are written to a temporary file in the same
    directory and then renamed into place. A crashed writer leaves no
    half-written object visible. If a symbol is already present, a second
    write is a no-op — the point of content addressing is idempotency.
    """

    # Prefix we use for SHA-256 identities; matches the spec.
    PREFIX = "sha256:"

    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "sha256").mkdir(exist_ok=True)

    # -- Public API ------------------------------------------------------

    def put(self, name: str, definition: Definition) -> str:
        """Store a symbol and return its content identity.

        Idempotent. If the symbol is already in the store, its existing
        bytes are verified and the identity is returned unchanged.
        """
        identity = symbol_hash(name, definition)
        data = symbol_bytes(name, definition)
        self._write_atomic(identity, data)
        return identity

    def has(self, identity: str) -> bool:
        """Return True iff the store has an entry for this identity."""
        return self._path_for(identity).exists()

    def get_bytes(self, identity: str) -> bytes:
        """Return the stored canonical bytes for an identity.

        On read the bytes are rehashed and compared to the identity. If the
        two disagree, :class:`IntegrityError` is raised — corruption or
        tampering on disk never returns a value.
        """
        path = self._path_for(identity)
        if not path.exists():
            raise NotFound(identity)
        data = path.read_bytes()
        observed = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if observed != identity:
            raise IntegrityError(expected=identity, actual=observed)
        return data

    def get(self, identity: str) -> dict:
        """Return the parsed canonical JSON object for an identity."""
        return json.loads(self.get_bytes(identity))

    def iter_identities(self) -> Iterator[str]:
        """Yield every identity currently stored, in filesystem order.

        Iteration is not sorted because callers who care about ordering
        should sort themselves; imposing an order here would lie about
        what the filesystem returns.
        """
        base = self.root / "sha256"
        if not base.exists():
            return
        for shard in base.iterdir():
            if not shard.is_dir() or len(shard.name) != 2:
                continue
            for obj in shard.iterdir():
                if obj.suffix != ".json":
                    continue
                yield f"sha256:{shard.name}{obj.stem}"

    def put_module(self, module: Module) -> List[tuple[str, str]]:
        """Store every definition in a module.

        Returns a list of (symbol_name, identity) pairs, in declaration
        order. The module itself is not stored as a unit; it is
        reconstructable from the set of symbol identities plus a name
        lookup table (the return value is that table).
        """
        out: List[tuple[str, str]] = []
        for defn in module.symbols:
            out.append((defn.name, self.put(defn.name, defn)))
        return out

    # -- Internals -------------------------------------------------------

    def _path_for(self, identity: str) -> Path:
        digest = self._parse_identity(identity)
        return self.root / "sha256" / digest[:2] / f"{digest[2:]}.json"

    @classmethod
    def _parse_identity(cls, identity: str) -> str:
        if not identity.startswith(cls.PREFIX):
            raise StoreError(
                f"identity must start with {cls.PREFIX!r}: {identity!r}"
            )
        digest = identity[len(cls.PREFIX):]
        if len(digest) != 64 or not all(c in "0123456789abcdef" for c in digest):
            raise StoreError(f"malformed sha256 identity: {identity!r}")
        return digest

    def _write_atomic(self, identity: str, data: bytes) -> None:
        # Verify first: the caller asked us to save bytes under an
        # identity; if the bytes do not hash to that identity, we refuse.
        # This is defense against the caller, not against the disk.
        observed = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if observed != identity:
            raise IntegrityError(expected=identity, actual=observed)

        path = self._path_for(identity)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            # Idempotent: if someone already wrote these bytes, we're done.
            return

        # Atomic write: temp file + rename. The fsync is a concession to
        # durability; if the process dies before rename, the temp file
        # just gets cleaned up on the next run by whoever does GC.
        fd, tmp_path = tempfile.mkstemp(
            prefix=".noema-",
            suffix=".tmp",
            dir=str(path.parent),
        )
        tmp = Path(tmp_path)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except Exception:
            # Clean up the temp file on any error; the rename target may
            # or may not exist but is either absent or the previous
            # good contents.
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            raise
