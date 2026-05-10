"""Noema CLI.

Subcommands:
    run <file.nm>       Parse and execute a Noema program.
    canonical <file.nm> Print the canonical JSON projection.
    test                Run the Noema test suite.

The CLI is deliberately minimal. Noema's surface is a projection; a richer
interaction is better done over the canonical form (see noema.projection).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import parse, run
from .projection.canonical import to_canonical
from .runtime.errors import NoemaError


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def cmd_run(args: argparse.Namespace) -> int:
    try:
        module = parse(_read(args.file))
        entry = args.entry or _default_entry(module)
        result = run(module, entry)
        if result is not None:
            # Print the unwrapped result for scripting convenience.
            print(result)
        return 0
    except NoemaError as e:
        print(f"noema: {e}", file=sys.stderr)
        return 1


def cmd_canonical(args: argparse.Namespace) -> int:
    try:
        module = parse(_read(args.file))
        print(json.dumps(to_canonical(module), indent=2, sort_keys=True))
        return 0
    except NoemaError as e:
        print(f"noema: {e}", file=sys.stderr)
        return 1


def cmd_test(args: argparse.Namespace) -> int:
    # Defer to unittest discovery so new tests are picked up automatically.
    import unittest
    tests_dir = Path(__file__).resolve().parent.parent / "tests"
    loader = unittest.TestLoader()
    suite = loader.discover(str(tests_dir))
    runner = unittest.TextTestRunner(verbosity=2)
    return 0 if runner.run(suite).wasSuccessful() else 1


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
    parser = argparse.ArgumentParser(prog="noema")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="execute a Noema program")
    p_run.add_argument("file")
    p_run.add_argument("--entry", help="entry definition (default: main or sole definition)")
    p_run.set_defaults(func=cmd_run)

    p_can = sub.add_parser("canonical", help="print canonical JSON")
    p_can.add_argument("file")
    p_can.set_defaults(func=cmd_canonical)

    p_test = sub.add_parser("test", help="run the test suite")
    p_test.set_defaults(func=cmd_test)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
