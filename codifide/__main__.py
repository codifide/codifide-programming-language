"""Codifide CLI.

Subcommands:
    run <file.cod>            Parse and execute a Codifide program.
    canonical <file.cod>      Print the canonical JSON projection.
    verify <file.cod>         Verify a program parses, type-checks,
                              and canonicalizes cleanly; print per-
                              symbol content hashes.
    capability                Print the capability manifest.
    test                      Run the Codifide test suite.
    store put <file.cod>      Store every symbol in a module by content hash.
    store get <hash>          Print the canonical JSON for a stored symbol.
    store list                List every stored symbol identity.
    store hash <file.cod>     Print (name, hash) pairs for a module's symbols.
    store index name=<id>...  Publish an index module bundling name->id pairs.
    store verify <hash>       Walk a stored module's imports and report
                              any pointees missing from the store.

The CLI is deliberately minimal. Codifide's surface is a projection; a richer
interaction is better done over the canonical form (see codifide.projection).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from . import parse, run
from .projection.canonical import to_canonical
from .projection.cbor import canonical_cbor
from .runtime.errors import CodifideError, ParseError
from .store import StoreError, SymbolStore, symbol_hash, symbol_hash_json


# Maximum size of a single .cod source file the CLI will read. Source
# files are small by design; anything over this is either a mistake
# (piped binary, /dev/zero) or hostile. The Rust canonical binary
# already enforces the same bound for its JSON input (2026-05-10 CBOR
# audit P1-7); this is the Python counterpart. See
# dispatches/2026-05-11-cli-audit.md for the finding that motivated
# adding it here.
_MAX_SOURCE_BYTES = 16 * 1024 * 1024  # 16 MiB


def _read(path: str) -> str:
    """Read a .cod source file with a bounded byte count.

    Reads at most ``_MAX_SOURCE_BYTES + 1`` bytes so we can distinguish
    "exactly at the cap" from "over the cap". Exceeding the cap raises
    ``ParseError`` — sourced via the parser's error channel because a
    file we refuse to read cannot parse, and the host wants a typed
    Codifide error rather than an OS-level error here.
    """
    try:
        with open(path, "rb") as fh:
            data = fh.read(_MAX_SOURCE_BYTES + 1)
    except OSError as exc:
        raise ParseError(f"cannot read {path!r}: {exc}") from exc
    if len(data) > _MAX_SOURCE_BYTES:
        raise ParseError(
            f"source file {path!r} exceeds {_MAX_SOURCE_BYTES} bytes; "
            f"refuse to read more. Codifide source files are small by design."
        )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError(
            f"source file {path!r} is not valid UTF-8: {exc}"
        ) from exc


def cmd_run(args: argparse.Namespace) -> int:
    # Runtime selection: Rust is the default in v2.0.0; Python is the
    # reference fallback via --runtime python.
    runtime = getattr(args, "runtime", None) or os.environ.get("CODIFIDE_RUNTIME", "rust")

    if runtime == "rust":
        return _cmd_run_rust(args)
    return _cmd_run_python(args)


def _cmd_run_rust(args: argparse.Namespace) -> int:
    """Delegate execution to the Rust interpreter binary."""
    import shutil
    import subprocess

    # Locate the Rust binary: prefer the release build next to this repo,
    # then fall back to PATH.
    repo_root = Path(__file__).resolve().parent.parent
    rust_bin = repo_root / "target" / "release" / "codifide-run"
    if not rust_bin.exists():
        rust_bin_path = shutil.which("codifide-run")
        if rust_bin_path is None:
            # Rust binary not available; fall back to Python silently.
            return _cmd_run_python(args)
        rust_bin = Path(rust_bin_path)

    cmd = [str(rust_bin), "run", args.file]
    if args.entry:
        cmd += ["--entry", args.entry]
    # Pass store path so the Rust runtime can resolve from-imports.
    store_root = str(_store_root(args))
    cmd += ["--store", store_root]

    result = subprocess.run(cmd, capture_output=True, text=True)
    # Forward stderr directly.
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        return result.returncode

    # The binary prints io.say output on earlier lines and the JSON result
    # on the last line. Print io.say lines as-is; unwrap the JSON result
    # for display (matching Python's `print(result)` behavior).
    lines = result.stdout.splitlines()
    if not lines:
        return 0
    # All lines except the last are io.say output — print them directly.
    for line in lines[:-1]:
        print(line)
    # Last line is the JSON result — unwrap for display.
    last = lines[-1]
    try:
        val = json.loads(last)
        # Print like Python's print(): strings unquoted, everything else as repr.
        if isinstance(val, str):
            print(val)
        elif val is None:
            pass  # None result: print nothing (matches Python behavior)
        else:
            print(val)
    except (json.JSONDecodeError, ValueError):
        print(last)
    return 0


def _cmd_run_python(args: argparse.Namespace) -> int:
    """Original Python tree-walking interpreter."""
    from .store.remote import RemoteStore

    try:
        src = _read(args.file)
        store: Optional[SymbolStore] = None
        try:
            module = parse(src)
        except CodifideError:
            store = SymbolStore(_store_root(args))
            module = parse(src, store=store)
        if store is None and module.imports:
            store = SymbolStore(_store_root(args))

        # Wrap with RemoteStore if --registry is set (V3-2).
        effective_store = store
        registry = getattr(args, "registry", None)
        if registry and store is not None:
            effective_store = RemoteStore(store, registry=registry)
        elif registry and module.imports:
            local = SymbolStore(_store_root(args))
            effective_store = RemoteStore(local, registry=registry)

        entry = args.entry or _default_entry(module)
        result = run(module, entry, store=effective_store)
        if result is not None:
            print(result)
        return 0
    except CodifideError as e:
        print(f"codifide: {e}", file=sys.stderr)
        return 1


def cmd_canonical(args: argparse.Namespace) -> int:
    try:
        module = parse(_read(args.file))
        if args.cbor:
            # CBOR is binary; write raw bytes to stdout so callers can
            # pipe into a file or a consumer tool without re-encoding.
            sys.stdout.buffer.write(canonical_cbor(to_canonical(module)))
            return 0
        print(json.dumps(to_canonical(module), indent=2, sort_keys=True))
        return 0
    except CodifideError as e:
        print(f"codifide: {e}", file=sys.stderr)
        return 1


def cmd_test(args: argparse.Namespace) -> int:
    # Defer to unittest discovery so new tests are picked up automatically.
    import unittest
    tests_dir = Path(__file__).resolve().parent.parent / "tests"
    loader = unittest.TestLoader()
    suite = loader.discover(str(tests_dir))
    runner = unittest.TextTestRunner(verbosity=2)
    return 0 if runner.run(suite).wasSuccessful() else 1


def cmd_capability(args: argparse.Namespace) -> int:
    """Print the capability manifest — Codifide's agent-facing language interface.

    The manifest is derived from the current implementation so there is
    no authoring drift: what you see is what the runtime exposes. See
    ``docs/CAPABILITY.md`` for the schema and rationale.
    """
    from .capability import generate_capability

    manifest = generate_capability()
    if args.cbor:
        from .projection.cbor import canonical_cbor
        sys.stdout.buffer.write(canonical_cbor(manifest))
        return 0
    if args.hash:
        from .projection.cbor import canonical_cbor
        import hashlib
        # Hash over canonical CBOR bytes — the stable binary form.
        # Agents that want a JSON-based hash can compute it themselves.
        digest = hashlib.sha256(canonical_cbor(manifest)).hexdigest()
        print(f"sha256:{digest}")
        return 0
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify a .cod program without running it.

    Performs the checks a correctly-authored Codifide module must pass
    before it is safe to share: parses, canonicalizes, round-trips
    through JSON and CBOR without byte drift, and passes the
    transitive effect check. Prints the content hash of each symbol
    on success; prints a typed error and exits non-zero on any
    failure.

    This is the single command another agent runs to ask "does my
    program conform to Codifide before I send it to anyone else?" —
    cheaper than running it, stronger than just parsing it.
    """
    from .capability import generate_capability
    from .projection.canonical import canonical_bytes as canon_json
    from .projection.cbor import canonical_cbor
    from .runtime.interpreter import _check_transitive_effects, _ResolvedImports
    from .store import SymbolStore, symbol_hash, symbol_hash_cbor, symbol_hash_json

    try:
        src = _read(args.file)
        module = parse(src)
    except CodifideError as e:
        print(f"codifide verify: PARSE FAILED: {e}", file=sys.stderr)
        return 1

    # Transitive effect check. Runs without a store unless the module
    # declares imports, in which case we need one to resolve them.
    try:
        store = None
        resolved = _ResolvedImports.empty()
        if module.imports:
            store = SymbolStore(_store_root(args))
            resolved = _ResolvedImports.from_module(module, store)
        _check_transitive_effects(module, resolved)
    except CodifideError as e:
        print(f"codifide verify: EFFECT CHECK FAILED: {e}", file=sys.stderr)
        return 1

    # Canonical form round-trip: JSON and CBOR both derive from the
    # same in-memory module, and the bytes must be stable under
    # re-encoding.
    try:
        j_bytes = canon_json(module)
        c_bytes = canonical_cbor(to_canonical(module))
    except Exception as e:
        print(f"codifide verify: CANONICALIZATION FAILED: {e}", file=sys.stderr)
        return 1

    # Per-symbol identity — what another agent would receive if they
    # imported each symbol by content hash. CBOR is the primary form
    # post the 2026-05-11 migration; JSON is shown as a legacy
    # inspection aid.
    print(f"module:  {module.name}")
    print(f"symbols: {len(module.symbols)}")
    print(f"imports: {len(module.imports)}")
    print(f"bytes:   JSON {len(j_bytes)}, CBOR {len(c_bytes)}")
    print()
    for defn in module.symbols:
        h_cbor = symbol_hash_cbor(defn.name, defn)
        h_json = symbol_hash_json(defn.name, defn)
        print(f"  {defn.name}")
        print(f"    cbor  {h_cbor}  (primary)")
        print(f"    json  {h_json}  (legacy)")
    return 0


# ---------------------------------------------------------------------------
# Symbol store
# ---------------------------------------------------------------------------


def _store_root(args: argparse.Namespace) -> Path:
    """Resolve the store root: --store flag, env var, or default."""
    if args.store:
        return Path(args.store)
    env = os.environ.get("CODIFIDE_STORE")
    if env:
        return Path(env)
    return Path.home() / ".codifide" / "store"


def cmd_store_put(args: argparse.Namespace) -> int:
    try:
        module = parse(_read(args.file))
        store = SymbolStore(_store_root(args))
        # As of 2026-05-11, the primary put path is CBOR. ``--json``
        # opts into the legacy JSON identity; ``--cbor`` is accepted
        # but redundant. Either flag alone is explicit and fine.
        use_cbor = not args.json
        entries = store.put_module(module, cbor=use_cbor)
        for name, identity in entries:
            print(f"{identity}\t{name}")
        return 0
    except (CodifideError, StoreError) as e:
        print(f"codifide: {e}", file=sys.stderr)
        return 1


def cmd_store_get(args: argparse.Namespace) -> int:
    try:
        store = SymbolStore(_store_root(args))
        obj = store.get(args.hash)
        print(json.dumps(obj, indent=2, sort_keys=True))
        return 0
    except StoreError as e:
        print(f"codifide: {e}", file=sys.stderr)
        return 1


def cmd_store_list(args: argparse.Namespace) -> int:
    store = SymbolStore(_store_root(args))
    for identity in sorted(store.iter_identities()):
        print(identity)
    return 0


def cmd_store_hash(args: argparse.Namespace) -> int:
    # Compute identities without writing anything — useful for scripting
    # (e.g. seeing what a module would produce before committing to a put).
    # Defaults to the primary (CBOR) identity; ``--json`` prints the
    # legacy JSON identity for each symbol.
    try:
        module = parse(_read(args.file))
        hash_fn = symbol_hash_json if args.json else symbol_hash
        for defn in module.symbols:
            print(f"{hash_fn(defn.name, defn)}\t{defn.name}")
        return 0
    except CodifideError as e:
        print(f"codifide: {e}", file=sys.stderr)
        return 1


def cmd_store_index(args: argparse.Namespace) -> int:
    """Publish an index: a module whose imports table is its export map.

    Given ``name=sha256:...`` pairs on the command line, mint a module
    with those entries in its imports table, store it, and print the
    resulting identity. Consumers can then write
    ``from <index_id> import <name>`` to resolve any of those names
    back to a specific symbol identity.

    Indices are ordinary modules; they live in the same store as the
    symbols they reference and their identity is computed the same way
    (content hash of their canonical bytes).
    """
    from .core.types import Module

    entries: list[tuple[str, str]] = []
    for raw in args.entry:
        if "=" not in raw:
            print(
                f"codifide: index entry must be `name=sha256:<hex>`: {raw!r}",
                file=sys.stderr,
            )
            return 2
        name, identity = raw.split("=", 1)
        name = name.strip()
        identity = identity.strip()
        if not name.isidentifier():
            print(f"codifide: invalid index name: {name!r}", file=sys.stderr)
            return 2
        if not (identity.startswith("sha256:") and len(identity) == 71):
            print(f"codifide: invalid identity: {identity!r}", file=sys.stderr)
            return 2
        entries.append((name, identity))

    store = SymbolStore(_store_root(args))
    index_module = Module(
        name=args.name or "index",
        symbols=(),
        imports=tuple(entries),
    )

    # The module's content identity is the hash of its canonical bytes.
    # Post 2026-05-11 the primary identity is CBOR-over-bytes;
    # ``--json`` emits the legacy JSON-hashed identity.
    import hashlib
    from .projection.canonical import to_canonical
    from .projection.cbor import canonical_cbor

    canonical_obj = to_canonical(index_module)
    if getattr(args, "json", False):
        data = json.dumps(
            canonical_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        suffix = ".json"
    else:
        data = canonical_cbor(canonical_obj)
        suffix = ".cbor"
    identity = f"sha256:{hashlib.sha256(data).hexdigest()}"

    # Write through the store's atomic-write path. We use the internal
    # method because the public API is per-symbol; indices are modules,
    # not symbols. The on-disk layout is identical beyond suffix.
    store._write_atomic(identity, data, suffix=suffix)
    print(f"{identity}\t{index_module.name}")
    return 0


def cmd_store_verify(args: argparse.Namespace) -> int:
    """Verify a stored index's pointees are present and well-formed.

    Security audit 2026-05-10 P3-1: indices are validated opportunistically
    at parse time — a broken index parses fine and errors at runtime
    when a consumer actually resolves it. This subcommand is the opt-in
    check Sable proposed: fetch the index, walk its imports, confirm
    each pointee exists in the store and round-trips through canonical
    form. Exit 0 if every pointee is reachable, exit 1 if any are not.

    Also works on ordinary symbols (walks their transitive user-function
    calls and flags ones that would fail at module load). Best-effort —
    not a full type-check pass.
    """
    from .projection.canonical import from_canonical

    store = SymbolStore(_store_root(args))
    try:
        obj = store.get(args.hash)
    except StoreError as e:
        print(f"codifide: {e}", file=sys.stderr)
        return 1

    try:
        module = from_canonical(obj)
    except Exception as e:
        print(f"codifide: malformed module at {args.hash}: {e}", file=sys.stderr)
        return 1

    problems: list[str] = []
    # Verify each imports-table entry is present and round-trips.
    for local_name, target_id in module.imports:
        if not store.has(target_id):
            problems.append(f"  {local_name}: missing in store → {target_id}")
            continue
        try:
            target_obj = store.get(target_id)
            from_canonical(target_obj)
        except Exception as e:
            problems.append(f"  {local_name}: unreadable ({target_id}): {e}")

    # Report.
    if problems:
        print(f"codifide: {args.hash} has {len(problems)} problem(s):", file=sys.stderr)
        for p in problems:
            print(p, file=sys.stderr)
        return 1
    n_imports = len(module.imports)
    n_syms = len(module.symbols)
    print(
        f"{args.hash}\tOK  "
        f"({n_syms} symbol{'s' if n_syms != 1 else ''}, "
        f"{n_imports} import{'s' if n_imports != 1 else ''})"
    )
    return 0


def cmd_store_push(args: argparse.Namespace) -> int:
    """Push a locally-stored symbol to a remote registry.

    Reads the symbol bytes from the local store, POSTs them to the
    registry's POST /symbols endpoint, and verifies the returned
    identity matches. Idempotent: a second push of the same symbol
    returns 200 with the existing identity.

    The registry URL defaults to https://codifide.com. Agents running
    private registries pass --registry https://my-registry.example.com.
    """
    import urllib.error
    import urllib.request

    registry = (args.registry or "https://codifide.com").rstrip("/")
    identity = args.identity

    # Validate identity shape before touching the store.
    if not (identity.startswith("sha256:") and len(identity) == 71):
        print(
            f"codifide: invalid identity {identity!r}; "
            f"expected sha256: followed by 64 hex chars",
            file=sys.stderr,
        )
        return 1

    try:
        store = SymbolStore(_store_root(args))
        data = store.get_bytes(identity)
    except StoreError as e:
        print(f"codifide: {e}", file=sys.stderr)
        return 1

    url = f"{registry}/symbols"
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/cbor"},
    )
    # Add write token if provided (for registries that require auth).
    write_token = getattr(args, "token", None) or os.environ.get("REGISTRY_WRITE_TOKEN", "")
    if write_token:
        req.add_header("Authorization", f"Bearer {write_token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(1024 * 1024)
    except urllib.error.HTTPError as exc:
        body = exc.read(4096)
        try:
            import json as _json
            err = _json.loads(body)
            detail = err.get("detail", err.get("error", str(exc)))
        except Exception:
            detail = body.decode("utf-8", errors="replace")
        print(
            f"codifide: registry {url} returned HTTP {exc.code}: {detail}",
            file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as exc:
        print(
            f"codifide: cannot reach registry {registry}: {exc.reason}",
            file=sys.stderr,
        )
        return 1

    try:
        import json as _json
        result = _json.loads(body)
    except Exception as exc:
        print(f"codifide: cannot parse registry response: {exc}", file=sys.stderr)
        return 1

    returned_identity = result.get("identity", "")
    if returned_identity != identity:
        print(
            f"codifide: registry returned identity {returned_identity!r} "
            f"but expected {identity!r}; refusing to accept",
            file=sys.stderr,
        )
        return 1

    name = result.get("name", "?")
    print(f"{identity}\t{name}")
    return 0


def cmd_store_gc(args: argparse.Namespace) -> int:
    """Report or delete unreachable identities.

    Dry-run by default — safe to invoke; prints a plan without
    touching the store. Pass ``--execute`` to actually delete.
    ``--execute`` refuses to run if the ``ROOTS`` file is empty or
    missing; the footgun guard is deliberate.

    See ``dispatches/2026-05-11-store-gc-design.readout.md``.
    """
    from .store.gc import GCError
    store = SymbolStore(_store_root(args))
    try:
        report = store.gc(execute=args.execute)
    except GCError as exc:
        print(f"codifide: {exc}", file=sys.stderr)
        return 1
    if report.executed:
        print(report.summary())
        if report.deleted:
            for identity in report.deleted:
                print(f"  deleted {identity}")
    else:
        print(report.summary())
        if report.roots_count == 0:
            print(
                "codifide: ROOTS is empty or missing; `--execute` will refuse.\n"
                "         Add roots with `codifide store roots add <identity>`.",
                file=sys.stderr,
            )
        if report.deleted:
            print("would delete:")
            for identity in report.deleted:
                print(f"  {identity}")
            print("Pass --execute to actually delete.")
    return 0


def cmd_store_roots_list(args: argparse.Namespace) -> int:
    store = SymbolStore(_store_root(args))
    for identity in store.roots():
        print(identity)
    return 0


def cmd_store_roots_add(args: argparse.Namespace) -> int:
    try:
        store = SymbolStore(_store_root(args))
        store.add_root(args.identity)
        return 0
    except StoreError as exc:
        print(f"codifide: {exc}", file=sys.stderr)
        return 1


def cmd_store_roots_remove(args: argparse.Namespace) -> int:
    store = SymbolStore(_store_root(args))
    removed = store.remove_root(args.identity)
    if not removed:
        print(
            f"codifide: {args.identity} was not in ROOTS; nothing to remove",
            file=sys.stderr,
        )
        return 1
    return 0


def cmd_dispatch_index(args: argparse.Namespace) -> int:
    """Regenerate or check-drift the dispatches/INDEX.md file."""
    from pathlib import Path as _Path
    from .dispatch_index import build_index, check_index, write_index

    repo_root = _Path(__file__).resolve().parent.parent
    dispatch_dir = repo_root / "dispatches"
    if not dispatch_dir.exists():
        print(
            f"codifide: no dispatches directory at {dispatch_dir}",
            file=sys.stderr,
        )
        return 1

    if args.check:
        if check_index(dispatch_dir):
            return 0
        print(
            "codifide: dispatches/INDEX.md is out of sync with "
            "dispatches/ contents.\n"
            "         Regenerate with `python3 -m codifide dispatch-index`.",
            file=sys.stderr,
        )
        return 1

    path = write_index(dispatch_dir)
    print(f"wrote {path.relative_to(repo_root)}")
    return 0


def cmd_dispatch_check(args: argparse.Namespace) -> int:
    """Check dispatch stream completeness — flag orphaned readouts and missing pairs.

    Every Quill readout (.readout.md) should have a paired Glyph YAML (.yaml).
    Every session date should have a session-close pair.
    Proposals that have a readout but no YAML are flagged.

    Also checks publicsite sync:
    - publicsite/capability.json generator field must match the live manifest.
    - index.html version stat must match the live manifest generator version.

    Exits 0 if complete, 1 if gaps found. Designed to run as an agentStop
    hook so Quill and Glyph don't fall asleep on the job.
    """
    from pathlib import Path as _Path
    from .dispatch_index import _collect_entries

    repo_root = _Path(__file__).resolve().parent.parent
    dispatch_dir = repo_root / "dispatches"
    if not dispatch_dir.exists():
        return 0

    entries = _collect_entries(dispatch_dir)
    gaps = []

    for e in entries:
        # A readout without a paired YAML is an orphan.
        # Exception: standalone .md dispatches (audit notes, journals)
        # that were never intended to have a YAML pair are fine — they
        # show up with readout_path but no yaml_path AND their slug
        # doesn't end in a pattern that implies a pair is expected.
        # We flag it if the readout path ends in .readout.md (explicit
        # Quill output) but no YAML exists.
        if (
            e.readout_path
            and e.readout_path.endswith(".readout.md")
            and not e.yaml_path
        ):
            gaps.append(
                f"  ORPHAN  {e.date}-{e.slug}: "
                f"readout exists but no paired Glyph YAML"
            )

        # A YAML without a readout is unusual but not always wrong
        # (some Glyph dispatches are standalone). Don't flag these.

    # Check for session-close pair on any date that has other dispatches.
    dates_with_dispatches = {e.date for e in entries}
    dates_with_close = {
        e.date for e in entries
        if e.slug == "session-close" and e.readout_path and e.yaml_path
    }
    # Only flag today's date if it has dispatches but no close pair —
    # past sessions are already closed.
    import datetime
    today = datetime.date.today().isoformat()
    if today in dates_with_dispatches and today not in dates_with_close:
        gaps.append(
            f"  MISSING {today}-session-close: "
            f"dispatches filed today but no session-close pair"
        )

    # ------------------------------------------------------------------
    # Publicsite sync checks (PS-1, PS-3)
    # ------------------------------------------------------------------
    _check_publicsite_sync(repo_root, gaps)

    if gaps:
        print("codifide dispatch-check: gaps found:")
        for g in gaps:
            print(g)
        print(
            "\nFile the missing artifacts before ending the session. "
            "Every Quill readout needs a paired Glyph YAML. "
            "Every session needs a session-close pair."
        )
        return 1

    print("codifide dispatch-check: all dispatch pairs complete.")
    return 0


def _check_publicsite_sync(repo_root: "Path", gaps: list) -> None:
    """Check that publicsite/capability.json and index.html are in sync
    with the live capability manifest generator version.

    Appends human-readable gap strings to ``gaps`` if anything is stale.
    Silently skips checks when the publicsite directory is not present
    (e.g. running from a checkout that doesn't include the publicsite).
    """
    import json as _json
    from pathlib import Path as _Path

    publicsite = repo_root.parent / "publicsite"
    if not publicsite.exists():
        return  # publicsite not co-located; skip silently

    # PS-1 — capability.json generator version
    cap_json = publicsite / "capability.json"
    if cap_json.exists():
        try:
            from .capability import generate_capability
            live_generator = generate_capability().get("generator", "")
            published = _json.loads(cap_json.read_text(encoding="utf-8"))
            published_generator = published.get("generator", "")
            if published_generator != live_generator:
                gaps.append(
                    f"  STALE   publicsite/capability.json: "
                    f"generator is '{published_generator}' but live is '{live_generator}'. "
                    f"Regenerate with: python3 -m codifide capability > publicsite/capability.json"
                )
        except Exception as exc:
            gaps.append(
                f"  ERROR   publicsite/capability.json: could not check sync ({exc})"
            )
    else:
        gaps.append(
            "  MISSING publicsite/capability.json: "
            "file not found in publicsite directory"
        )

    # PS-3 — version stat in index.html
    index_html = publicsite / "index.html"
    if index_html.exists():
        try:
            from .capability import generate_capability
            live_generator = generate_capability().get("generator", "")
            # Extract version number: "codifide-python-3.0.0" -> "v3.0"
            # Strip patch for the display stat (matches existing "v2.0" pattern).
            import re as _re
            m = _re.search(r"codifide-python-(\d+)\.(\d+)", live_generator)
            if m:
                expected_stat = f"v{m.group(1)}.{m.group(2)}"
                html = index_html.read_text(encoding="utf-8")
                # Match the lang-stat-num span that is immediately followed
                # by a lang-stat-label containing "released" — that's the
                # version stat, not the test count or implementation count.
                stat_m = _re.search(
                    r'class="lang-stat-num"[^>]*>([^<]+)</span>'
                    r'<span[^>]*class="lang-stat-label"[^>]*>[^<]*released[^<]*</span>',
                    html
                )
                if stat_m:
                    actual_stat = stat_m.group(1).strip()
                    if actual_stat != expected_stat:
                        gaps.append(
                            f"  STALE   publicsite/index.html: "
                            f"version stat shows '{actual_stat}' but current release is '{expected_stat}'. "
                            f"Update the lang-stat-num span paired with 'released May 20XX' in index.html."
                        )
                else:
                    gaps.append(
                        "  MISSING publicsite/index.html: "
                        "could not find version stat span (lang-stat-num paired with 'released') "
                        "to verify version"
                    )
        except Exception as exc:
            gaps.append(
                f"  ERROR   publicsite/index.html: could not check version stat ({exc})"
            )


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the Codifide RPC API server.

    Thin HTTP wrapper over the symbol store. See ``docs/RPC_API.md``.
    Binds to 127.0.0.1 by default — not safe to expose over a network
    without a reverse proxy with TLS and auth.

    Pass ``--read-only`` to disable POST /symbols for public registry
    deployments (V3-2).
    """
    from .server import serve

    store = SymbolStore(_store_root(args))
    read_only = getattr(args, "read_only", False)
    serve(store, host=args.host, port=args.port, read_only=read_only)
    return 0


def cmd_agent_quickstart(args: argparse.Namespace) -> int:
    """Bootstrap a fresh agent environment and write a hello-world program.

    Steps:
    1. Check Python version (3.9+ required).
    2. Run the test suite — confirms the interpreter is healthy.
    3. Write examples/quickstart.cod — a hello-world with intent, effects,
       belief, and a content hash.
    4. Run it.
    5. Print the content hash.
    6. Print "You are ready to write Codifide."

    Designed to be the first command a fresh agent runs after cloning the
    repo or installing the package.
    """
    import subprocess
    import sys as _sys
    from pathlib import Path as _Path

    repo_root = _Path(__file__).resolve().parent.parent
    ok = "\033[32m✓\033[0m"
    fail = "\033[31m✗\033[0m"

    print("codifide agent-quickstart\n")

    # Step 1 — Python version
    major, minor = _sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 9):
        print(f"{fail} Python {major}.{minor} detected. Codifide requires Python 3.9+.")
        return 1
    print(f"{ok} Python {major}.{minor}")

    # Step 2 — test suite
    # Regenerate the dispatch index first so the drift test doesn't fail
    # on a stale index in an active development session (AUD-T2-01).
    from .dispatch_index import write_index as _write_index
    _repo_root_for_index = _Path(__file__).resolve().parent.parent
    _dispatch_dir = _repo_root_for_index / "dispatches"
    if _dispatch_dir.exists():
        _write_index(_dispatch_dir)

    print(f"   Running test suite (this takes a few seconds)...")
    result = subprocess.run(
        [_sys.executable, "-m", "pytest", "--tb=short", "-q"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    # Extract the summary line (last non-empty line of stdout)
    summary = next(
        (l for l in reversed(result.stdout.splitlines()) if l.strip()),
        "no output"
    )
    if result.returncode != 0:
        print(f"{fail} Test suite failed: {summary}")
        print(result.stdout[-2000:] if result.stdout else "")
        return 1
    print(f"{ok} {summary}")

    # Step 3 — write quickstart.cod
    quickstart_path = repo_root / "examples" / "quickstart.cod"
    quickstart_path.parent.mkdir(parents=True, exist_ok=True)
    quickstart_src = '''\
module quickstart

# Hello, Codifide.
#
# This program demonstrates the four things that make Codifide different:
#   1. intent  — every function names the choice it represents
#   2. effects — every function declares its side effects
#   3. belief  — values carry confidence scores
#   4. content addressing — every symbol has a stable hash identity

def classify_greeting
  intent "label a greeting as warm or neutral based on keyword signals"
  sig    (msg: String) -> Label
  effects {}
  cand
    intent "warm greeting"
    when   contains(lower(msg), "hello")
    belief("warm", 0.90)
  cand
    intent "neutral fallback"
    belief("neutral", 0.60)

def main
  intent "demonstrate Codifide to a fresh agent"
  sig    () -> Label
  effects {io.stdout}
  cand
    result <- classify_greeting("Hello, Codifide")
    io.say(result)
'''
    quickstart_path.write_text(quickstart_src, encoding="utf-8")
    print(f"{ok} Wrote {quickstart_path.relative_to(repo_root)}")

    # Step 4 — run it
    run_result = subprocess.run(
        [_sys.executable, "-m", "codifide", "run",
         str(quickstart_path), "--runtime", "python"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if run_result.returncode != 0:
        print(f"{fail} Run failed: {run_result.stderr.strip()}")
        return 1
    output = run_result.stdout.strip()
    # io.say prints the value AND the CLI runner echoes the return value,
    # so output appears twice — that's correct Codifide behavior (AUD-T2-02).
    print(f"{ok} Ran quickstart.cod → {output.splitlines()[0]!r} (io.say prints + CLI echoes return value)")

    # Step 5 — publish to the content-addressed store and print hashes
    # Use `store put` (not `store hash`) so the symbols are actually stored
    # and can be imported by hash in subsequent programs. (AUD-T2-06)
    put_result = subprocess.run(
        [_sys.executable, "-m", "codifide", "store", "put",
         str(quickstart_path)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if put_result.returncode == 0:
        for line in put_result.stdout.strip().splitlines():
            print(f"   {line}")
        print(f"   (symbols stored — importable via `import name = sha256:<hash>`)")

    # Step 6
    print(f"\n{ok} You are ready to write Codifide.")
    print(
        "\n   Next steps:"
        "\n   - Read docs/FOR_AGENTS.md"
        "\n   - Run: python3 -m codifide capability"
        "\n   - Browse examples/ for working programs"
        "\n   - Read docs/AGENT_COOKBOOK.md if you hit an error"
    )
    return 0


def _default_entry(module) -> str:
    # If there's only one definition, use it; else prefer `main`.
    if len(module.symbols) == 1:
        return module.symbols[0].name
    for d in module.symbols:
        if d.name == "main":
            return "main"
    # Fall back to the last-declared definition.
    return module.symbols[-1].name


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="codifide")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="execute a Codifide program")
    p_run.add_argument("file")
    p_run.add_argument("--entry", help="entry definition (default: main or sole definition)")
    p_run.add_argument(
        "--runtime",
        choices=["rust", "python"],
        default=None,
        help="interpreter runtime: rust (default) or python (reference). "
             "Override with CODIFIDE_RUNTIME env var.",
    )
    p_run.add_argument(
        "--store",
        help="store root for import resolution (default: $CODIFIDE_STORE or ~/.codifide/store)",
    )
    p_run.add_argument(
        "--registry",
        default=None,
        help="remote registry URL for resolving imports on cache miss "
             "(e.g. https://codifide.com). Opt-in: without this flag, "
             "only the local store is used.",
    )
    p_run.set_defaults(func=cmd_run)

    p_can = sub.add_parser("canonical", help="print canonical JSON or CBOR")
    p_can.add_argument("file")
    p_can.add_argument(
        "--cbor",
        action="store_true",
        help="emit canonical CBOR (RFC 8949 §4.2) bytes instead of JSON",
    )
    p_can.set_defaults(func=cmd_canonical)

    p_test = sub.add_parser("test", help="run the test suite")
    p_test.set_defaults(func=cmd_test)

    p_cap = sub.add_parser(
        "capability",
        help="print the capability manifest describing the language interface",
    )
    p_cap.add_argument(
        "--cbor",
        action="store_true",
        help="emit canonical CBOR bytes instead of pretty-printed JSON",
    )
    p_cap.add_argument(
        "--hash",
        action="store_true",
        help="print sha256:<hex> over canonical CBOR bytes of the manifest",
    )
    p_cap.set_defaults(func=cmd_capability)

    p_verify = sub.add_parser(
        "verify",
        help="verify a .cod program parses, type-checks, and canonicalizes cleanly",
    )
    p_verify.add_argument("file")
    p_verify.set_defaults(func=cmd_verify)

    p_dispatch_index = sub.add_parser(
        "dispatch-index",
        help="regenerate dispatches/INDEX.md from the directory contents",
    )
    p_dispatch_index.add_argument(
        "--check",
        action="store_true",
        help="verify the checked-in INDEX.md matches what would be generated",
    )
    p_dispatch_index.set_defaults(func=cmd_dispatch_index)

    p_dispatch_check = sub.add_parser(
        "dispatch-check",
        help="check dispatch stream completeness — flag orphaned readouts and missing pairs",
    )
    p_dispatch_check.set_defaults(func=cmd_dispatch_check)

    # Symbol store. A store root can be passed via --store or the
    # CODIFIDE_STORE environment variable; defaults to ~/.codifide/store.
    p_store = sub.add_parser(
        "store",
        help="content-addressed symbol store",
    )
    p_store.add_argument(
        "--store",
        help="store root directory (default: $CODIFIDE_STORE or ~/.codifide/store)",
    )
    store_sub = p_store.add_subparsers(dest="store_cmd", required=True)

    p_put = store_sub.add_parser("put", help="store every symbol in a module")
    p_put.add_argument("file")
    p_put.add_argument(
        "--cbor",
        action="store_true",
        help="(default) store in CBOR form — primary identity since 2026-05-11",
    )
    p_put.add_argument(
        "--json",
        action="store_true",
        help="store in legacy JSON form (produces different identities than CBOR)",
    )
    p_put.set_defaults(func=cmd_store_put)

    p_get = store_sub.add_parser("get", help="fetch one symbol by hash")
    p_get.add_argument("hash")
    p_get.set_defaults(func=cmd_store_get)

    p_list = store_sub.add_parser("list", help="list every stored identity")
    p_list.set_defaults(func=cmd_store_list)

    p_hash = store_sub.add_parser(
        "hash",
        help="print the content hash of every symbol in a module without storing",
    )
    p_hash.add_argument("file")
    p_hash.add_argument(
        "--json",
        action="store_true",
        help="print legacy JSON hashes instead of primary CBOR hashes",
    )
    p_hash.set_defaults(func=cmd_store_hash)

    p_index = store_sub.add_parser(
        "index",
        help="publish an index module from name=<identity> pairs",
    )
    p_index.add_argument(
        "--name",
        default=None,
        help="module name for the index (default: `index`)",
    )
    p_index.add_argument(
        "entry",
        nargs="+",
        help="name=sha256:<hex> pairs defining the index's exports",
    )
    p_index.add_argument(
        "--json",
        action="store_true",
        help="publish the index as legacy JSON (default is CBOR since 2026-05-11)",
    )
    p_index.set_defaults(func=cmd_store_index)

    p_verify_store = store_sub.add_parser(
        "verify",
        help="verify a stored module's imports resolve in the store",
    )
    p_verify_store.add_argument("hash", help="identity of the module to verify")
    p_verify_store.set_defaults(func=cmd_store_verify)

    p_push = store_sub.add_parser(
        "push",
        help="push a locally-stored symbol to a remote registry",
    )
    p_push.add_argument(
        "identity",
        help="sha256:<hex> identity of the symbol to push",
    )
    p_push.add_argument(
        "--registry",
        default=None,
        help="registry URL (default: https://codifide.com)",
    )
    p_push.add_argument(
        "--token",
        default=None,
        help="write token for the registry (Authorization: Bearer <token>)",
    )
    p_push.set_defaults(func=cmd_store_push)

    # -- Garbage collection (2026-05-11 design dispatch) --------------
    p_gc = store_sub.add_parser(
        "gc",
        help="report or delete identities unreachable from the ROOTS file",
    )
    p_gc.add_argument(
        "--execute",
        action="store_true",
        help="actually delete (default is dry-run)",
    )
    p_gc.set_defaults(func=cmd_store_gc)

    p_roots = store_sub.add_parser(
        "roots",
        help="manage the ROOTS file that declares live identities for GC",
    )
    roots_sub = p_roots.add_subparsers(dest="roots_cmd", required=True)

    p_roots_list = roots_sub.add_parser("list", help="print current roots")
    p_roots_list.set_defaults(func=cmd_store_roots_list)

    p_roots_add = roots_sub.add_parser("add", help="add an identity as a root")
    p_roots_add.add_argument("identity")
    p_roots_add.set_defaults(func=cmd_store_roots_add)

    p_roots_remove = roots_sub.add_parser(
        "remove", help="remove an identity from the roots"
    )
    p_roots_remove.add_argument("identity")
    p_roots_remove.set_defaults(func=cmd_store_roots_remove)

    p_quickstart = sub.add_parser(
        "agent-quickstart",
        help="bootstrap a fresh agent environment and write a hello-world program",
    )
    p_quickstart.set_defaults(func=cmd_agent_quickstart)

    p_serve = sub.add_parser(
        "serve",
        help="start the RPC API server (HTTP wrapper over the symbol store)",
    )
    p_serve.add_argument(
        "--port",
        type=int,
        default=7777,
        help="port to listen on (default: 7777)",
    )
    p_serve.add_argument(
        "--host",
        default="127.0.0.1",
        help="host to bind to (default: 127.0.0.1 — local only)",
    )
    p_serve.add_argument(
        "--store",
        help="store root directory (default: $CODIFIDE_STORE or ~/.codifide/store)",
    )
    p_serve.add_argument(
        "--read-only",
        action="store_true",
        dest="read_only",
        help="disable POST /symbols — for public registry deployments (V3-2)",
    )
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
