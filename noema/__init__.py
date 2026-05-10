"""Noema: a programming language for agentic AI.

Public API:
    parse(source: str) -> Module
    run(module: Module, entry: str = "main") -> Value
    to_canonical(module: Module) -> dict
    from_canonical(obj: dict) -> Module
"""
from .core.types import (
    Module,
    Definition,
    Candidate,
    Signature,
    Param,
    Value,
    Belief,
    Bottom,
    EffectSet,
)
from .parser.parser import parse
from .projection.canonical import to_canonical, from_canonical
from .runtime.interpreter import run, Interpreter
from .runtime.errors import (
    NoemaError,
    ParseError,
    EffectViolation,
    ContractViolation,
    RefusalError,
    DispatchError,
)

__version__ = "0.1.0"

__all__ = [
    "Module",
    "Definition",
    "Candidate",
    "Signature",
    "Param",
    "Value",
    "Belief",
    "Bottom",
    "EffectSet",
    "parse",
    "run",
    "Interpreter",
    "to_canonical",
    "from_canonical",
    "NoemaError",
    "ParseError",
    "EffectViolation",
    "ContractViolation",
    "RefusalError",
    "DispatchError",
]
