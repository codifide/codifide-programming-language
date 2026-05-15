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
    BottomWithReason,
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
    symbol_bytes,           # primary = CBOR
    symbol_bytes_json,      # legacy JSON form
    symbol_hash,            # primary = CBOR hash
    symbol_hash_cbor,       # alias of symbol_hash
    symbol_hash_json,       # legacy JSON hash
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
    TypeViolation,
)

__version__ = "4.0.0"

__all__ = [
    "Module",
    "Definition",
    "Candidate",
    "Signature",
    "Param",
    "Value",
    "Belief",
    "Bottom",
    "BottomWithReason",
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
    "TypeViolation",
    "SymbolStore",
    "symbol_bytes",
    "symbol_bytes_json",
    "symbol_hash",
    "symbol_hash_cbor",
    "symbol_hash_json",
    "StoreError",
    "NotFound",
    "IntegrityError",
]
