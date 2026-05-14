"""Conformance bridge: Rust interpreter vs Python reference.

Two layers:
  1. Example-file tests — run every .cod file through both runtimes,
     compare JSON-deserialized results.
  2. Inline source tests — mirror the key cases from test_runtime.py,
     test_primitives.py, test_cost_dispatch.py, test_inline_conditional.py,
     and test_indexed_primitives.py, running each through the Rust binary
     and asserting the same outcome as Python.

The Rust binary is `target/release/codifide-run`. If it is not built,
all tests are skipped with a clear reason.

Output format (RI-3): the binary prints the JSON result to stdout.
The bridge deserializes both sides for comparison.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from codifide import parse
from codifide import run as py_run
from codifide.core.types import Bottom
from codifide.runtime.errors import (
    BottomPropagationError,
    ContractViolation,
    DispatchError,
    EffectViolation,
    ParseError,
    PrimitiveError,
    RecursionLimitError,
    RefusalError,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
RUST_BIN = REPO_ROOT / "target" / "release" / "codifide-run"


# ---------------------------------------------------------------------------
# Bridge helpers
# ---------------------------------------------------------------------------

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


def _rust_run_file(path: Path, entry: str = "main", args=None) -> tuple:
    """Run a .cod file through the Rust interpreter.
    Returns (last_stdout_line, stderr_text, returncode).
    """
    cmd = [str(RUST_BIN), "run", str(path), "--entry", entry]
    if args is not None:
        cmd += ["--args", json.dumps(args)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    lines = result.stdout.strip().splitlines()
    last = lines[-1] if lines else None
    return last, result.stderr.strip(), result.returncode


def _rust_run_src(src: str, entry: str = "main", args=None) -> tuple:
    """Run inline Codifide source through the Rust interpreter via a temp file."""
    with tempfile.NamedTemporaryFile("w", suffix=".cod", delete=False, encoding="utf-8") as f:
        f.write(src)
        tmp = Path(f.name)
    try:
        return _rust_run_file(tmp, entry=entry, args=args)
    finally:
        tmp.unlink(missing_ok=True)


def _py_to_json(result) -> str:
    if result is Bottom:
        return json.dumps("\u22a5")
    if isinstance(result, bool):
        return json.dumps(result)
    if isinstance(result, int):
        return json.dumps(result)
    if isinstance(result, float):
        if result == int(result) and abs(result) < 1e15:
            return json.dumps(int(result))
        return json.dumps(result)
    return json.dumps(result)


def _norm(s: str):
    return json.loads(s)


class _RustBase(unittest.TestCase):
    """Base class: skip all tests if the Rust binary is unavailable."""

    @classmethod
    def setUpClass(cls):
        if not _ensure_rust_binary():
            raise unittest.SkipTest("Rust interpreter binary not available; skipped")

    # -- Assertion helpers ------------------------------------------------

    def assertRustEquals(self, src: str, expected, entry: str = "f", args=None):
        """Assert the Rust interpreter returns `expected` for `src`."""
        out, err, rc = _rust_run_src(src, entry=entry, args=args)
        if rc != 0:
            self.fail(f"Rust failed (rc={rc}): {err}")
        self.assertEqual(_norm(out), expected, f"Rust returned {out!r}, expected {expected!r}")

    def assertRustError(self, src: str, entry: str = "f", args=None):
        """Assert the Rust interpreter exits non-zero for `src`."""
        _, _, rc = _rust_run_src(src, entry=entry, args=args)
        self.assertNotEqual(rc, 0, "Expected Rust to fail but it succeeded")

    def assertRustMatchesPython(self, src: str, entry: str = "f", args=None):
        """Assert Rust and Python produce the same result."""
        module = parse(src)
        py_result = py_run(module, entry, args or [])
        py_json = _py_to_json(py_result)

        out, err, rc = _rust_run_src(src, entry=entry, args=args)
        if rc != 0:
            self.fail(f"Rust failed (rc={rc}): {err}\nPython returned: {py_json}")
        self.assertEqual(_norm(out), _norm(py_json),
                         f"Mismatch: Rust={out!r} Python={py_json!r}")


# ---------------------------------------------------------------------------
# 1. Example-file conformance
# ---------------------------------------------------------------------------

class ExampleFileConformance(_RustBase):
    """Every .cod example file: Rust must match Python."""

    def _check(self, path: Path):
        src = path.read_text(encoding="utf-8")
        try:
            module = parse(src)
        except Exception:
            return  # Invalid Codifide; skip silently.

        try:
            py_result = py_run(module)
            py_json = _py_to_json(py_result)
        except Exception as e:
            out, _, rc = _rust_run_file(path)
            if rc == 0:
                self.fail(f"{path.name}: Python raised {type(e).__name__} but Rust returned {out!r}")
            return

        if "clock.now" in src:
            out, err, rc = _rust_run_file(path)
            if rc != 0:
                self.fail(f"{path.name}: Rust failed on clock program: {err}")
            return

        out, err, rc = _rust_run_file(path)
        if rc != 0:
            self.fail(f"{path.name}: Rust failed: {err}\nPython: {py_json}")
        self.assertEqual(_norm(out), _norm(py_json),
                         f"{path.name}: Rust={out!r} Python={py_json!r}")

    def test_top_level(self):
        for p in sorted(EXAMPLES_DIR.glob("*.cod")):
            with self.subTest(example=p.name):
                self._check(p)

    def test_assessment(self):
        for p in sorted((EXAMPLES_DIR / "assessment").glob("*.cod")):
            with self.subTest(example=p.name):
                self._check(p)

    def test_ai_generated(self):
        for p in sorted((EXAMPLES_DIR / "ai_generated").glob("*.cod")):
            with self.subTest(example=p.name):
                self._check(p)


# ---------------------------------------------------------------------------
# 2. Runtime semantics
# ---------------------------------------------------------------------------

class RuntimeSemantics(_RustBase):

    def test_pure_expression(self):
        self.assertRustEquals("""
def f
  intent "compute 42"
  sig    () -> Int
  effects {}
  cand
    add(40, 2)
""", 42)

    def test_sort_example(self):
        src = (EXAMPLES_DIR / "sort.cod").read_text()
        out, err, rc = _rust_run_file(EXAMPLES_DIR / "sort.cod")
        self.assertEqual(rc, 0, err)
        self.assertEqual(_norm(out), [1, 1, 2, 3, 3, 4, 5, 5, 6, 9])

    def test_undeclared_effect_rejected(self):
        self.assertRustError("""
def f
  intent "phones home"
  sig    () -> String
  effects {}
  cand
    io.say("oops")
""")

    def test_declared_effect_allowed(self):
        out, err, rc = _rust_run_src("""
def f
  intent "declares what it does"
  sig    () -> String
  effects {io.stdout}
  cand
    io.say("hello")
""", entry="f")
        self.assertEqual(rc, 0, err)

    def test_transitive_effect_rejected(self):
        self.assertRustError("""
def launder
  intent "claims pure but calls impure"
  sig    () -> String
  effects {}
  cand
    impure()

def impure
  intent "does io"
  sig    () -> String
  effects {io.stdout}
  cand
    io.say("pwned")
""")

    def test_transitive_effect_allowed_when_declared(self):
        out, err, rc = _rust_run_src("""
def outer
  intent "declares everything"
  sig    () -> String
  effects {io.stdout}
  cand
    inner()

def inner
  intent "uses io"
  sig    () -> String
  effects {io.stdout}
  cand
    io.say("legit")
""", entry="outer")
        self.assertEqual(rc, 0, err)

    def test_precondition_failure(self):
        self.assertRustError("""
def f
  intent "require non-empty"
  sig    (name: String) -> String
  effects {}
  pre    ne(name, "")
  cand
    name
""", args=[""])

    def test_postcondition_failure(self):
        self.assertRustError("""
def f
  intent "promises name in output"
  sig    (name: String) -> String
  effects {}
  post   contains(result, name)
  cand
    "something else"
""", args=["Ada"])

    def test_candidate_guards_in_order(self):
        src = """
def f
  intent "pick tiny vs default"
  sig    (n: Int) -> String
  effects {}
  cand
    intent "tiny"
    when   lt(n, 10)
    "tiny"
  cand
    intent "default"
    "default"
"""
        self.assertRustEquals(src, "tiny", args=[5])
        self.assertRustEquals(src, "default", args=[100])

    def test_dispatch_error_no_guard_matches(self):
        self.assertRustError("""
def f
  intent "no default"
  sig    (n: Int) -> String
  effects {}
  cand
    when   lt(n, 0)
    "negative"
""", args=[1])

    def test_div_by_zero_is_error(self):
        self.assertRustError("""
def f
  intent "div by zero"
  sig    () -> Int
  effects {}
  cand
    div(1, 0)
""")

    def test_bottom_into_arithmetic_is_error(self):
        self.assertRustError("""
def f
  intent "bottom into arithmetic"
  sig    () -> Int
  effects {}
  cand
    add(1, bottom)
""")

    def test_recursion_limit_enforced(self):
        # 100-deep chain; default limit is 64.
        parts = []
        for i in range(100):
            nxt = f"f{i+1}()" if i < 99 else "1"
            parts.append(
                f"\ndef f{i}\n  intent \"chain\"\n  sig () -> Int\n"
                f"  effects {{}}\n  cand\n    {nxt}\n"
            )
        self.assertRustError("".join(parts), entry="f0")

    def test_contracts_are_pure(self):
        self.assertRustError("""
def f
  intent "post tries io"
  sig    () -> String
  effects {io.stdout}
  post   contains(result, io.say("x"))
  cand
    "ok"
""")

    def test_belief_dispatch_high_confidence(self):
        src = (EXAMPLES_DIR / "classify.cod").read_text()
        out, err, rc = _rust_run_file(EXAMPLES_DIR / "classify.cod")
        self.assertEqual(rc, 0, err)
        self.assertEqual(_norm(out), "cat")

    def test_belief_dispatch_refusal_below_threshold(self):
        self.assertRustError("""
def classify
  intent "refuse rather than guess"
  sig    (img: Image) -> Label
  effects {model.vision}
  cand
    label <- vision.classify(img)
    believe label
      ge(conf(label), 0.9) => label
      else                 => bottom

def main
  intent "low-confidence path"
  sig    () -> Label
  effects {model.vision}
  cand
    classify(low_conf_image())

def low_conf_image
  intent "deliberately low confidence"
  sig    () -> Image
  effects {}
  cand
    host_image("maybe-cat", 0.3)
""", entry="main")


# ---------------------------------------------------------------------------
# 3. Primitive library
# ---------------------------------------------------------------------------

class PrimitiveLibrary(_RustBase):

    def test_math_primitives(self):
        self.assertRustEquals("""
def f
  intent "math"
  sig    () -> List
  effects {}
  cand
    list(abs(neg(7)), min(3, 9), max(3, 9), pow(2, 10), floor(2.9), ceil(2.1), round(2.5))
""", [7, 3, 9, 1024, 2, 3, 2])

    def test_collection_primitives(self):
        self.assertRustEquals("""
def f
  intent "collections"
  sig    () -> List
  effects {}
  cand
    xs <- list(3, 1, 4, 1, 5)
    list(min_of(xs), max_of(xs), sum(xs), reverse(xs), append(xs, 9), contains_item(xs, 4), contains_item(xs, 99), sum(list()))
""", [1, 5, 14, [5, 1, 4, 1, 3], [3, 1, 4, 1, 5, 9], True, False, 0])

    def test_append_non_mutating(self):
        self.assertRustEquals("""
def f
  intent "non-mutating append"
  sig    () -> List
  effects {}
  cand
    xs <- list(1, 2)
    ys <- append(xs, 3)
    list(len(xs), len(ys))
""", [2, 3])

    def test_string_primitives(self):
        self.assertRustEquals("""
def f
  intent "strings"
  sig    () -> List
  effects {}
  cand
    list(upper("cafe"), lower("CODIFIDE"), trim("  hi  "), starts_with("codifide", "codi"), ends_with("codifide", "fide"), replace("a-b-c", "-", "/"), split("a,b,c", ","), join("/", split("a,b,c", ",")))
""", ["CAFE", "codifide", "hi", True, True, "a/b/c", ["a", "b", "c"], "a/b/c"])

    def test_min_of_empty_is_error(self):
        self.assertRustError("""
def f
  intent "min of empty"
  sig    () -> Any
  effects {}
  cand
    min_of(list())
""")

    def test_reverse_string(self):
        self.assertRustEquals("""
def f
  intent "reverse string"
  sig    () -> String
  effects {}
  cand
    reverse("hello")
""", "olleh")

    def test_reverse_list(self):
        self.assertRustEquals("""
def f
  intent "reverse list"
  sig    () -> List
  effects {}
  cand
    reverse(list(1, 2, 3))
""", [3, 2, 1])

    def test_is_sorted(self):
        self.assertRustEquals("""
def f
  intent "is_sorted"
  sig    () -> List
  effects {}
  cand
    list(is_sorted(list(1, 2, 3)), is_sorted(list(3, 1, 2)))
""", [True, False])

    def test_str_primitive(self):
        self.assertRustEquals("""
def f
  intent "str"
  sig    () -> String
  effects {}
  cand
    str(42)
""", "42")

    def test_mod_primitive(self):
        self.assertRustEquals("""
def f
  intent "mod"
  sig    () -> Int
  effects {}
  cand
    mod(10, 3)
""", 1)

    def test_contains_string(self):
        self.assertRustEquals("""
def f
  intent "contains"
  sig    () -> Bool
  effects {}
  cand
    contains("hello world", "world")
""", True)

    def test_conf_primitive(self):
        self.assertRustEquals("""
def f
  intent "conf"
  sig    () -> Float
  effects {}
  cand
    conf(belief(42, 0.7))
""", 0.7)

    def test_is_bottom_true(self):
        self.assertRustEquals("""
def f
  intent "is_bottom true"
  sig    () -> Bool
  effects {}
  cand
    is_bottom(bottom)
""", True)

    def test_is_bottom_false(self):
        self.assertRustEquals("""
def f
  intent "is_bottom false"
  sig    () -> Bool
  effects {}
  cand
    is_bottom(42)
""", False)


# ---------------------------------------------------------------------------
# 4. Cost-based dispatch
# ---------------------------------------------------------------------------

class CostDispatch(_RustBase):

    def test_unannotated_first_wins(self):
        self.assertRustEquals("""
def f
  intent "unannotated"
  sig    () -> String
  effects {}
  cand
    intent "first"
    "first"
  cand
    intent "second"
    "second"
""", "first")

    def test_lower_cost_wins(self):
        self.assertRustEquals("""
def f
  intent "two costed"
  sig    () -> String
  effects {}
  cand
    intent "expensive"
    cost 100
    "expensive"
  cand
    intent "cheap"
    cost 10
    "cheap"
""", "cheap")

    def test_declaration_index_breaks_ties(self):
        self.assertRustEquals("""
def f
  intent "equal costs"
  sig    () -> String
  effects {}
  cand
    intent "first"
    cost 5
    "first"
  cand
    intent "second"
    cost 5
    "second"
""", "first")

    def test_annotated_beats_unannotated(self):
        self.assertRustEquals("""
def f
  intent "mixed"
  sig    () -> String
  effects {}
  cand
    intent "unannotated first"
    "from_unannotated"
  cand
    intent "annotated second"
    cost 100
    "from_annotated"
""", "from_annotated")

    def test_false_guard_skipped_despite_low_cost(self):
        self.assertRustEquals("""
def f
  intent "guarded cheap"
  sig    () -> String
  effects {}
  cand
    intent "cheap but false"
    cost 1
    when  eq(1, 2)
    "unreachable"
  cand
    intent "expensive but reachable"
    cost 1000
    "reachable"
""", "reachable")

    def test_zero_cost_wins(self):
        self.assertRustEquals("""
def f
  intent "zero cost"
  sig    () -> String
  effects {}
  cand
    intent "free"
    cost 0
    "free"
  cand
    intent "paid"
    cost 1
    "paid"
""", "free")


# ---------------------------------------------------------------------------
# 5. Inline conditional
# ---------------------------------------------------------------------------

class InlineConditional(_RustBase):

    def test_true_branch(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    if true then 1 else 2
""", 1)

    def test_false_branch(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    if false then 1 else 2
""", 2)

    def test_computed_condition(self):
        src = """
def f
  intent "abs"
  sig (n: Int) -> Int
  effects {}
  cand
    if lt(n, 0) then neg(n) else n
"""
        self.assertRustEquals(src, 5, args=[-5])
        self.assertRustEquals(src, 7, args=[7])

    def test_nested_if(self):
        src = """
def f
  intent "sign"
  sig (n: Int) -> Int
  effects {}
  cand
    if lt(n, 0) then neg(1) else if eq(n, 0) then 0 else 1
"""
        self.assertRustEquals(src, -1, args=[-3])
        self.assertRustEquals(src, 0, args=[0])
        self.assertRustEquals(src, 1, args=[5])

    def test_short_circuit_else_not_evaluated(self):
        self.assertRustEquals("""
def f
  intent "gate index by length"
  sig (s: String) -> String
  effects {}
  cand
    if gt(len(s), 0) then char_at(s, 0) else ""
""", "h", args=["hello"])

    def test_short_circuit_empty_string(self):
        self.assertRustEquals("""
def f
  intent "gate index by length"
  sig (s: String) -> String
  effects {}
  cand
    if gt(len(s), 0) then char_at(s, 0) else ""
""", "", args=[""])

    def test_short_circuit_division(self):
        src = """
def f
  intent "safe div"
  sig (a: Int, b: Int) -> Int
  effects {}
  cand
    if eq(b, 0) then 0 else div(a, b)
"""
        self.assertRustEquals(src, 0, args=[10, 0])
        self.assertRustEquals(src, 5, args=[10, 2])

    def test_if_in_postcondition(self):
        self.assertRustEquals("""
def f
  intent "abs with post"
  sig (n: Int) -> Int
  effects {}
  post   eq(result, if lt(n, 0) then neg(n) else n)
  cand
    if lt(n, 0) then neg(n) else n
""", 7, args=[-7])

    def test_multiline_if(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig (n: Int) -> Int
  effects {}
  cand
    if lt(n, 0)
      then neg(n)
      else n
""", 5, args=[-5])

    def test_effectful_if_in_pure_context_rejected(self):
        self.assertRustError("""
def f
  intent "hide io in if"
  sig () -> String
  effects {}
  cand
    if true then io.say("hi") else "ok"
""")


# ---------------------------------------------------------------------------
# 6. Indexed primitives
# ---------------------------------------------------------------------------

class IndexedPrimitives(_RustBase):

    def test_slice_string(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig (s: String) -> String
  effects {}
  cand
    slice(s, 1, 4)
""", "bcd", args=["abcdef"])

    def test_slice_list(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> List
  effects {}
  cand
    slice(list(1, 2, 3, 4, 5), 1, 4)
""", [2, 3, 4])

    def test_slice_clamps_out_of_range(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig (s: String) -> String
  effects {}
  cand
    slice(s, -100, 100)
""", "abc", args=["abc"])

    def test_slice_empty_when_start_ge_end(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    slice("hello", 3, 2)
""", "")

    def test_at_string(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    at("hello", 1)
""", "e")

    def test_at_list(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    at(list(10, 20, 30), 2)
""", 30)

    def test_at_negative_index(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    at("hello", -1)
""", "o")

    def test_at_out_of_range_is_error(self):
        self.assertRustError("""
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    at("hi", 10)
""")

    def test_char_at_string(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    char_at("hello", 0)
""", "h")

    def test_char_at_rejects_list(self):
        self.assertRustError("""
def f
  intent "t"
  sig () -> String
  effects {}
  cand
    char_at(list(1, 2, 3), 0)
""")

    def test_indexof_string(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    indexof("hello world", "world")
""", 6)

    def test_indexof_string_not_found(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    indexof("abc", "z")
""", -1)

    def test_indexof_list(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    indexof(list("a", "b", "c"), "b")
""", 1)

    def test_indexof_list_not_found(self):
        self.assertRustEquals("""
def f
  intent "t"
  sig () -> Int
  effects {}
  cand
    indexof(list(1, 2, 3), 99)
""", -1)


# ---------------------------------------------------------------------------
# 7. Assessment battery
# ---------------------------------------------------------------------------

class AssessmentBattery(_RustBase):
    """All 7 assessment programs must pass through the Rust interpreter."""

    def _run_assessment(self, name: str):
        path = EXAMPLES_DIR / "assessment" / name
        src = path.read_text(encoding="utf-8")
        if "clock.now" in src:
            out, err, rc = _rust_run_file(path)
            self.assertEqual(rc, 0, f"{name}: {err}")
            return
        module = parse(src)
        py_result = py_run(module)
        py_json = _py_to_json(py_result)
        out, err, rc = _rust_run_file(path)
        self.assertEqual(rc, 0, f"{name}: {err}")
        self.assertEqual(_norm(out), _norm(py_json), f"{name}: Rust={out!r} Python={py_json!r}")

    def test_01_fahrenheit_to_celsius(self): self._run_assessment("01_fahrenheit_to_celsius.cod")
    def test_02_email_valid(self):           self._run_assessment("02_email_valid.cod")
    def test_03_fizzbuzz(self):              self._run_assessment("03_fizzbuzz.cod")
    def test_04_greeting_confidence(self):   self._run_assessment("04_greeting_confidence.cod")
    def test_05_balanced_brackets(self):     self._run_assessment("05_balanced_brackets.cod")
    def test_06_pipeline(self):              self._run_assessment("06_pipeline.cod")
    def test_07_url_parse(self):             self._run_assessment("07_url_parse.cod")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# 8. From-import via Rust runtime (V2-3)
# ---------------------------------------------------------------------------

class FromImportRust(_RustBase):
    """V2-3: from-import resolved by the Rust parser with --store flag."""

    def setUp(self):
        super()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store_root = Path(self._tmpdir.name) / "store"
        from codifide.store import SymbolStore
        self.store = SymbolStore(self.store_root)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _rust_run_with_store(self, src: str, entry: str = "main") -> tuple:
        """Run inline source through Rust with --store pointing at our temp store."""
        with tempfile.NamedTemporaryFile("w", suffix=".cod", delete=False, encoding="utf-8") as f:
            f.write(src)
            tmp = Path(f.name)
        try:
            cmd = [str(RUST_BIN), "run", str(tmp),
                   "--entry", entry,
                   "--store", str(self.store_root)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            lines = result.stdout.strip().splitlines()
            last = lines[-1] if lines else None
            return last, result.stderr.strip(), result.returncode
        finally:
            tmp.unlink(missing_ok=True)

    def _store_symbol(self, src: str, sym_name: str) -> str:
        """Parse src, store sym_name, return its identity."""
        from codifide import parse as py_parse
        from codifide.core.types import Module as CodModule
        from codifide.projection.canonical import to_canonical
        from codifide.projection.cbor import canonical_cbor
        module = py_parse(src)
        defn = next(d for d in module.symbols if d.name == sym_name)
        single = CodModule(name=module.name, symbols=(defn,), imports=())
        return self.store.put(defn.name, defn)

    def test_from_import_basic(self) -> None:
        """from-import resolves a symbol from the store via the Rust parser."""
        greet_src = """\
module greet_lib

def greet
  intent "greet a user"
  sig    (name: String) -> String
  effects {}
  cand
    "hello, " ++ name
"""
        greet_id = self._store_symbol(greet_src, "greet")

        # Build an index module pointing at greet.
        import hashlib
        from codifide.core.types import Module as CodModule
        from codifide.projection.canonical import to_canonical
        from codifide.projection.cbor import canonical_cbor
        index = CodModule(
            name="greet_index",
            symbols=(),
            imports=(("greet", greet_id),),
        )
        index_cbor = canonical_cbor(to_canonical(index))
        index_id = f"sha256:{hashlib.sha256(index_cbor).hexdigest()}"
        self.store._write_atomic(index_id, index_cbor, suffix=".cbor")

        consumer_src = f"""\
module consumer

from {index_id} import greet

def main
  intent "use greet from index"
  sig    () -> String
  effects {{}}
  cand
    greet("world")
"""
        out, err, rc = self._rust_run_with_store(consumer_src)
        self.assertEqual(rc, 0, f"Rust failed: {err}")
        self.assertEqual(_norm(out), "hello, world")

    def test_from_import_missing_store_gives_clear_error(self) -> None:
        """from-import without --store gives a clear error message."""
        src = """\
module consumer

from sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa import foo

def main
  intent "test"
  sig    () -> String
  effects {}
  cand
    foo()
"""
        with tempfile.NamedTemporaryFile("w", suffix=".cod", delete=False, encoding="utf-8") as f:
            f.write(src)
            tmp = Path(f.name)
        try:
            # Run WITHOUT --store flag.
            cmd = [str(RUST_BIN), "run", str(tmp), "--entry", "main"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("store", result.stderr.lower())
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# 9. Parallel evaluator import support (V3-1 / AUD-OVERNIGHT-02)
# ---------------------------------------------------------------------------

class ParallelImportRust(_RustBase):
    """V3-1: imported symbols are available inside parallel branches.

    Regression test for AUD-OVERNIGHT-02. Before the fix, branch interpreters
    were created with empty resolved_imports, so a call to an imported symbol
    inside list(f(x), g(x)) would fail with 'unknown callable'. After the fix,
    the parent's resolved_imports are cloned into each branch interpreter.

    The test publishes two pure symbols to a temp store, then writes a consumer
    that calls both inside list(...). The parallel evaluator should fire (both
    args are direct calls to imported symbols with disjoint effects) and return
    the correct result.
    """

    def setUp(self):
        super()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store_root = Path(self._tmpdir.name) / "store"
        from codifide.store import SymbolStore
        self.store = SymbolStore(self.store_root)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _rust_run_with_store(self, src: str, entry: str = "main") -> tuple:
        with tempfile.NamedTemporaryFile("w", suffix=".cod", delete=False, encoding="utf-8") as f:
            f.write(src)
            tmp = Path(f.name)
        try:
            cmd = [str(RUST_BIN), "run", str(tmp),
                   "--entry", entry,
                   "--store", str(self.store_root)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            lines = result.stdout.strip().splitlines()
            last = lines[-1] if lines else None
            return last, result.stderr.strip(), result.returncode
        finally:
            tmp.unlink(missing_ok=True)

    def _store_symbol(self, src: str, sym_name: str) -> str:
        from codifide import parse as py_parse
        module = py_parse(src)
        defn = next(d for d in module.symbols if d.name == sym_name)
        return self.store.put(defn.name, defn)

    def test_imported_symbols_available_in_parallel_branches(self) -> None:
        """list(double(n), triple(n)) with imported double and triple evaluates correctly.

        Both args are direct calls to imported pure symbols with disjoint effects
        (both effects {}). The parallel evaluator should fire and return the correct
        list. Before V3-1, this would fail with 'unknown callable: double'.
        """
        double_src = """\
def double
  intent "double a number"
  sig    (n: Int) -> Int
  effects {}
  cand
    add(n, n)
"""
        triple_src = """\
def triple
  intent "triple a number"
  sig    (n: Int) -> Int
  effects {}
  cand
    add(n, add(n, n))
"""
        double_id = self._store_symbol(double_src, "double")
        triple_id = self._store_symbol(triple_src, "triple")

        consumer_src = f"""\
import double = {double_id}
import triple = {triple_id}

def run_both
  intent "call double and triple in parallel via list"
  sig    (n: Int) -> List
  effects {{}}
  cand
    list(double(n), triple(n))

def main
  intent "test parallel imported symbol calls"
  sig    () -> List
  effects {{}}
  cand
    run_both(5)
"""
        out, err, rc = self._rust_run_with_store(consumer_src)
        self.assertEqual(rc, 0, f"Rust failed: {err}")
        result = _norm(out)
        self.assertEqual(result, [10, 15],
                         f"Expected [10, 15] (double(5)=10, triple(5)=15), got {result!r}")

    def test_imported_effectful_symbols_serialize(self) -> None:
        """Two imported symbols sharing an effect (io.stdout) must not parallelize.

        The effect-disjoint check should prevent parallelism when both symbols
        declare the same effect. This test verifies the effect analysis correctly
        handles imported symbols — it should run sequentially and succeed.
        """
        say_hi_src = """\
def say_hi
  intent "print hi"
  sig    (name: String) -> String
  effects {io.stdout}
  cand
    io.say("hi " ++ name)
"""
        say_bye_src = """\
def say_bye
  intent "print bye"
  sig    (name: String) -> String
  effects {io.stdout}
  cand
    io.say("bye " ++ name)
"""
        hi_id = self._store_symbol(say_hi_src, "say_hi")
        bye_id = self._store_symbol(say_bye_src, "say_bye")

        consumer_src = f"""\
import say_hi  = {hi_id}
import say_bye = {bye_id}

def greet_and_farewell
  intent "say hi then bye — must serialize due to shared io.stdout effect"
  sig    (name: String) -> String
  effects {{io.stdout}}
  cand
    say_hi(name)
    say_bye(name)

def main
  intent "test that shared-effect imported symbols serialize correctly"
  sig    () -> String
  effects {{io.stdout}}
  cand
    greet_and_farewell("world")
"""
        out, err, rc = self._rust_run_with_store(consumer_src)
        self.assertEqual(rc, 0, f"Rust failed: {err}")
        # say_bye is the last call in the seq, so main returns "bye world"
        self.assertEqual(_norm(out), "bye world")
