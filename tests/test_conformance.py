"""Conformance between the Python reference and the Rust canonical crate.

The point of this test suite is the one that makes Noema a language rather
than a Python library: two independent implementations must agree on the
canonical byte form of every example program, and on the content hash that
derives from it. Both the JSON form (v0.1 primary) and the CBOR form
(v0.2 binary) are checked.

The Rust crate is built on demand; if `cargo` is not available the test is
skipped with a clear reason. When the crate is available, each example is
parsed by Python, emitted as canonical JSON, handed to the Rust binary, and
the Rust round-trip bytes are compared to the Python canonical bytes byte
for byte.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from noema import (
    canonical_bytes,
    canonical_cbor_bytes,
    content_hash,
    content_hash_cbor,
    parse,
    to_canonical,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
RUST_CRATE = REPO_ROOT / "crates" / "noema-canonical"
RUST_BIN = REPO_ROOT / "target" / "release" / "noema-canonical"


def _cargo_available() -> bool:
    return shutil.which("cargo") is not None


def _ensure_rust_binary() -> bool:
    """Build the Rust binary if it does not already exist. Return success."""
    if RUST_BIN.exists():
        return True
    if not _cargo_available():
        return False
    result = subprocess.run(
        ["cargo", "build", "--release", "-p", "noema-canonical"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return result.returncode == 0 and RUST_BIN.exists()


class RustPythonConformance(unittest.TestCase):
    """Byte-level agreement between the two implementations.

    The Python side is the reference parser (Rust does not parse `.nm` in
    v0). Both sides consume canonical JSON and must produce identical
    canonical bytes; that is the tightest surface we can conform on without
    duplicating the parser.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if not _cargo_available():
            raise unittest.SkipTest(
                "cargo not available; Rust conformance skipped"
            )
        if not _ensure_rust_binary():
            raise unittest.SkipTest(
                "Rust binary did not build; conformance skipped"
            )

    def _canonical_json_for(self, src_path: Path) -> dict:
        module = parse(src_path.read_text(encoding="utf-8"))
        return to_canonical(module)

    def test_rust_and_python_agree_on_canonical_bytes(self) -> None:
        for example in sorted(EXAMPLES_DIR.glob("*.nm")):
            with self.subTest(example=example.name):
                module = parse(example.read_text(encoding="utf-8"))
                python_bytes = canonical_bytes(module)

                canonical_json = to_canonical(module)
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".json", delete=False, encoding="utf-8"
                ) as tmp:
                    json.dump(canonical_json, tmp)
                    tmp_path = Path(tmp.name)
                try:
                    rust = subprocess.run(
                        [str(RUST_BIN), "bytes", str(tmp_path)],
                        capture_output=True,
                        check=True,
                    )
                finally:
                    tmp_path.unlink(missing_ok=True)
                rust_bytes = rust.stdout

                # The whole point: byte-for-byte agreement. If this ever
                # diverges, one of the two implementations is wrong and the
                # spec needs to adjudicate.
                self.assertEqual(
                    rust_bytes,
                    python_bytes,
                    f"Rust/Python canonical bytes differ for {example.name}",
                )

    def test_rust_and_python_agree_on_content_hash(self) -> None:
        for example in sorted(EXAMPLES_DIR.glob("*.nm")):
            with self.subTest(example=example.name):
                module = parse(example.read_text(encoding="utf-8"))
                python_hash = content_hash(module)

                canonical_json = to_canonical(module)
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".json", delete=False, encoding="utf-8"
                ) as tmp:
                    json.dump(canonical_json, tmp)
                    tmp_path = Path(tmp.name)
                try:
                    rust = subprocess.run(
                        [str(RUST_BIN), "hash", str(tmp_path)],
                        capture_output=True,
                        check=True,
                        text=True,
                    )
                finally:
                    tmp_path.unlink(missing_ok=True)
                rust_hash = rust.stdout.strip()

                self.assertEqual(
                    rust_hash,
                    python_hash,
                    f"Rust/Python content hash differs for {example.name}",
                )

    def test_rust_and_python_agree_on_canonical_cbor_bytes(self) -> None:
        # CBOR is the v0.2 binary canonical form. Both implementations
        # follow RFC 8949 §4.2 deterministic encoding: shortest head,
        # shortest float, sorted maps. Byte-level agreement is the
        # proof that the determinism rules are implemented the same
        # way on both sides — anything less would defeat the point of
        # having a binary canonical form at all.
        for example in sorted(EXAMPLES_DIR.glob("*.nm")):
            with self.subTest(example=example.name):
                module = parse(example.read_text(encoding="utf-8"))
                python_cbor = canonical_cbor_bytes(module)

                canonical_json = to_canonical(module)
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".json", delete=False, encoding="utf-8"
                ) as tmp:
                    json.dump(canonical_json, tmp)
                    tmp_path = Path(tmp.name)
                try:
                    rust = subprocess.run(
                        [str(RUST_BIN), "bytes-cbor", str(tmp_path)],
                        capture_output=True,
                        check=True,
                    )
                finally:
                    tmp_path.unlink(missing_ok=True)
                rust_cbor = rust.stdout

                self.assertEqual(
                    rust_cbor,
                    python_cbor,
                    f"Rust/Python canonical CBOR bytes differ for "
                    f"{example.name}: "
                    f"py={python_cbor.hex()[:80]}... "
                    f"rs={rust_cbor.hex()[:80]}...",
                )

    def test_rust_and_python_agree_on_cbor_content_hash(self) -> None:
        # CBOR content hash is computed over the canonical CBOR byte
        # form. If the byte form agrees on every example, the hash
        # trivially agrees; asserting it explicitly pins the interface
        # so that a future change to the hash function is caught, not
        # silent.
        for example in sorted(EXAMPLES_DIR.glob("*.nm")):
            with self.subTest(example=example.name):
                module = parse(example.read_text(encoding="utf-8"))
                python_hash = content_hash_cbor(module)

                canonical_json = to_canonical(module)
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".json", delete=False, encoding="utf-8"
                ) as tmp:
                    json.dump(canonical_json, tmp)
                    tmp_path = Path(tmp.name)
                try:
                    rust = subprocess.run(
                        [str(RUST_BIN), "hash-cbor", str(tmp_path)],
                        capture_output=True,
                        check=True,
                        text=True,
                    )
                finally:
                    tmp_path.unlink(missing_ok=True)
                rust_hash = rust.stdout.strip()

                self.assertEqual(
                    rust_hash,
                    python_hash,
                    f"Rust/Python CBOR content hash differs for {example.name}",
                )


if __name__ == "__main__":
    unittest.main()
