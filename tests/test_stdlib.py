"""Tests for V4-2: Standard library primitives.

Covers:
  V4-2a: io.read, io.write, io.exists
  V4-2b: http.get, http.post (HTTPS enforcement, error handling)
  V4-2c: json.parse, json.encode
  V4-2d: clock.today, clock.parse, clock.add_days, clock.format
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from codifide import parse, run
from codifide.runtime.errors import PrimitiveError, EffectViolation


def _run(src: str, entry: str = "main") -> object:
    return run(parse(src), entry)


# ---------------------------------------------------------------------------
# V4-2a: File I/O
# ---------------------------------------------------------------------------

class FileIOTests(unittest.TestCase):

    def test_io_read_reads_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello from file")
            path = f.name
        try:
            src = f"""
def main
  intent "read a file"
  sig    () -> String
  effects {{io.read}}
  cand
    io.read("{path}")
"""
            self.assertEqual(_run(src), "hello from file")
        finally:
            os.unlink(path)

    def test_io_write_writes_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            path = f.name
        try:
            src = f"""
def main
  intent "write a file"
  sig    () -> Unit
  effects {{io.write}}
  cand
    io.write("{path}", "written by codifide")
"""
            _run(src)
            with open(path) as fh:
                self.assertEqual(fh.read(), "written by codifide")
        finally:
            os.unlink(path)

    def test_io_exists_true_for_existing_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            path = f.name
        try:
            src = f"""
def main
  intent "check file exists"
  sig    () -> Bool
  effects {{io.read}}
  cand
    io.exists("{path}")
"""
            self.assertTrue(_run(src))
        finally:
            os.unlink(path)

    def test_io_exists_false_for_missing_file(self):
        src = """
def main
  intent "check missing file"
  sig    () -> Bool
  effects {io.read}
  cand
    io.exists("/tmp/codifide_test_definitely_does_not_exist_xyz.txt")
"""
        self.assertFalse(_run(src))

    def test_io_read_rejects_path_traversal(self):
        src = """
def main
  intent "attempt path traversal"
  sig    () -> String
  effects {io.read}
  cand
    io.read("../../etc/passwd")
"""
        with self.assertRaises(PrimitiveError) as ctx:
            _run(src)
        self.assertIn("traversal", str(ctx.exception).lower())

    def test_io_write_rejects_path_traversal(self):
        src = """
def main
  intent "attempt path traversal write"
  sig    () -> Unit
  effects {io.write}
  cand
    io.write("../../tmp/evil.txt", "bad")
"""
        with self.assertRaises(PrimitiveError) as ctx:
            _run(src)
        self.assertIn("traversal", str(ctx.exception).lower())

    def test_io_read_requires_io_read_effect(self):
        src = """
def main
  intent "read without effect"
  sig    () -> String
  effects {}
  cand
    io.read("/tmp/test.txt")
"""
        with self.assertRaises(EffectViolation):
            _run(src)

    def test_io_write_requires_io_write_effect(self):
        src = """
def main
  intent "write without effect"
  sig    () -> Unit
  effects {}
  cand
    io.write("/tmp/test.txt", "bad")
"""
        with self.assertRaises(EffectViolation):
            _run(src)


# ---------------------------------------------------------------------------
# V4-2b: HTTP client
# ---------------------------------------------------------------------------

class HTTPClientTests(unittest.TestCase):

    def test_http_get_rejects_http_url(self):
        src = """
def main
  intent "attempt http not https"
  sig    () -> String
  effects {http.fetch}
  cand
    http.get("http://example.com")
"""
        with self.assertRaises(PrimitiveError) as ctx:
            _run(src)
        self.assertIn("HTTPS", str(ctx.exception))

    def test_http_post_rejects_http_url(self):
        src = """
def main
  intent "attempt http post not https"
  sig    () -> String
  effects {http.fetch}
  cand
    http.post("http://example.com", "body")
"""
        with self.assertRaises(PrimitiveError) as ctx:
            _run(src)
        self.assertIn("HTTPS", str(ctx.exception))

    def test_http_get_requires_http_fetch_effect(self):
        src = """
def main
  intent "http get without effect"
  sig    () -> String
  effects {}
  cand
    http.get("https://example.com")
"""
        with self.assertRaises(EffectViolation):
            _run(src)

    def test_http_post_requires_http_fetch_effect(self):
        src = """
def main
  intent "http post without effect"
  sig    () -> String
  effects {}
  cand
    http.post("https://example.com", "body")
"""
        with self.assertRaises(EffectViolation):
            _run(src)


# ---------------------------------------------------------------------------
# V4-2c: JSON primitives
# ---------------------------------------------------------------------------

class JSONPrimitivesTests(unittest.TestCase):

    def test_json_parse_object(self):
        src = """
def main
  intent "parse json object"
  sig    () -> Any
  effects {}
  cand
    json.parse("{\\\"key\\\": \\\"value\\\"}")
"""
        result = _run(src)
        self.assertEqual(result, {"key": "value"})

    def test_json_parse_array(self):
        src = """
def main
  intent "parse json array"
  sig    () -> Any
  effects {}
  cand
    json.parse("[1, 2, 3]")
"""
        result = _run(src)
        self.assertEqual(result, [1, 2, 3])

    def test_json_parse_string(self):
        src = """
def main
  intent "parse json string"
  sig    () -> Any
  effects {}
  cand
    json.parse("\\"hello\\"")
"""
        self.assertEqual(_run(src), "hello")

    def test_json_parse_number(self):
        src = """
def main
  intent "parse json number"
  sig    () -> Any
  effects {}
  cand
    json.parse("42")
"""
        self.assertEqual(_run(src), 42)

    def test_json_parse_invalid_raises(self):
        src = """
def main
  intent "parse invalid json"
  sig    () -> Any
  effects {}
  cand
    json.parse("not json {{{")
"""
        with self.assertRaises(PrimitiveError) as ctx:
            _run(src)
        self.assertIn("json.parse", str(ctx.exception))

    def test_json_encode_list(self):
        src = """
def main
  intent "encode list as json"
  sig    () -> String
  effects {}
  cand
    json.encode(list(1, 2, 3))
"""
        result = _run(src)
        self.assertEqual(json.loads(result), [1, 2, 3])

    def test_json_encode_string(self):
        src = """
def main
  intent "encode string as json"
  sig    () -> String
  effects {}
  cand
    json.encode("hello")
"""
        result = _run(src)
        self.assertEqual(json.loads(result), "hello")

    def test_json_encode_number(self):
        src = """
def main
  intent "encode number as json"
  sig    () -> String
  effects {}
  cand
    json.encode(42)
"""
        result = _run(src)
        self.assertEqual(json.loads(result), 42)

    def test_json_parse_is_pure(self):
        """json.parse has no effect — usable in effects {} functions."""
        src = """
def main
  intent "parse json in pure context"
  sig    () -> Any
  effects {}
  cand
    json.parse("[1,2,3]")
"""
        self.assertEqual(_run(src), [1, 2, 3])

    def test_json_encode_is_pure(self):
        src = """
def main
  intent "encode json in pure context"
  sig    () -> String
  effects {}
  cand
    json.encode(list(1, 2))
"""
        result = _run(src)
        self.assertEqual(json.loads(result), [1, 2])

    def test_json_roundtrip(self):
        """parse(encode(x)) == x for simple values."""
        src = """
def main
  intent "json roundtrip"
  sig    () -> Any
  effects {}
  cand
    json.parse(json.encode(list(1, 2, 3)))
"""
        self.assertEqual(_run(src), [1, 2, 3])


# ---------------------------------------------------------------------------
# V4-2d: Date arithmetic
# ---------------------------------------------------------------------------

class DateArithmeticTests(unittest.TestCase):

    def test_clock_today_returns_date_string(self):
        import re
        src = """
def main
  intent "get today"
  sig    () -> String
  effects {clock.read}
  cand
    clock.today()
"""
        result = _run(src)
        self.assertRegex(str(result), r"^\d{4}-\d{2}-\d{2}$")

    def test_clock_parse_returns_int(self):
        src = """
def main
  intent "parse a date"
  sig    () -> Int
  effects {}
  cand
    clock.parse("2026-01-01")
"""
        result = _run(src)
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)

    def test_clock_add_days_adds_one_day(self):
        src = """
def main
  intent "add one day"
  sig    () -> Int
  effects {}
  cand
    clock.add_days(clock.parse("2026-01-01"), 1)
"""
        base_src = """
def main
  intent "base"
  sig    () -> Int
  effects {}
  cand
    clock.parse("2026-01-01")
"""
        base = _run(base_src)
        result = _run(src)
        self.assertEqual(result, base + 86400)

    def test_clock_add_days_negative(self):
        src = """
def main
  intent "subtract one day"
  sig    () -> Int
  effects {}
  cand
    clock.add_days(clock.parse("2026-01-02"), -1)
"""
        base_src = """
def main
  intent "base"
  sig    () -> Int
  effects {}
  cand
    clock.parse("2026-01-01")
"""
        base = _run(base_src)
        result = _run(src)
        self.assertEqual(result, base)

    def test_clock_format_year(self):
        src = """
def main
  intent "format year"
  sig    () -> String
  effects {}
  cand
    clock.format(clock.parse("2026-05-14"), "%Y")
"""
        self.assertEqual(_run(src), "2026")

    def test_clock_parse_invalid_raises(self):
        src = """
def main
  intent "parse invalid date"
  sig    () -> Int
  effects {}
  cand
    clock.parse("not-a-date")
"""
        with self.assertRaises(PrimitiveError) as ctx:
            _run(src)
        self.assertIn("clock.parse", str(ctx.exception))

    def test_clock_today_requires_clock_read_effect(self):
        src = """
def main
  intent "today without effect"
  sig    () -> String
  effects {}
  cand
    clock.today()
"""
        with self.assertRaises(EffectViolation):
            _run(src)

    def test_clock_parse_is_pure(self):
        src = """
def main
  intent "parse date pure"
  sig    () -> Int
  effects {}
  cand
    clock.parse("2026-01-01")
"""
        result = _run(src)
        self.assertIsInstance(result, int)

    def test_clock_add_days_is_pure(self):
        src = """
def main
  intent "add days pure"
  sig    () -> Int
  effects {}
  cand
    clock.add_days(1000000, 7)
"""
        self.assertEqual(_run(src), 1000000 + 7 * 86400)

    def test_clock_format_is_pure(self):
        src = """
def main
  intent "format pure"
  sig    () -> String
  effects {}
  cand
    clock.format(0, "%Y")
"""
        result = _run(src)
        # epoch year depends on timezone but should be a 4-digit year
        self.assertRegex(str(result), r"^\d{4}$")


# ---------------------------------------------------------------------------
# Capability manifest coverage
# ---------------------------------------------------------------------------

class StdlibInManifestTests(unittest.TestCase):
    """New stdlib primitives appear in the capability manifest."""

    def setUp(self):
        from codifide.capability import generate_capability
        self.manifest = generate_capability()
        self.prim_names = {p["name"] for p in self.manifest["primitives"]}
        self.effects = set(self.manifest["effects"])

    def test_io_read_in_manifest(self):
        self.assertIn("io.read", self.prim_names)

    def test_io_write_in_manifest(self):
        self.assertIn("io.write", self.prim_names)

    def test_io_exists_in_manifest(self):
        self.assertIn("io.exists", self.prim_names)

    def test_http_get_in_manifest(self):
        self.assertIn("http.get", self.prim_names)

    def test_http_post_in_manifest(self):
        self.assertIn("http.post", self.prim_names)

    def test_json_parse_in_manifest(self):
        self.assertIn("json.parse", self.prim_names)

    def test_json_encode_in_manifest(self):
        self.assertIn("json.encode", self.prim_names)

    def test_clock_today_in_manifest(self):
        self.assertIn("clock.today", self.prim_names)

    def test_clock_parse_in_manifest(self):
        self.assertIn("clock.parse", self.prim_names)

    def test_clock_add_days_in_manifest(self):
        self.assertIn("clock.add_days", self.prim_names)

    def test_clock_format_in_manifest(self):
        self.assertIn("clock.format", self.prim_names)

    def test_io_read_effect_in_manifest(self):
        self.assertIn("io.read", self.effects)

    def test_io_write_effect_in_manifest(self):
        self.assertIn("io.write", self.effects)

    def test_http_fetch_effect_in_manifest(self):
        self.assertIn("http.fetch", self.effects)

    def test_type_violation_in_manifest_errors(self):
        error_names = {e["name"] for e in self.manifest["errors"]}
        self.assertIn("TypeViolation", error_names)


if __name__ == "__main__":
    unittest.main()
