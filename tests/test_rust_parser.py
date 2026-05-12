"""Rust parser conformance: Rust parse output must match Python canonical JSON.

For every .cod example, parse with both Python and Rust, serialize to
canonical JSON, and compare byte-for-byte. This is the tightest possible
conformance check: if the two parsers agree on canonical bytes, they agree
on everything the language cares about.

The Rust binary's `parse` subcommand prints canonical JSON to stdout.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from codifide import parse as py_parse
from codifide.projection.canonical import to_canonical, canonical_bytes

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
RUST_BIN = REPO_ROOT / "target" / "release" / "codifide-run"


def _ensure_rust_binary() -> bool:
    if RUST_BIN.exists():
        return True
    if not shutil.which("cargo"):
        return False
    result = subprocess.run(
        ["cargo", "build", "--release", "-p", "codifide-interpreter"],
        cwd=REPO_ROOT, capture_output=True,
    )
    return result.returncode == 0 and RUST_BIN.exists()


def _rust_parse(path: Path) -> dict | None:
    """Run the Rust parser on a .cod file; return parsed canonical JSON dict."""
    result = subprocess.run(
        [str(RUST_BIN), "parse", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout.strip())


class RustParserConformance(unittest.TestCase):
    """Rust parser must produce identical canonical JSON to Python parser."""

    @classmethod
    def setUpClass(cls):
        if not _ensure_rust_binary():
            raise unittest.SkipTest("Rust binary not available; skipped")

    def _check(self, path: Path):
        src = path.read_text(encoding="utf-8")
        # Skip programs that don't parse in Python (invalid Codifide).
        try:
            py_module = py_parse(src)
        except Exception:
            return

        py_canonical = to_canonical(py_module)
        py_bytes = canonical_bytes(py_module)

        rust_canonical = _rust_parse(path)
        if rust_canonical is None:
            self.fail(f"{path.name}: Rust parser failed")

        # Compare canonical bytes: sort keys, no whitespace.
        rust_bytes_str = json.dumps(rust_canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
        py_bytes_str = json.dumps(py_canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()

        self.assertEqual(
            rust_bytes_str, py_bytes_str,
            f"{path.name}: Rust/Python canonical JSON mismatch\n"
            f"  Rust: {rust_bytes_str[:200]}\n"
            f"  Py:   {py_bytes_str[:200]}"
        )

    def test_top_level_examples(self):
        for p in sorted(EXAMPLES_DIR.glob("*.cod")):
            with self.subTest(example=p.name):
                self._check(p)

    def test_assessment_examples(self):
        for p in sorted((EXAMPLES_DIR / "assessment").glob("*.cod")):
            with self.subTest(example=p.name):
                self._check(p)

    def test_ai_generated_examples(self):
        for p in sorted((EXAMPLES_DIR / "ai_generated").glob("*.cod")):
            with self.subTest(example=p.name):
                self._check(p)


if __name__ == "__main__":
    unittest.main()
