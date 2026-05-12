"""Content-addressed symbol store.

A symbol is a single Codifide definition. Its *identity* is the SHA-256 of its
canonical byte form, prefixed with ``sha256:`` (see
``docs/CANONICAL.md §Content addressing``).

**Primary identity is CBOR as of 2026-05-11.** Before that migration the
primary identity was over canonical JSON bytes; that path is still
available under the ``_json`` suffix for callers that need it, but
``symbol_hash`` / ``symbol_bytes`` / ``SymbolStore.put`` now hash and
store in CBOR form by default. Reasons for the migration are in
``dispatches/2026-05-11-primary-hash-migration-proposal.readout.md``;
the triggering P1 is ``dispatches/2026-05-11-cbor-reaudit.md`` AUD-08.

This module turns that identity into a working store:

- :func:`symbol_bytes` serializes one definition to canonical CBOR bytes
  (the primary form).
- :func:`symbol_bytes_json` serializes one definition to canonical JSON
  bytes (legacy; still used by some tools for human inspection).
- :func:`symbol_hash` hashes the CBOR byte form to produce the primary
  content identity. Under the hood it is identical to
  :func:`symbol_hash_cbor`, which is kept as an explicit alias for
  callers that want the intent-naming of "CBOR identity" to be
  obvious at the call site.
- :func:`symbol_hash_json` hashes the JSON byte form to produce the
  legacy JSON identity. Preserved so pre-migration stored objects are
  still addressable and so second-implementation conformance tests can
  still assert JSON-byte agreement on the safe value subset.
- :class:`SymbolStore` is a filesystem-backed key-value store keyed by
  an identity. Writes verify the hash before accepting the bytes; reads
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
from ..projection.cbor import canonical_cbor


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


def symbol_bytes_json(name: str, definition: Definition) -> bytes:
    """Canonical JSON byte form of a single symbol.

    Legacy — pre-2026-05-11 this was the primary byte form. The JSON
    byte form is still useful for human inspection and for tools that
    cannot consume CBOR. It is **not** used to mint primary content
    identities any more; see :func:`symbol_bytes` for that.

    The bytes are identical to what an independent implementation (e.g.
    the Rust crate) would produce for the same symbol on values that
    round-trip identically through both JSON parsers. For f16-class
    floats the two implementations can disagree on the exact bytes
    (see ``dispatches/2026-05-11-cbor-reaudit.md`` AUD-08); the
    primary-hash migration to CBOR closed this structurally.
    """
    envelope = _symbol_envelope(name, definition)
    return json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def symbol_cbor_bytes(name: str, definition: Definition) -> bytes:
    """Canonical CBOR byte form of a single symbol.

    Parallel to :func:`symbol_bytes_json` but uses the CBOR (v0.2
    binary) canonical form. Typically 25-30% shorter than JSON;
    deterministic by RFC 8949 §4.2.

    This is the canonical wire form for primary identities. An alias
    :func:`symbol_bytes` points here.
    """
    envelope = _symbol_envelope(name, definition)
    return canonical_cbor(envelope)


# The primary byte function is CBOR.
symbol_bytes = symbol_cbor_bytes


def symbol_hash_json(name: str, definition: Definition) -> str:
    """Content identity of a single symbol over its JSON byte form.

    Legacy — pre-2026-05-11 this was the primary identity. Preserved
    for callers that need to reproduce a historical hash or verify
    agreement with an older Codifide client. The primary identity function
    is :func:`symbol_hash`, which hashes over CBOR.
    """
    digest = hashlib.sha256(symbol_bytes_json(name, definition)).hexdigest()
    return f"sha256:{digest}"


def symbol_hash_cbor(name: str, definition: Definition) -> str:
    """Content identity of a single symbol over its CBOR byte form.

    Primary identity function as of 2026-05-11. :func:`symbol_hash` is
    an alias; call either interchangeably. Naming this one explicitly
    ``_cbor`` makes the wire form obvious at the call site for code
    that also references :func:`symbol_hash_json`.
    """
    digest = hashlib.sha256(symbol_cbor_bytes(name, definition)).hexdigest()
    return f"sha256:{digest}"


# The primary hash function is CBOR.
symbol_hash = symbol_hash_cbor


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
        """Store a symbol in CBOR form and return its content identity.

        As of 2026-05-11, the primary put path writes CBOR bytes and
        produces a CBOR-over-bytes identity. Callers who specifically
        want the legacy JSON path should call :meth:`put_json`.

        Idempotent. If the symbol is already in the store, its existing
        bytes are verified and the identity is returned unchanged.
        """
        identity = symbol_hash_cbor(name, definition)
        data = symbol_cbor_bytes(name, definition)
        self._write_atomic(identity, data, suffix=".cbor")
        return identity

    def put_json(self, name: str, definition: Definition) -> str:
        """Store a symbol in JSON form and return its JSON content identity.

        Legacy path. Distinct identity from :meth:`put`. Useful when
        interoperating with a pre-migration store or when producing
        output a consumer can inspect by eye.
        """
        identity = symbol_hash_json(name, definition)
        data = symbol_bytes_json(name, definition)
        self._write_atomic(identity, data, suffix=".json")
        return identity

    # Alias preserved so callers that pre-date the migration keep working.
    # ``put_cbor`` is exactly what ``put`` does now; keeping the alias means
    # downstream code that explicitly spelled out ``put_cbor`` is not broken.
    put_cbor = put

    def has(self, identity: str) -> bool:
        """Return True iff the store has an entry for this identity.

        An identity may be stored in JSON (`.json`) or CBOR (`.cbor`)
        form; either presence satisfies this predicate.
        """
        return self._path_for(identity, ".json").exists() or self._path_for(
            identity, ".cbor"
        ).exists()

    def get_bytes(self, identity: str) -> bytes:
        """Return the stored canonical bytes for an identity.

        Accepts either wire form. The returned bytes are always the
        stored form (JSON bytes if stored as JSON, CBOR bytes if stored
        as CBOR). On read the bytes are rehashed and compared to the
        identity. If the two disagree, :class:`IntegrityError` is raised
        — corruption or tampering on disk never returns a value.
        """
        # Try JSON first (v0.1 default), fall back to CBOR.
        for suffix in (".json", ".cbor"):
            path = self._path_for(identity, suffix)
            if path.exists():
                data = path.read_bytes()
                observed = f"sha256:{hashlib.sha256(data).hexdigest()}"
                if observed != identity:
                    raise IntegrityError(expected=identity, actual=observed)
                return data
        raise NotFound(identity)

    def get(self, identity: str) -> dict:
        """Return the parsed canonical object (JSON-compatible) for an identity.

        Decodes according to the wire form the bytes were stored under,
        not a guess based on the leading byte. Security audit P1-6
        (CBOR audit, 2026-05-10) caught that the previous byte-sniffing
        dispatch leaked ``UnicodeDecodeError`` from ``json.loads`` when
        CBOR bytes happened to start with ``0x7B``. Routing by suffix
        honors the producer's intent and keeps decoder errors inside
        the typed-error discipline.
        """
        # Find which suffix actually holds the bytes.
        json_path = self._path_for(identity, ".json")
        cbor_path = self._path_for(identity, ".cbor")
        if json_path.exists():
            data = self.get_bytes(identity)  # hash-verifies
            try:
                return json.loads(data)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                # Translate any decode failure into a typed store error.
                raise StoreError(
                    f"cannot decode stored JSON for {identity}: {exc}"
                ) from exc
        if cbor_path.exists():
            data = self.get_bytes(identity)  # hash-verifies
            from ..projection.cbor_decoder import decode_canonical_cbor
            try:
                return decode_canonical_cbor(data)
            except ValueError as exc:
                raise StoreError(
                    f"cannot decode stored CBOR for {identity}: {exc}"
                ) from exc
        raise NotFound(identity)

    def iter_identities(self) -> Iterator[str]:
        """Yield every identity currently stored, in filesystem order.

        Iteration is not sorted because callers who care about ordering
        should sort themselves; imposing an order here would lie about
        what the filesystem returns. Surfaces both JSON and CBOR artifacts
        — each is a distinct identity.
        """
        base = self.root / "sha256"
        if not base.exists():
            return
        for shard in base.iterdir():
            if not shard.is_dir() or len(shard.name) != 2:
                continue
            for obj in shard.iterdir():
                if obj.suffix not in (".json", ".cbor"):
                    continue
                yield f"sha256:{shard.name}{obj.stem}"

    def put_module(self, module: Module, *, cbor: bool = True) -> List[tuple[str, str]]:
        """Store every definition in a module.

        Returns a list of (symbol_name, identity) pairs, in declaration
        order. The module itself is not stored as a unit; it is
        reconstructable from the set of symbol identities plus a name
        lookup table (the return value is that table).

        ``cbor`` defaults to ``True`` (the primary path as of the
        2026-05-11 hash migration). Pass ``cbor=False`` to store in
        legacy JSON form; the returned identities will then be
        JSON-hashed, not CBOR-hashed.
        """
        out: List[tuple[str, str]] = []
        for defn in module.symbols:
            if cbor:
                out.append((defn.name, self.put(defn.name, defn)))
            else:
                out.append((defn.name, self.put_json(defn.name, defn)))
        return out

    # -- Garbage collection ---------------------------------------------

    def gc(self, *, execute: bool = False) -> "GCReport":
        """Run garbage collection against this store.

        See :mod:`codifide.store.gc` for the design. Dry-run by default;
        pass ``execute=True`` to actually delete unreachable objects.
        Requires a non-empty ``ROOTS`` file at the store root when
        executing (see :class:`GCError`).
        """
        from .gc import gc as _gc
        return _gc(self, execute=execute)

    def add_root(self, identity: str) -> None:
        """Add an identity to the store's ROOTS file.

        Idempotent: adding a root that is already present is a no-op.
        Validates identity shape — the ROOTS file is not the place to
        discover your hash format was wrong.
        """
        self._parse_identity(identity)  # raises StoreError on shape issues
        from .gc import read_roots, write_roots
        current = read_roots(self.root)
        if identity in current:
            return
        write_roots(self.root, current + [identity])

    def remove_root(self, identity: str) -> bool:
        """Remove an identity from the store's ROOTS file.

        Returns ``True`` if the identity was present and removed,
        ``False`` if it wasn't in the roots to begin with.
        """
        from .gc import read_roots, write_roots
        current = read_roots(self.root)
        if identity not in current:
            return False
        write_roots(self.root, [r for r in current if r != identity])
        return True

    def roots(self) -> List[str]:
        """Return the current list of declared root identities."""
        from .gc import read_roots
        return read_roots(self.root)

    # -- Internals -------------------------------------------------------

    def _path_for(self, identity: str, suffix: str = ".json") -> Path:
        digest = self._parse_identity(identity)
        return self.root / "sha256" / digest[:2] / f"{digest[2:]}{suffix}"

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

    def _write_atomic(self, identity: str, data: bytes, suffix: str = ".json") -> None:
        # Verify first: the caller asked us to save bytes under an
        # identity; if the bytes do not hash to that identity, we refuse.
        # This is defense against the caller, not against the disk.
        observed = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if observed != identity:
            raise IntegrityError(expected=identity, actual=observed)

        path = self._path_for(identity, suffix)
        # Security audit P1-5 (2026-05-10 CBOR audit): the shard
        # directory or the target file may be a symlink pointing
        # outside the store, in which case a naive write would leak
        # legitimate bytes into attacker-controlled territory.
        #
        # Defense in two layers:
        #
        # 1. Containment check. Resolve the parent path and refuse if
        #    it escapes ``self.root``. Catches the typical case where
        #    an attacker has already planted a symlink at
        #    ``<root>/sha256/<XX>`` pointing outside the store.
        #
        # 2. O_NOFOLLOW on the final target open. The TOCTOU window
        #    between the containment check and the rename-into-place
        #    is closed by asking the kernel to refuse any final-
        #    component symlink at the target path. An attacker who
        #    races us to plant a symlink at the exact target after
        #    the containment check still loses: ``os.replace`` into a
        #    pre-existing symlink target would follow; our O_NOFOLLOW
        #    + O_EXCL on the tempfile stage, followed by a rename onto
        #    an expected-absent target, closes it cleanly.
        try:
            resolved_parent = path.parent.resolve(strict=False)
            resolved_root = self.root.resolve(strict=False)
        except OSError as exc:
            raise StoreError(
                f"cannot resolve store path for {identity}: {exc}"
            ) from exc
        root_parts = resolved_root.parts
        parent_parts = resolved_parent.parts
        if (
            len(parent_parts) < len(root_parts)
            or parent_parts[: len(root_parts)] != root_parts
        ):
            raise StoreError(
                f"refusing to write outside store root: "
                f"{resolved_parent} is not within {resolved_root}. "
                f"This usually means a symlink was planted inside the "
                f"store's shard directory."
            )

        # Also refuse if the shard directory itself is a symlink, even
        # if resolve succeeded (it might resolve to a parent that is
        # under root but be reached through a symlink hop).
        if path.parent.exists() and path.parent.is_symlink():
            raise StoreError(
                f"refusing to traverse symlinked shard directory: "
                f"{path.parent}. This indicates a planted symlink; "
                f"remove it before retrying."
            )

        path.parent.mkdir(parents=True, exist_ok=True)

        # Also refuse if the target itself already exists as a symlink.
        # ``Path.exists()`` follows symlinks; use ``is_symlink`` to
        # detect the dangling-or-redirecting case.
        if path.is_symlink():
            raise StoreError(
                f"refusing to overwrite symlink at {path}. "
                f"A symlink at a store object path indicates tampering."
            )

        if path.exists():
            # Idempotent: if someone already wrote these bytes, we're done.
            return

        # Atomic write: temp file + rename. The fsync is a concession to
        # durability; if the process dies before rename, the temp file
        # just gets cleaned up on the next run by whoever does GC.
        fd, tmp_path = tempfile.mkstemp(
            prefix=".codifide-",
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
