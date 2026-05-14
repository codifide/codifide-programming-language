"""Codifide RPC API server.

A thin HTTP wrapper over the content-addressed symbol store. Implements
the three endpoints specified in ``docs/RPC_API.md``:

    POST /symbols                    — publish a symbol, get its hash
    GET  /symbols/<identity>         — retrieve a symbol by hash
    GET  /symbols/<identity>/imports — resolve the import graph
    GET  /health                     — liveness check

Start with::

    python3 -m codifide serve [--port 7777] [--store ~/.codifide/store]

The server binds to 127.0.0.1 only. It is not safe to expose over a
network without a reverse proxy with TLS and auth (see docs/RPC_API.md
§Security).

Design decisions:
- http.server.ThreadingHTTPServer — handles concurrent POSTs correctly;
  the store's atomic-write semantics make concurrent writes safe.
- No new dependencies — stdlib only.
- CBOR primary, JSON secondary — matches the store's wire format.
- 16 MiB body limit — same as the CLI's source-file cap.
"""
from __future__ import annotations

import http.server
import json
import re
import threading
from pathlib import Path
from typing import Optional

from .projection.canonical import from_canonical
from .projection.cbor import canonical_cbor
from .projection.cbor_decoder import decode_canonical_cbor
from .store import IntegrityError, NotFound, StoreError, SymbolStore

# Maximum request body the server will read. Matches the CLI's source-file
# cap (dispatches/2026-05-11-cli-audit.md).
_MAX_BODY_BYTES = 16 * 1024 * 1024  # 16 MiB

# Content-type constants.
_CT_CBOR = "application/cbor"
_CT_JSON = "application/json"

# Identity pattern: sha256: + 64 lowercase hex chars.
_IDENTITY_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _json_response(handler: http.server.BaseHTTPRequestHandler,
                   status: int, body: dict) -> None:
    data = json.dumps(body, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", _CT_JSON)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _bytes_response(handler: http.server.BaseHTTPRequestHandler,
                    status: int, data: bytes, content_type: str) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _read_body(handler: http.server.BaseHTTPRequestHandler) -> Optional[bytes]:
    """Read the request body up to _MAX_BODY_BYTES.

    Returns None if Content-Length is invalid.
    Returns the body bytes (possibly truncated to _MAX_BODY_BYTES + 1 so
    the caller can detect oversized bodies).

    When Content-Length exceeds the limit, drains the socket before
    returning so the connection stays clean and the server can send a
    proper 413 response without a broken pipe.
    """
    length_str = handler.headers.get("Content-Length", "")
    if not length_str:
        # No Content-Length — read up to the limit + 1.
        return handler.rfile.read(_MAX_BODY_BYTES + 1)
    try:
        length = int(length_str)
    except ValueError:
        return None
    if length < 0:
        return None
    if length > _MAX_BODY_BYTES:
        # Drain the socket in chunks so the client can receive the 413.
        remaining = length
        chunk = 65536
        while remaining > 0:
            handler.rfile.read(min(chunk, remaining))
            remaining -= chunk
        # Return a sentinel that is exactly one byte over the limit.
        return b"\x00" * (_MAX_BODY_BYTES + 1)
    return handler.rfile.read(length)


class _Handler(http.server.BaseHTTPRequestHandler):
    """Request handler for the Codifide RPC API."""

    # The store is injected by the server factory below.
    store: SymbolStore

    def log_message(self, fmt: str, *args) -> None:  # type: ignore[override]
        # Suppress the default per-request log to stderr; the server
        # prints a startup message and that's enough for a local tool.
        pass

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/")

        if path == "/health":
            _json_response(self, 200, {"status": "ok"})
            return

        # GET /symbols/<identity>
        m = re.match(r"^/symbols/(sha256:[0-9a-f]{64})$", path)
        if m:
            self._get_symbol(m.group(1))
            return

        # GET /symbols/<identity>/imports
        m = re.match(r"^/symbols/(sha256:[0-9a-f]{64})/imports$", path)
        if m:
            self._get_imports(m.group(1))
            return

        # Malformed identity in /symbols/...
        if path.startswith("/symbols/"):
            _json_response(self, 400, {
                "error": "invalid_identity",
                "detail": "identity must be sha256: followed by 64 lowercase hex chars",
            })
            return

        _json_response(self, 404, {"error": "not_found", "detail": f"no route: {path}"})

    def do_POST(self) -> None:
        path = self.path.split("?")[0].rstrip("/")

        if path == "/symbols":
            self._post_symbol()
            return

        _json_response(self, 404, {"error": "not_found", "detail": f"no route: {path}"})

    def do_HEAD(self) -> None:
        # HEAD /symbols/<identity> — existence check without body.
        path = self.path.split("?")[0].rstrip("/")
        m = re.match(r"^/symbols/(sha256:[0-9a-f]{64})$", path)
        if m:
            identity = m.group(1)
            if self.store.has(identity):
                self.send_response(200)
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _post_symbol(self) -> None:
        """POST /symbols — publish a symbol, return its identity."""
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip()

        body = _read_body(self)
        if body is None:
            _json_response(self, 413, {
                "error": "body_too_large",
                "detail": f"body exceeds {_MAX_BODY_BYTES} bytes",
            })
            return
        if len(body) > _MAX_BODY_BYTES:
            _json_response(self, 413, {
                "error": "body_too_large",
                "detail": f"body exceeds {_MAX_BODY_BYTES} bytes",
            })
            return

        # Decode body to a canonical dict.
        try:
            if content_type == _CT_CBOR:
                obj = decode_canonical_cbor(body)
            else:
                # Default to JSON for any other content type.
                obj = json.loads(body)
        except (ValueError, json.JSONDecodeError) as exc:
            _json_response(self, 400, {
                "error": "invalid_body",
                "detail": f"cannot decode body: {exc}",
            })
            return

        # Reconstruct the Module.
        try:
            if not isinstance(obj, dict):
                raise ValueError(f"expected a JSON object, got {type(obj).__name__}")
            module = from_canonical(obj)
        except (ValueError, KeyError, TypeError) as exc:
            _json_response(self, 400, {
                "error": "invalid_body",
                "detail": f"not a valid canonical module: {exc}",
            })
            return

        # Exactly one symbol required.
        if len(module.symbols) == 0:
            _json_response(self, 400, {
                "error": "invalid_body",
                "detail": "module contains no symbols; publish symbols individually",
            })
            return
        if len(module.symbols) > 1:
            _json_response(self, 400, {
                "error": "multi_symbol",
                "detail": (
                    f"module contains {len(module.symbols)} symbols; "
                    "publish symbols individually (one per POST)"
                ),
            })
            return

        defn = module.symbols[0]

        # Store and return identity.
        try:
            identity = self.store.put(defn.name, defn)
        except IntegrityError as exc:
            _json_response(self, 500, {
                "error": "store_error",
                "detail": str(exc),
            })
            return
        except StoreError as exc:
            _json_response(self, 500, {
                "error": "store_error",
                "detail": str(exc),
            })
            return

        _json_response(self, 200, {"identity": identity, "name": defn.name})

    def _get_symbol(self, identity: str) -> None:
        """GET /symbols/<identity> — retrieve a symbol by hash."""
        accept = self.headers.get("Accept", _CT_CBOR).split(";")[0].strip()
        want_json = accept == _CT_JSON

        try:
            obj = self.store.get(identity)
        except NotFound:
            _json_response(self, 404, {
                "error": "not_found",
                "identity": identity,
            })
            return
        except (IntegrityError, StoreError) as exc:
            _json_response(self, 500, {
                "error": "store_error",
                "detail": str(exc),
            })
            return

        if want_json:
            data = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
            _bytes_response(self, 200, data, _CT_JSON)
        else:
            data = canonical_cbor(obj)
            _bytes_response(self, 200, data, _CT_CBOR)

    def _get_imports(self, identity: str) -> None:
        """GET /symbols/<identity>/imports — resolve the import graph."""
        try:
            obj = self.store.get(identity)
        except NotFound:
            _json_response(self, 404, {
                "error": "not_found",
                "identity": identity,
            })
            return
        except (IntegrityError, StoreError) as exc:
            _json_response(self, 500, {
                "error": "store_error",
                "detail": str(exc),
            })
            return

        try:
            module = from_canonical(obj)
        except (ValueError, KeyError, TypeError) as exc:
            _json_response(self, 500, {
                "error": "store_error",
                "detail": f"stored object is not a valid module: {exc}",
            })
            return

        imports_out = []
        missing = []
        for local_name, target_id in module.imports:
            present = self.store.has(target_id)
            imports_out.append({
                "name": local_name,
                "identity": target_id,
                "present": present,
            })
            if not present:
                missing.append(target_id)

        _json_response(self, 200, {
            "identity": identity,
            "imports": imports_out,
            "missing": missing,
        })


def make_server(store: SymbolStore, host: str = "127.0.0.1", port: int = 7777):
    """Create a ThreadingHTTPServer bound to host:port, backed by store.

    Uses ThreadingHTTPServer so concurrent POSTs are handled correctly.
    The store's atomic-write semantics make concurrent writes safe.

    A 30-second socket timeout is set to prevent slow-loris style
    resource exhaustion (AUD-RPC-02).
    """
    # Inject the store into the handler class via a subclass so each
    # request handler can access it without a global.
    handler_class = type("_BoundHandler", (_Handler,), {"store": store})

    server = http.server.ThreadingHTTPServer((host, port), handler_class)
    # 30-second timeout per connection. Prevents a slow client from
    # holding a thread indefinitely.
    server.socket.settimeout(30)
    return server


def serve(store: SymbolStore, host: str = "127.0.0.1", port: int = 7777) -> None:
    """Start the server and block until interrupted."""
    server = make_server(store, host, port)
    print(f"codifide serve: listening on http://{host}:{port}")
    print(f"  store: {store.root}")
    print(f"  endpoints: POST /symbols  GET /symbols/<hash>  GET /symbols/<hash>/imports")
    print(f"  stop: Ctrl-C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\ncodifide serve: stopped")
    finally:
        server.server_close()
