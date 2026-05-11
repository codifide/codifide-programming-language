"""Codifide: a programming language for agentic AI.

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
from .projection.canonical import (
    to_canonical,
    from_canonical,
    canonical_bytes,
    canonical_cbor_bytes,
    content_hash,
    content_hash_cbor,
)
from .runtime.interpreter import run, Interpreter
from .store import (
    IntegrityError,
    NotFound,
    StoreError,
    SymbolStore,
    symbol_bytes,
    symbol_hash,
)
from .runtime.errors import (
    CodifideError,
    ParseError,
    EffectViolation,
    ContractViolation,
    RefusalError,
    DispatchError,
    RecursionLimitError,
    PrimitiveError,
    BottomPropagationError,
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
    "canonical_bytes",
    "canonical_cbor_bytes",
    "content_hash",
    "content_hash_cbor",
    "CodifideError",
    "ParseError",
    "EffectViolation",
    "ContractViolation",
    "RefusalError",
    "DispatchError",
    "RecursionLimitError",
    "PrimitiveError",
    "BottomPropagationError",
    "SymbolStore",
    "symbol_bytes",
    "symbol_hash",
    "StoreError",
    "NotFound",
    "IntegrityError",
]
