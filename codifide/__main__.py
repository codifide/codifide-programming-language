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
        entry = args.entry or _default_entry(module)
        result = run(module, entry, store=store)
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

    p_verify = store_sub.add_parser(
        "verify",
        help="verify a stored module's imports resolve in the store",
    )
    p_verify.add_argument("hash", help="identity of the module to verify")
    p_verify.set_defaults(func=cmd_store_verify)

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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
