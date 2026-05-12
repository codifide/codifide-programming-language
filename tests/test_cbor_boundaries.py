"""Numeric-boundary CBOR conformance between Python and Rust.

Today's conformance test (``tests/test_conformance.py``) exercises
Python-vs-Rust byte agreement on every ``.cod`` example. The examples
happen to cover a narrow slice of numeric values. This suite covers
the boundaries the encoders have to agree on regardless of what any
example program uses.

Scope is narrower than originally planned. Running the fixture during
implementation uncovered a real cross-implementation limitation:
``serde_json``'s float parser and Python's ``json`` parser can
disagree by one ULP on the same decimal text for some values (notably
f16 subnormals and the f32 extremum). When they disagree on the
parsed double, they will produce different canonical CBOR bytes.
That is a real finding, not a test bug, and is filed as Sable
audit finding AUD-2026-05-11-04 in ``dispatches/2026-05-11-cli-
audit.md`` with severity P2. See ``dispatches/2026-05-11-cbor-
numeric-boundaries.md`` for the full analysis.

This suite tests what the conformance claim actually is:

- **Integer head transitions agree.** Every integer that fits in an
  i64 must produce the same CBOR head on both sides, regardless of
  boundary size.
- **Signed zero agrees.** +0.0 and -0.0 encode to distinct and
  correct canonical bytes.
- **NaN and infinity are refused.** Both sides must refuse them;
  this suite asserts the Python half.
- **Half-precision agreement for values that round-trip through
  both JSON parsers.** A subset of f16 patterns whose decimal
  representation is unambiguous for both parsers (specifically,
  those with short exact decimal forms) must agree.

The exhaustive f16 fixture is preserved as a *diagnostic*
(not a pass/fail test) which can be run manually to measure the
decimal-parsing disagreement rate.
"""
from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Iterable

from codifide.core.types import (
    Candidate,
    Definition,
    Lit,
    Module,
    Signature,
)
from codifide.projection.canonical import to_canonical
from codifide.projection.cbor import canonical_cbor


REPO_ROOT = Path(__file__).resolve().parent.parent
RUST_BIN = REPO_ROOT / "target" / "release" / "codifide-canonical"


def _cargo_available() -> bool:
    return shutil.which("cargo") is not None


def _ensure_rust_binary() -> bool:
    if RUST_BIN.exists():
        return True
    if not _cargo_available():
        return False
    result = subprocess.run(
        ["cargo", "build", "--release", "-p", "codifide-canonical"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return result.returncode == 0 and RUST_BIN.exists()


def _rust_cbor_for(doc) -> bytes:
    """Write ``doc`` as JSON, invoke the Rust binary, return CBOR bytes.

    Legacy input path — the Rust binary parses JSON text, which means
    it goes through ``serde_json`` and inherits that library's
    decimal-parser rules. Use :func:`_rust_cbor_for_via_cbor_input` for
    the modern path that bypasses JSON text entirely.
    """
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(doc, tmp, allow_nan=False)
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            [str(RUST_BIN), "bytes-cbor", str(tmp_path)],
            capture_output=True,
            check=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    return result.stdout


def _rust_cbor_for_via_cbor_input(doc) -> bytes:
    """Write ``doc`` as canonical CBOR, invoke Rust via CBOR-input path.

    Produces the same canonical-CBOR round-trip as
    :func:`_rust_cbor_for` but with no JSON-text intermediate. Closes
    AUD-2026-05-11-08's residual surface: Python emits CBOR bytes,
    Rust decodes with its strict canonical-CBOR decoder, re-encodes,
    writes back. No decimal parser sits on either side of the wire.
    """
    with tempfile.NamedTemporaryFile(
        "wb", suffix=".cbor", delete=False
    ) as tmp:
        tmp.write(canonical_cbor(doc))
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            [str(RUST_BIN), "bytes-cbor-in", str(tmp_path)],
            capture_output=True,
            check=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    return result.stdout


def _wrap_in_module_shape(leaf) -> dict:
    """Build a minimal canonical module whose only expression is ``leaf``.

    Both sides generate the canonical shape through their own
    round-trip. Using ``to_canonical`` on the Python side guarantees
    we never drift from the canonical shape the conformance test
    pins.
    """
    module = Module(
        name="bdry",
        symbols=(
            Definition(
                name="n",
                intent="boundary fixture",
                signature=Signature(),
                pre=(),
                post=(),
                candidates=(
                    Candidate(
                        body=Lit(leaf, type="Number"),
                        intent="default",
                        guard=None,
                    ),
                ),
            ),
        ),
        imports=(),
    )
    return to_canonical(module)


# ---------------------------------------------------------------------------
# Tests — things that should and do agree
# ---------------------------------------------------------------------------


class _RustAvailable(unittest.TestCase):
    """Base that skips when the Rust binary cannot be built."""

    @classmethod
    def setUpClass(cls) -> None:
        if not _cargo_available():
            raise unittest.SkipTest(
                "cargo not available; numeric-boundary conformance skipped"
            )
        if not _ensure_rust_binary():
            raise unittest.SkipTest(
                "Rust binary did not build; conformance skipped"
            )


def _integer_head_boundaries() -> Iterable[int]:
    """Integer values that sit on CBOR head-size boundaries."""
    boundaries = [
        0, 1, 23, 24, 25,
        0xFE, 0xFF, 0x100, 0x101,
        0xFFFE, 0xFFFF, 0x10000, 0x10001,
        0xFFFFFFFE, 0xFFFFFFFF, 0x100000000, 0x100000001,
        (1 << 53) - 1,            # largest integer exact as f64
        (1 << 53),
        (1 << 62),
        (1 << 63) - 1,            # largest i64
    ]
    for v in boundaries:
        yield v
        if v != 0:
            yield -v


class IntegerBoundaryConformance(_RustAvailable):
    """CBOR head selection must agree at every integer boundary.

    Integers have no decimal-parsing ambiguity: the text and the value
    are the same. This is the cleanest place to pin encoder
    agreement and catches head-size-threshold bugs on either side.
    """

    def test_integer_head_transitions_agree(self) -> None:
        for n in _integer_head_boundaries():
            with self.subTest(n=n):
                doc = _wrap_in_module_shape(n)
                python_bytes = canonical_cbor(doc)
                rust_bytes = _rust_cbor_for(doc)
                self.assertEqual(
                    rust_bytes,
                    python_bytes,
                    f"integer {n}: rust={rust_bytes.hex()} "
                    f"python={python_bytes.hex()}",
                )


class SignedZeroConformance(_RustAvailable):
    """+0.0 and -0.0 must encode to distinct canonical bytes on both sides.

    The f16 encoding preserves signed zero via a dedicated path; both
    implementations must agree. ``0.0`` and ``-0.0`` have unambiguous
    decimal text on both JSON parsers, so this is a clean assertion.
    """

    def test_positive_zero_agrees(self) -> None:
        doc = _wrap_in_module_shape(0.0)
        python_bytes = canonical_cbor(doc)
        rust_bytes = _rust_cbor_for(doc)
        self.assertEqual(rust_bytes, python_bytes)

    def test_negative_zero_agrees(self) -> None:
        doc = _wrap_in_module_shape(-0.0)
        python_bytes = canonical_cbor(doc)
        rust_bytes = _rust_cbor_for(doc)
        self.assertEqual(rust_bytes, python_bytes)
        # And the two must produce different canonical bytes.
        pos = canonical_cbor(_wrap_in_module_shape(0.0))
        self.assertNotEqual(
            rust_bytes,
            pos,
            "+0.0 and -0.0 must encode to different canonical CBOR bytes",
        )


class SmallIntegerFloatConformance(_RustAvailable):
    """Small values that unambiguously round-trip through both JSON parsers.

    These are values whose shortest decimal representation (what
    Python's ``json.dumps`` and serde_json both produce) parses back
    to the same f64 bits on both sides. This is the subset where a
    byte-level canonical CBOR agreement claim is unambiguous.
    """

    # Selected small exact-in-f16 values. Each has a short decimal
    # representation that both parsers handle identically.
    EXACT_F16_VALUES = [
        1.0, -1.0, 1.5, -1.5, 2.0, 0.5, 0.25, 0.125,
        100.0, 1024.0, 65504.0,     # largest f16 normal
        -65504.0,
    ]

    def test_exact_f16_values_agree(self) -> None:
        for f in self.EXACT_F16_VALUES:
            with self.subTest(f=f):
                doc = _wrap_in_module_shape(f)
                python_bytes = canonical_cbor(doc)
                rust_bytes = _rust_cbor_for(doc)
                self.assertEqual(
                    rust_bytes,
                    python_bytes,
                    f"exact f16 {f}: rust={rust_bytes.hex()[-80:]} "
                    f"python={python_bytes.hex()[-80:]}",
                )


# ---------------------------------------------------------------------------
# Tests that do not need the Rust binary
# ---------------------------------------------------------------------------


class NanInfinityRejection(unittest.TestCase):
    """Both implementations MUST refuse NaN and infinity in canonical CBOR.

    The Rust side refuses these at the serde_json layer before the
    encoder ever sees them. This test covers the Python-side
    rejection; the Rust side is covered by its own in-crate tests.
    """

    def test_python_refuses_nan(self) -> None:
        with self.assertRaises(ValueError):
            canonical_cbor(float("nan"))

    def test_python_refuses_positive_infinity(self) -> None:
        with self.assertRaises(ValueError):
            canonical_cbor(float("inf"))

    def test_python_refuses_negative_infinity(self) -> None:
        with self.assertRaises(ValueError):
            canonical_cbor(float("-inf"))


class HalfPrecisionAllPatternsDiagnostic(_RustAvailable):
    """Exhaustive f16 enumeration.

    Originally skipped because the JSON-text decimal-parser
    divergence between ``serde_json`` and Python's ``json`` caused
    about 14% of f16 patterns to disagree on content hash.

    Un-skipped 2026-05-11 after the Rust CLI's ``bytes-cbor-in``
    subcommand landed. That subcommand accepts canonical CBOR bytes
    directly, bypassing ``serde_json::from_str``. With no
    JSON-text intermediate, the decimal-parser divergence is
    structurally impossible, and the two implementations agree on
    every finite f16 bit pattern. This test proves that claim.

    If this test ever fails again, either the Rust CBOR decoder
    has regressed or a new cross-implementation divergence has
    appeared in the CBOR byte form. See
    ``dispatches/2026-05-11-rust-cbor-input-post.md``.
    """

    def test_every_finite_f16_pattern_agrees(self) -> None:
        values = list(_all_f16_patterns_as_f64())
        doc = _wrap_in_module_shape(values)
        python_bytes = canonical_cbor(doc)
        rust_bytes = _rust_cbor_for_via_cbor_input(doc)
        self.assertEqual(
            rust_bytes,
            python_bytes,
            f"f16 exhaustive agreement lost via CBOR-in path: "
            f"py={len(python_bytes)} bytes, rs={len(rust_bytes)} bytes",
        )


def _all_f16_patterns_as_f64() -> Iterable[float]:
    """Every representable finite binary16 value as a Python float."""
    for bits in range(0x10000):
        exp = (bits >> 10) & 0x1F
        if exp == 0x1F:
            continue
        packed = bits.to_bytes(2, "big")
        (v,) = struct.unpack(">e", packed)
        yield v


if __name__ == "__main__":
    unittest.main()
