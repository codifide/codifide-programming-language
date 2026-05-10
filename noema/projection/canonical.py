"""Canonical JSON projection.

Noema canonical form is a typed hypergraph. JSON is the v0 serialization; CBOR
and content-addressing will arrive later. Round-tripping is total: any Module
parsed, projected to JSON, and read back is structurally identical.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..core.types import (
    Attr,
    Believe,
    Bind,
    BottomExpr,
    Call,
    Candidate,
    Concat,
    Definition,
    Expr,
    Lit,
    Module,
    Param,
    Ref,
    Seq,
    Signature,
)

NOEMA_SCHEMA_VERSION = "0.1"


def to_canonical(module: Module) -> Dict[str, Any]:
    return {
        "noema": NOEMA_SCHEMA_VERSION,
        "module": module.name,
        "symbols": {d.name: _def_to_json(d) for d in module.symbols},
    }


def from_canonical(obj: Dict[str, Any]) -> Module:
    if obj.get("noema") != NOEMA_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported Noema schema version: {obj.get('noema')!r}"
        )
    name = obj.get("module", "main")
    syms = obj.get("symbols", {})
    defs = tuple(_def_from_json(dn, dv) for dn, dv in syms.items())
    return Module(name=name, symbols=defs)


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------


def _def_to_json(d: Definition) -> Dict[str, Any]:
    return {
        "kind": "definition",
        "intent": d.intent,
        "signature": _sig_to_json(d.signature),
        "pre": [_expr_to_json(e) for e in d.pre],
        "post": [_expr_to_json(e) for e in d.post],
        "candidates": [_cand_to_json(c) for c in d.candidates],
    }


def _def_from_json(name: str, obj: Dict[str, Any]) -> Definition:
    return Definition(
        name=name,
        intent=obj["intent"],
        signature=_sig_from_json(obj.get("signature", {})),
        pre=tuple(_expr_from_json(e) for e in obj.get("pre", [])),
        post=tuple(_expr_from_json(e) for e in obj.get("post", [])),
        candidates=tuple(_cand_from_json(c) for c in obj.get("candidates", [])),
    )


def _sig_to_json(s: Signature) -> Dict[str, Any]:
    return {
        "params": [{"name": p.name, "type": p.type} for p in s.params],
        "returns": s.returns,
        "effects": sorted(s.effects),
    }


def _sig_from_json(obj: Dict[str, Any]) -> Signature:
    return Signature(
        params=tuple(Param(name=p["name"], type=p.get("type", "Any"))
                     for p in obj.get("params", [])),
        returns=obj.get("returns", "Any"),
        effects=frozenset(obj.get("effects", [])),
    )


def _cand_to_json(c: Candidate) -> Dict[str, Any]:
    return {
        "kind": "candidate",
        "intent": c.intent,
        "guard": _expr_to_json(c.guard) if c.guard is not None else None,
        "body": _expr_to_json(c.body),
    }


def _cand_from_json(obj: Dict[str, Any]) -> Candidate:
    guard = obj.get("guard")
    return Candidate(
        body=_expr_from_json(obj["body"]),
        intent=obj.get("intent", "default"),
        guard=_expr_from_json(guard) if guard is not None else None,
    )


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


def _expr_to_json(e: Expr) -> Dict[str, Any]:
    if isinstance(e, Lit):
        return {
            "kind": "lit",
            "value": e.value,
            "type": e.type,
            "conf": e.conf,
            "provenance": e.provenance,
        }
    if isinstance(e, Ref):
        return {"kind": "ref", "name": e.name}
    if isinstance(e, Call):
        return {
            "kind": "call",
            "fn": e.fn,
            "args": [_expr_to_json(a) for a in e.args],
        }
    if isinstance(e, Bind):
        return {
            "kind": "bind",
            "name": e.name,
            "expr": _expr_to_json(e.expr),
            "in": _expr_to_json(e.body),
        }
    if isinstance(e, Seq):
        return {"kind": "seq", "steps": [_expr_to_json(s) for s in e.steps]}
    if isinstance(e, Believe):
        return {
            "kind": "believe",
            "subject": _expr_to_json(e.subject),
            "arms": [[_expr_to_json(c), _expr_to_json(v)] for c, v in e.arms],
            "else": _expr_to_json(e.otherwise),
        }
    if isinstance(e, BottomExpr):
        return {"kind": "bottom"}
    if isinstance(e, Concat):
        return {"kind": "concat", "parts": [_expr_to_json(p) for p in e.parts]}
    if isinstance(e, Attr):
        return {"kind": "attr", "target": _expr_to_json(e.target), "name": e.name}
    raise TypeError(f"cannot serialize expression: {type(e).__name__}")


def _expr_from_json(obj: Dict[str, Any]) -> Expr:
    k = obj.get("kind")
    if k == "lit":
        return Lit(
            value=obj["value"],
            type=obj.get("type", "Any"),
            conf=obj.get("conf", 1.0),
            provenance=obj.get("provenance", "literal"),
        )
    if k == "ref":
        return Ref(obj["name"])
    if k == "call":
        return Call(obj["fn"], tuple(_expr_from_json(a) for a in obj.get("args", [])))
    if k == "bind":
        return Bind(
            name=obj["name"],
            expr=_expr_from_json(obj["expr"]),
            body=_expr_from_json(obj["in"]),
        )
    if k == "seq":
        return Seq(steps=tuple(_expr_from_json(s) for s in obj["steps"]))
    if k == "believe":
        return Believe(
            subject=_expr_from_json(obj["subject"]),
            arms=tuple(
                (_expr_from_json(c), _expr_from_json(v))
                for c, v in obj.get("arms", [])
            ),
            otherwise=_expr_from_json(obj["else"]),
        )
    if k == "bottom":
        return BottomExpr()
    if k == "concat":
        return Concat(parts=tuple(_expr_from_json(p) for p in obj.get("parts", [])))
    if k == "attr":
        return Attr(target=_expr_from_json(obj["target"]), name=obj["name"])
    raise ValueError(f"unknown expression kind: {k!r}")
