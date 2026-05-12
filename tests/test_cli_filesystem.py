"""Regression tests for CLI filesystem-safety hardening.

Pins the fixes from the 2026-05-11 CLI audit (dispatches/2026-05-11-
cli-audit.md). The CLI's ``_read`` helper previously used
``Path.read_text()`` with no size bound: ``codifide canonical /dev/zero``
would hang indefinitely, and a 50 MiB junk file would be loaded in
full before the parser rejected it.

These tests assert the bound is in place and that the failure is a
clean typed error, not an uncaught hang.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_codifide(argv, timeout=5):
    """Invoke the codifide CLI as a subprocess with a bounded timeout."""
    return subprocess.run(
        [sys.executable, "-m", "codifide", *argv],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=timeout,
    )


class BoundedSourceReadTests(unittest.TestCase):
    """``_read`` refuses to slurp unbounded input."""

    def test_dev_zero_produces_typed_error_not_hang(self) -> None:
        if not os.path.exists("/dev/zero"):
            self.skipTest("/dev/zero not available on this platform")
        # The subprocess must terminate quickly with a clean exit code.
        # Before the fix this hung indefinitely.
        result = _run_codifide(["canonical", "/dev/zero"], timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exceeds", result.stderr)
        self.assertIn("source file", result.stderr)

    def test_large_junk_file_is_refused(self) -> None:
        # 20 MiB is just over the 16 MiB cap; the CLI must refuse
        # without loading the file into memory for the parser.
        with tempfile.NamedTemporaryFile(
            "wb", suffix=".cod", delete=False
        ) as tmp:
            tmp.write(b"a" * (20 * 1024 * 1024))
            path = tmp.name
        try:
            result = _run_codifide(["canonical", path], timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exceeds", result.stderr)
        finally:
            os.unlink(path)

    def test_legitimate_source_files_still_parse(self) -> None:
        # A small file well under the cap must continue to work.
        example = REPO_ROOT / "examples" / "greet.cod"
        self.assertTrue(example.exists())
        result = _run_codifide(["canonical", str(example)], timeout=10)
        self.assertEqual(
            result.returncode,
            0,
            f"greet.cod canonical failed: stderr={result.stderr!r}",
        )
        # Canonical output is JSON.
        self.assertIn('"codifide"', result.stdout)

    def test_non_utf8_source_is_typed_error(self) -> None:
        # Binary junk that fails UTF-8 decoding must surface as a
        # typed ParseError, not UnicodeDecodeError from the host.
        with tempfile.NamedTemporaryFile(
            "wb", suffix=".cod", delete=False
        ) as tmp:
            tmp.write(b"\xff\xfe\x00\x01\x02")
            path = tmp.name
        try:
            result = _run_codifide(["canonical", path], timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not valid UTF-8", result.stderr)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
