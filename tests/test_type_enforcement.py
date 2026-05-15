"""Tests for V4-1: Runtime type enforcement.

Every user-function call boundary checks argument types against sig
declarations and return values against the declared return type.
TypeViolation is raised on mismatch. Any-typed values pass all checks.
"""
from __future__ import annotations

import unittest

from codifide import parse, run
from codifide.runtime.errors import TypeViolation


def _run(src: str, entry: str = "main") -> object:
    return run(parse(src), entry)


class ArgTypeEnforcement(unittest.TestCase):
    """Type checking on function arguments."""

    def test_int_param_accepts_int(self):
        src = """
def double
  intent "double an int"
  sig    (n: Int) -> Int
  effects {}
  cand
    add(n, n)

def main
  intent "test"
  sig    () -> Int
  effects {}
  cand
    double(21)
"""
        self.assertEqual(_run(src), 42)

    def test_int_param_rejects_string(self):
        src = """
def double
  intent "double an int"
  sig    (n: Int) -> Int
  effects {}
  cand
    add(n, n)

def main
  intent "test"
  sig    () -> Int
  effects {}
  cand
    double("hello")
"""
        with self.assertRaises(TypeViolation) as ctx:
            _run(src)
        self.assertIn("n", str(ctx.exception))
        self.assertIn("Int", str(ctx.exception))
        self.assertIn("String", str(ctx.exception))

    def test_string_param_accepts_string(self):
        src = """
def shout
  intent "uppercase a string"
  sig    (s: String) -> String
  effects {}
  cand
    upper(s)

def main
  intent "test"
  sig    () -> String
  effects {}
  cand
    shout("hello")
"""
        self.assertEqual(_run(src), "HELLO")

    def test_string_param_rejects_int(self):
        src = """
def shout
  intent "uppercase a string"
  sig    (s: String) -> String
  effects {}
  cand
    upper(s)

def main
  intent "test"
  sig    () -> String
  effects {}
  cand
    shout(42)
"""
        with self.assertRaises(TypeViolation) as ctx:
            _run(src)
        self.assertIn("String", str(ctx.exception))

    def test_bool_param_accepts_bool(self):
        src = """
def negate
  intent "negate a bool"
  sig    (b: Bool) -> Bool
  effects {}
  cand
    not(b)

def main
  intent "test"
  sig    () -> Bool
  effects {}
  cand
    negate(eq(1, 1))
"""
        self.assertEqual(_run(src), False)

    def test_list_param_accepts_list(self):
        src = """
def count
  intent "count items"
  sig    (xs: List) -> Int
  effects {}
  cand
    len(xs)

def main
  intent "test"
  sig    () -> Int
  effects {}
  cand
    count(list(1, 2, 3))
"""
        self.assertEqual(_run(src), 3)

    def test_list_param_rejects_string(self):
        src = """
def count
  intent "count items"
  sig    (xs: List) -> Int
  effects {}
  cand
    len(xs)

def main
  intent "test"
  sig    () -> Int
  effects {}
  cand
    count("not a list")
"""
        with self.assertRaises(TypeViolation) as ctx:
            _run(src)
        self.assertIn("List", str(ctx.exception))


class NumberSupertypeTests(unittest.TestCase):
    """Number is the supertype of Int and Float."""

    def test_number_param_accepts_int(self):
        src = """
def double
  intent "double a number"
  sig    (n: Number) -> Number
  effects {}
  cand
    mul(n, 2)

def main
  intent "test"
  sig    () -> Number
  effects {}
  cand
    double(21)
"""
        self.assertEqual(_run(src), 42)

    def test_number_param_accepts_float(self):
        src = """
def half
  intent "halve a number"
  sig    (n: Number) -> Number
  effects {}
  cand
    div(n, 2)

def main
  intent "test"
  sig    () -> Number
  effects {}
  cand
    half(3.14)
"""
        result = _run(src)
        self.assertAlmostEqual(result, 1.57, places=5)

    def test_int_param_accepts_number_typed_value(self):
        """A value tagged Number (from add/sub/mul) is accepted where Int is declared."""
        src = """
def use_int
  intent "use an int"
  sig    (n: Int) -> Int
  effects {}
  cand
    n

def main
  intent "test"
  sig    () -> Int
  effects {}
  cand
    use_int(add(20, 22))
"""
        # add returns Number-typed value; should be accepted for Int param
        self.assertEqual(_run(src), 42)


class AnyTypeTests(unittest.TestCase):
    """Any declared type accepts all values. Any actual type passes all checks."""

    def test_any_param_accepts_string(self):
        src = """
def identity
  intent "return any value"
  sig    (x: Any) -> Any
  effects {}
  cand
    x

def main
  intent "test"
  sig    () -> Any
  effects {}
  cand
    identity("hello")
"""
        self.assertEqual(_run(src), "hello")

    def test_any_param_accepts_int(self):
        src = """
def identity
  intent "return any value"
  sig    (x: Any) -> Any
  effects {}
  cand
    x

def main
  intent "test"
  sig    () -> Any
  effects {}
  cand
    identity(42)
"""
        self.assertEqual(_run(src), 42)

    def test_any_param_accepts_list(self):
        src = """
def identity
  intent "return any value"
  sig    (x: Any) -> Any
  effects {}
  cand
    x

def main
  intent "test"
  sig    () -> Any
  effects {}
  cand
    identity(list(1, 2, 3))
"""
        self.assertEqual(_run(src), [1, 2, 3])


class ReturnTypeEnforcement(unittest.TestCase):
    """Type checking on return values."""

    def test_return_type_violation_message_format(self):
        """TypeViolation message names fn, param, expected, actual."""
        src = """
def bad_return
  intent "return wrong type"
  sig    (n: Int) -> String
  effects {}
  cand
    n

def main
  intent "test"
  sig    () -> String
  effects {}
  cand
    bad_return(42)
"""
        with self.assertRaises(TypeViolation) as ctx:
            _run(src)
        msg = str(ctx.exception)
        self.assertIn("bad_return", msg)
        self.assertIn("<return>", msg)
        self.assertIn("String", msg)

    def test_correct_return_type_passes(self):
        src = """
def greet
  intent "greet"
  sig    (name: String) -> String
  effects {}
  cand
    "hello " ++ name

def main
  intent "test"
  sig    () -> String
  effects {}
  cand
    greet("world")
"""
        self.assertEqual(_run(src), "hello world")


class TypeViolationErrorShape(unittest.TestCase):
    """TypeViolation carries structured fields."""

    def test_fields_are_set(self):
        src = """
def typed
  intent "typed fn"
  sig    (n: Int) -> Int
  effects {}
  cand
    n

def main
  intent "test"
  sig    () -> Int
  effects {}
  cand
    typed("oops")
"""
        with self.assertRaises(TypeViolation) as ctx:
            _run(src)
        exc = ctx.exception
        self.assertEqual(exc.fn, "typed")
        self.assertEqual(exc.param, "n")
        self.assertEqual(exc.expected, "Int")
        self.assertEqual(exc.actual, "String")
        self.assertIn("oops", exc.value_repr)


if __name__ == "__main__":
    unittest.main()
