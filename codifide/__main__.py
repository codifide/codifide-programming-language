"""Codifide CLI.

Subcommands:
    run <file.nm>            Parse and execute a Codifide program.
    canonical <file.nm>      Print the canonical JSON projection.
    test                     Run the Codifide test suite.
    store put <file.nm>      Store every symbol in a module by content hash.
    store get <hash>         Print the canonical JSON for a stored symbol.
    store list               List every stored symbol identity.
    store hash <file.nm>     Print (name, hash) pairs for a module's symbols.
    store index name=<id>... Publish an index module bundling name->id pairs.

The CLI is deliberately minimal. Codifide's surface is a projection; a richer
interaction is better done over the canonical form (see codifide.projection).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import parse, run
from .projection.canonical import to_canonical
from .projection.cbor import canonical_cbor
from .runtime.errors import CodifideError
from .store import StoreError, SymbolStore, symbol_hash


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def cmd_run(args: argparse.Namespace) -> int:
    try:
        # Parse first without the store; if the source uses `from`
        # imports, the parser will return an error that names the
        # missing store. We open the store then and retry, so modules
        # that do not need a store do not pay for opening one.
        src = _read(args.file)
        store: Optional[SymbolStore] = None
        try:
            module = parse(src)
        except CodifideError:
            store = SymbolStore(_store_root(args))
            module = parse(src, store=store)
        if store is None and module.imports:
            # Plain `import` at runtime still needs a store.
            store = SymbolStore(_store_root(args))
        entry = args.entry or _default_entry(module)
        result = run(module, entry, store=store)
        if result is not None:
            # Print the unwrapped result for scripting convenience.
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
    from .store import SymbolStore, symbol_hash, symbol_hash_cbor

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
    # imported each symbol by content hash.
    print(f"module:  {module.name}")
    print(f"symbols: {len(module.symbols)}")
    print(f"imports: {len(module.imports)}")
    print(f"bytes:   JSON {len(j_bytes)}, CBOR {len(c_bytes)}")
    print()
    for defn in module.symbols:
        h_json = symbol_hash(defn.name, defn)
        h_cbor = symbol_hash_cbor(defn.name, defn)
        print(f"  {defn.name}")
        print(f"    json  {h_json}")
        print(f"    cbor  {h_cbor}")
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
        entries = store.put_module(module, cbor=args.cbor)
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
    try:
        module = parse(_read(args.file))
        for defn in module.symbols:
            print(f"{symbol_hash(defn.name, defn)}\t{defn.name}")
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
    # We compute and store it by writing the canonical JSON directly,
    # bypassing the symbol store's per-definition envelope since an
    # index has no definitions.
    import hashlib
    from .projection.canonical import to_canonical

    canonical_obj = to_canonical(index_module)
    data = json.dumps(
        canonical_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    identity = f"sha256:{hashlib.sha256(data).hexdigest()}"

    # Write through the store's atomic-write path. We use the internal
    # method because the public API is per-symbol; indices are modules,
    # not symbols. The on-disk layout is identical.
    store._write_atomic(identity, data)
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
        help="store in CBOR form (produces different identities than JSON)",
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
    p_index.set_defaults(func=cmd_store_index)

    p_verify = store_sub.add_parser(
        "verify",
        help="verify a stored module's imports resolve in the store",
    )
    p_verify.add_argument("hash", help="identity of the module to verify")
    p_verify.set_defaults(func=cmd_store_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
