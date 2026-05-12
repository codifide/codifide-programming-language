"""Content-addressed symbol store.

See :mod:`codifide.store.symbol_store` for the implementation.

The primary byte and hash functions (``symbol_bytes``, ``symbol_hash``)
operate on the CBOR canonical form as of 2026-05-11. The ``_cbor`` and
``_json`` variants are explicit-naming aliases preserved so callers can
make their wire form intent obvious at the call site.
"""
from .symbol_store import (
    IntegrityError,
    NotFound,
    StoreError,
    SymbolStore,
    symbol_bytes,           # primary = CBOR
    symbol_bytes_json,      # legacy JSON form, explicitly named
    symbol_cbor_bytes,      # alias of symbol_bytes for explicit callers
    symbol_hash,            # primary = CBOR hash
    symbol_hash_cbor,       # alias of symbol_hash for explicit callers
    symbol_hash_json,       # legacy JSON hash, for callers that need it
)

__all__ = [
    "IntegrityError",
    "NotFound",
    "StoreError",
    "SymbolStore",
    "symbol_bytes",
    "symbol_bytes_json",
    "symbol_cbor_bytes",
    "symbol_hash",
    "symbol_hash_cbor",
    "symbol_hash_json",
]
