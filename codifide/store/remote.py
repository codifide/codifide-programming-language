"""Remote symbol store — fetch-and-cache from a Codifide registry.

A ``RemoteStore`` wraps a local ``SymbolStore`` and falls back to a
remote registry on cache miss. The registry is any server that speaks
the Codifide RPC API (``docs/RPC_API.md``), including the public
registry at ``https://codifide.com``.

Trust model: hash-verification is the only trust mechanism. A remote
fetch that returns bytes not matching the requested identity is rejected
with ``IntegrityError`` before the bytes are cached or returned. The
registry cannot forge a symbol without changing its identity.

Usage::

    from codifide.store import SymbolStore
    from codifide.store.remote import RemoteStore

    local = SymbolStore("~/.codifide/store")
    store = RemoteStore(local, registry="https://codifide.com")
    obj = store.get("sha256:<hex>")   # local hit or remote fetch + cache

See ``dispatches/2026-05-14-v3-2-remote-symbols-design.readout.md``
for the design rationale.
"""
from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from typing import Optional

from .symbol_store import IntegrityError, NotFound, StoreError, SymbolStore

# Maximum bytes we will accept from a remote registry for a single symbol.
# Matches the CLI and server caps.
_MAX_REMOTE_BYTES = 16 * 1024 * 1024  # 16 MiB

# Default public registry URL.
DEFAULT_REGISTRY = "https://codifide.com"

# Timeout for remote HTTP requests (seconds).
_REQUEST_TIMEOUT = 30


class RemoteStore:
    """A SymbolStore that falls back to a remote registry on cache miss.

    All reads check the local store first. On a miss, the symbol is
    fetched from the registry, hash-verified, cached locally, and
    returned. Subsequent reads hit the local cache.

    The ``has`` method performs a HEAD request against the registry on
    a local miss — no body is transferred.

    This class exposes the same ``get``, ``has``, and ``get_bytes``
    interface as ``SymbolStore`` so it can be used as a drop-in
    replacement wherever a store is accepted.
    """

    def __init__(
        self,
        local: SymbolStore,
        registry: str = DEFAULT_REGISTRY,
    ) -> None:
        self.local = local
        self.registry = registry.rstrip("/")

    # ------------------------------------------------------------------
    # Public interface (mirrors SymbolStore)
    # ------------------------------------------------------------------

    def has(self, identity: str) -> bool:
        """Return True iff the symbol is in the local cache or the registry."""
        if self.local.has(identity):
            return True
        return self._remote_exists(identity)

    def get(self, identity: str) -> dict:
        """Return the parsed canonical object for an identity.

        Checks local cache first. On miss, fetches from the registry,
        hash-verifies, caches locally, and returns the parsed object.
        """
        try:
            return self.local.get(identity)
        except NotFound:
            pass
        # Fetch, verify, cache.
        data = self._fetch(identity)
        self.local._write_atomic(identity, data, suffix=".cbor")
        return self.local.get(identity)

    def get_bytes(self, identity: str) -> bytes:
        """Return the raw canonical bytes for an identity.

        Checks local cache first. On miss, fetches from the registry,
        hash-verifies, caches locally, and returns the bytes.
        """
        try:
            return self.local.get_bytes(identity)
        except NotFound:
            pass
        data = self._fetch(identity)
        self.local._write_atomic(identity, data, suffix=".cbor")
        return data

    # ------------------------------------------------------------------
    # Delegation — pass through to local store for write operations
    # ------------------------------------------------------------------

    def put(self, name: str, definition) -> str:
        """Store a symbol locally. Does not push to the registry."""
        return self.local.put(name, definition)

    def put_module(self, module, **kwargs):
        """Store every symbol in a module locally."""
        return self.local.put_module(module, **kwargs)

    # ------------------------------------------------------------------
    # Remote operations
    # ------------------------------------------------------------------

    def _symbol_url(self, identity: str) -> str:
        return f"{self.registry}/symbols/{identity}"

    def _remote_exists(self, identity: str) -> bool:
        """HEAD /symbols/<identity> — existence check without body."""
        url = self._symbol_url(identity)
        req = urllib.request.Request(url, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            raise StoreError(
                f"registry HEAD {url} returned HTTP {exc.code}: {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise StoreError(
                f"cannot reach registry {self.registry}: {exc.reason}"
            ) from exc

    def _fetch(self, identity: str) -> bytes:
        """GET /symbols/<identity> — fetch canonical CBOR bytes.

        Hash-verifies the response before returning. Raises
        ``IntegrityError`` if the bytes don't match the identity.
        Raises ``StoreError`` on network or HTTP errors.
        Raises ``NotFound`` on 404.
        """
        url = self._symbol_url(identity)
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/cbor"},
        )
        try:
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
                # Read up to the limit + 1 to detect oversized responses.
                data = resp.read(_MAX_REMOTE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFound(identity) from exc
            raise StoreError(
                f"registry GET {url} returned HTTP {exc.code}: {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise StoreError(
                f"cannot reach registry {self.registry}: {exc.reason}"
            ) from exc

        if len(data) > _MAX_REMOTE_BYTES:
            raise StoreError(
                f"remote symbol {identity} exceeds {_MAX_REMOTE_BYTES} bytes; "
                f"refusing to cache"
            )

        # Hash-verify before caching. This is the trust mechanism: the
        # registry cannot return a different symbol under the same identity
        # without this check detecting it.
        observed = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if observed != identity:
            raise IntegrityError(expected=identity, actual=observed)

        return data
