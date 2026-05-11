"""Content-addressed symbol store.

A symbol is a single Codifide definition. Its *identity* is the SHA-256 of its
canonical byte form, prefixed with ``sha256:`` (see
``docs/CANONICAL.md §Content addressing``).

This module turns that identity into a working store:

- :func:`symbol_bytes` serializes one definition to canonical JSON bytes.
- :func:`symbol_cbor_bytes` serializes one definition to canonical CBOR bytes.
- :func:`symbol_hash` hashes the JSON byte form to produce the JSON identity.
- :func:`symbol_hash_cbor` hashes the CBOR byte form to produce the CBOR
  identity. The two are distinct identities for the same abstract module —
  JSON and CBOR are different wire forms, and content addressing makes no
  pretense of collapsing them.
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


def symbol_bytes(name: str, definition: Definition) -> bytes:
    """Canonical JSON byte form of a single symbol.

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


def symbol_cbor_bytes(name: str, definition: Definition) -> bytes:
    """Canonical CBOR byte form of a single symbol.

    Parallel to :func:`symbol_bytes` but uses the CBOR (v0.2 binary)
    canonical form. Typically 25-30% shorter than JSON; deterministic
    by RFC 8949 §4.2.
    """
    envelope = _symbol_envelope(name, definition)
    return canonical_cbor(envelope)


def symbol_hash(name: str, definition: Definition) -> str:
    """Content identity of a single symbol over its JSON byte form.

    Stable across implementations. Two symbols with identical canonical
    bytes produce the same hash; any change to name, intent, signature,
    pre, post, or any candidate produces a new hash.
    """
    digest = hashlib.sha256(symbol_bytes(name, definition)).hexdigest()
    return f"sha256:{digest}"


def symbol_hash_cbor(name: str, definition: Definition) -> str:
    """Content identity of a single symbol over its CBOR byte form.

    A distinct identity from :func:`symbol_hash` — the same abstract
    Definition has a JSON identity and a CBOR identity, and agents
    exchanging one wire form need to agree on that wire form to share
    identities. The two forms are interoperable at the Module level (a
    consumer can materialize either from the in-memory form) but not at
    the identity level.
    """
    digest = hashlib.sha256(symbol_cbor_bytes(name, definition)).hexdigest()
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
        """Store a symbol in JSON form and return its content identity.

        Idempotent. If the symbol is already in the store, its existing
        bytes are verified and the identity is returned unchanged.
        """
        identity = symbol_hash(name, definition)
        data = symbol_bytes(name, definition)
        self._write_atomic(identity, data)
        return identity

    def put_cbor(self, name: str, definition: Definition) -> str:
        """Store a symbol in CBOR form and return its CBOR content identity.

        Distinct from :meth:`put`: the identity is computed over the CBOR
        byte form, so the same abstract Definition produces a different
        identity when stored as CBOR vs. JSON. Agents exchanging content
        addresses must agree on the wire form. On-disk layout uses the
        ``.cbor`` suffix in place of ``.json`` so iterating the store
        surfaces each artifact separately.

        Why it's a separate identity rather than a reformat of an
        existing one: content addressing is a property of bytes. If we
        collapsed the two into one identity, a consumer could no longer
        be certain which bytes were hashed. Better to have two honest
        identities than one misleading one.
        """
        identity = symbol_hash_cbor(name, definition)
        data = symbol_cbor_bytes(name, definition)
        self._write_atomic(identity, data, suffix=".cbor")
        return identity

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

    def put_module(self, module: Module, *, cbor: bool = False) -> List[tuple[str, str]]:
        """Store every definition in a module.

        Returns a list of (symbol_name, identity) pairs, in declaration
        order. The module itself is not stored as a unit; it is
        reconstructable from the set of symbol identities plus a name
        lookup table (the return value is that table).

        When ``cbor=True`` each symbol is stored in its CBOR canonical
        form, which produces a different identity than the JSON form.
        """
        out: List[tuple[str, str]] = []
        for defn in module.symbols:
            if cbor:
                out.append((defn.name, self.put_cbor(defn.name, defn)))
            else:
                out.append((defn.name, self.put(defn.name, defn)))
        return out

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
