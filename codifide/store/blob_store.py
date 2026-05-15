"""Vercel Blob-backed symbol store.

A ``BlobStore`` stores and retrieves Codifide symbols using the Vercel Blob
REST API. It exposes the same ``put``, ``get``, ``get_bytes``, and ``has``
interface as ``SymbolStore`` so it can be used as a drop-in replacement
wherever a store is accepted.

**Dependency:** ``vercel_blob`` (pip install vercel_blob). This is the
official Python wrapper for the Vercel Blob REST API. It is listed as an
optional dependency in ``pyproject.toml`` under ``[project.optional-dependencies]
blob``.

**Trust model.** Every read hash-verifies the returned bytes against the
requested identity before returning. A CDN or proxy cannot serve a different
symbol under the same identity without this check detecting it.

**Blob layout.** Each symbol is stored as a blob at the path::

    symbols/<first-2-hex>/<remaining-62-hex>.cbor

This mirrors the filesystem store's sharded layout, making the two backends
interchangeable and the blob store browseable.

**Public access.** Symbol blobs are stored with ``access='public'``. The
content is content-addressed — the hash is the identity, so there is no
secret in the content. Public access means agents can resolve symbols
directly from the CDN URL without going through the serverless function,
which is faster and cheaper.

**Write protection.** The ``put`` method requires ``BLOB_READ_WRITE_TOKEN``.
The serverless function that exposes ``POST /symbols`` should be
write-protected (see ``api/index.py`` in the publicsite repo).

Design decisions are recorded in
``dispatches/2026-05-14-v4-3-vercel-registry-design.readout.md``.
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional

from .symbol_store import (
    IntegrityError,
    NotFound,
    StoreError,
    symbol_cbor_bytes,
    symbol_hash_cbor,
)
from ..core.types import Definition, Module

# Maximum bytes we will accept from a blob read.
_MAX_BLOB_BYTES = 16 * 1024 * 1024  # 16 MiB


def _require_vercel_blob():
    """Import vercel_blob, raising a clear error if not installed."""
    try:
        import vercel_blob  # type: ignore[import]
        return vercel_blob
    except ImportError:
        raise StoreError(
            "BlobStore requires the 'vercel_blob' package. "
            "Install it with: pip install vercel_blob\n"
            "Or install the codifide blob extra: pip install codifide[blob]"
        )


class BlobStore:
    """Vercel Blob-backed content-addressed symbol store.

    Reads and writes symbols to Vercel Blob storage. Exposes the same
    interface as ``SymbolStore`` so it can be used as a drop-in replacement.

    ``token`` defaults to the ``BLOB_READ_WRITE_TOKEN`` environment variable,
    which Vercel sets automatically when a blob store is connected to a project.
    Pass it explicitly for local testing or when running outside Vercel.
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self._token = token or os.environ.get("BLOB_READ_WRITE_TOKEN", "")

    # ------------------------------------------------------------------
    # Public interface (mirrors SymbolStore)
    # ------------------------------------------------------------------

    def put(self, name: str, definition: Definition) -> str:
        """Store a symbol in Vercel Blob and return its content identity.

        Idempotent: if the blob already exists, the existing identity is
        returned without re-uploading.
        """
        if not self._token:
            raise StoreError(
                "BLOB_READ_WRITE_TOKEN is not set. "
                "Set it in your environment or pass token= to BlobStore()."
            )
        identity = symbol_hash_cbor(name, definition)
        data = symbol_cbor_bytes(name, definition)

        # Check existence first — idempotent writes avoid unnecessary uploads.
        if self.has(identity):
            return identity

        vb = _require_vercel_blob()
        pathname = self._pathname(identity)
        try:
            vb.put(
                pathname,
                data,
                options={
                    "access": "public",
                    "token": self._token,
                    "contentType": "application/cbor",
                    "cacheControlMaxAge": 31536000,  # 1 year — immutable
                    "allowOverwrite": False,
                },
            )
        except Exception as exc:
            raise StoreError(f"Vercel Blob put failed for {identity}: {exc}") from exc

        return identity

    def put_module(self, module: Module, *, cbor: bool = True) -> list:
        """Store every definition in a module. Returns (name, identity) pairs."""
        out = []
        for defn in module.symbols:
            out.append((defn.name, self.put(defn.name, defn)))
        return out

    def has(self, identity: str) -> bool:
        """Return True iff the symbol exists in Vercel Blob."""
        vb = _require_vercel_blob()
        pathname = self._pathname(identity)
        try:
            vb.head(pathname, options={"token": self._token} if self._token else {})
            return True
        except Exception as exc:
            # vercel_blob raises BlobNotFoundError (or a class whose name
            # contains "NotFound") when the blob doesn't exist. We check
            # the class name and message to catch both the typed error and
            # any HTTP 404 wrapper. All other exceptions propagate — a
            # network error or auth failure should not silently return False.
            exc_type = type(exc).__name__
            exc_str = str(exc).lower()
            is_not_found = (
                "notfound" in exc_type.lower()
                or "not_found" in exc_type.lower()
                or "404" in exc_str
                or "not found" in exc_str
            )
            if is_not_found:
                return False
            raise StoreError(f"Vercel Blob head failed for {identity}: {exc}") from exc

    def get_bytes(self, identity: str) -> bytes:
        """Return the canonical CBOR bytes for an identity.

        Hash-verifies the returned bytes. Raises ``NotFound`` if the
        symbol is not in the store. Raises ``IntegrityError`` if the
        bytes don't match the identity.
        """
        if not self.has(identity):
            raise NotFound(identity)

        vb = _require_vercel_blob()
        pathname = self._pathname(identity)

        # Public blobs have a stable CDN URL. Fetch via the download URL.
        try:
            result = vb.head(
                pathname,
                options={"token": self._token} if self._token else {},
            )
            download_url = result.get("downloadUrl") or result.get("url")
        except Exception as exc:
            raise StoreError(
                f"Vercel Blob head failed for {identity}: {exc}"
            ) from exc

        if not download_url:
            raise StoreError(f"Vercel Blob returned no URL for {identity}")

        # Fetch the bytes directly from the CDN URL.
        import urllib.request
        import urllib.error
        try:
            with urllib.request.urlopen(download_url, timeout=30) as resp:
                data = resp.read(_MAX_BLOB_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFound(identity) from exc
            raise StoreError(
                f"Vercel Blob download failed HTTP {exc.code} for {identity}"
            ) from exc
        except urllib.error.URLError as exc:
            raise StoreError(
                f"Vercel Blob download network error for {identity}: {exc.reason}"
            ) from exc

        if len(data) > _MAX_BLOB_BYTES:
            raise StoreError(
                f"blob {identity} exceeds {_MAX_BLOB_BYTES} bytes; refusing"
            )

        # Hash-verify before returning.
        observed = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if observed != identity:
            raise IntegrityError(expected=identity, actual=observed)

        return data

    def get(self, identity: str) -> dict:
        """Return the parsed canonical object for an identity."""
        data = self.get_bytes(identity)
        from ..projection.cbor_decoder import decode_canonical_cbor
        try:
            return decode_canonical_cbor(data)
        except ValueError as exc:
            raise StoreError(
                f"cannot decode stored CBOR for {identity}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Blob path helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pathname(identity: str) -> str:
        """Convert a sha256 identity to a blob pathname.

        Layout: symbols/<first-2-hex>/<remaining-62-hex>.cbor
        Mirrors the filesystem store's sharded layout.
        """
        digest = identity[len("sha256:"):]
        return f"symbols/{digest[:2]}/{digest[2:]}.cbor"
