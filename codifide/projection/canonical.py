"""Canonical JSON projection.

Codifide canonical form is a typed hypergraph. JSON is the v0 serialization; CBOR
is the v0.2 binary form (see ``codifide.projection.cbor``). Round-tripping is
total: any Module parsed, projected to JSON, and read back is structurally
identical.

This module also provides the *canonical byte form* — a deterministic byte
serialization of a Module that any two spec-conforming implementations must
agree on. The byte form is what content addressing hashes. See
`docs/CANONICAL.md §Canonical serialization` for the rules.
"""
from __future__ import annotations

import hashlib
import json
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
    If,
    Lit,
    Module,
    Param,
    Ref,
    Seq,
    Signature,
)

CODIFIDE_SCHEMA_VERSION = "0.1"


def to_canonical(module: Module) -> Dict[str, Any]:
    obj: Dict[str, Any] = {
        "codifide": CODIFIDE_SCHEMA_VERSION,
        "module": module.name,
        "symbols": {d.name: _def_to_json(d) for d in module.symbols},
    }
    # Imports are emitted only when present so modules without imports
    # produce the same canonical form they did before import support
    # landed. Keys are sorted so the in-memory canonical form matches
    # the canonical byte form (which sorts keys at every depth). Two
    # modules that differ only in import-declaration order produce
    # identical bytes and identical in-memory canonical dicts.
    if module.imports:
        sorted_imports = sorted(module.imports, key=lambda p: p[0])
        obj["imports"] = {name: identity for name, identity in sorted_imports}
    return obj


def from_canonical(obj: Dict[str, Any]) -> Module:
    if obj.get("codifide") != CODIFIDE_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported Codifide schema version: {obj.get('codifide')!r}"
        )
    name = obj.get("module", "main")
    syms = obj.get("symbols", {})
    defs = tuple(_def_from_json(dn, dv) for dn, dv in syms.items())
    imports_obj = obj.get("imports", {}) or {}
    # Restore imports in sorted order so from_canonical(to_canonical(m))
    # is a fixed point even for modules constructed with unsorted imports.
    imports = tuple(
        (name, identity) for name, identity in sorted(imports_obj.items())
    )
    return Module(name=name, symbols=defs, imports=imports)


def canonical_bytes_json(module: Module) -> bytes:
    """Deterministic JSON byte serialization of a Module.

    Legacy — pre-2026-05-11 this was the primary byte form. Callers
    that need the JSON form explicitly (human inspection, legacy-hash
    reconstruction) can call this. The primary byte form is CBOR; see
    :func:`canonical_bytes`.
    """
    obj = to_canonical(module)
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def canonical_bytes(module: Module) -> bytes:
    """Deterministic CBOR byte serialization of a Module.

    As of 2026-05-11, the primary byte form is CBOR (RFC 8949 §4.2
    deterministic encoding). This closes AUD-2026-05-11-08 — the JSON
    byte form cannot be made byte-equal across Python and Rust on
    f16-class floats because the two shortest-decimal writers produce
    different text for the same double.

    CBOR hashes over IEEE-754 bits and has no decimal-text
    intermediate. Two structurally-equal Modules produce identical
    bytes on every conforming implementation, full stop.
    """
    from .cbor import canonical_cbor

    return canonical_cbor(to_canonical(module))


def content_hash_json(module: Module) -> str:
    """SHA-256 of the legacy JSON canonical byte form.

    Preserved for callers that need to reproduce pre-migration
    identities. The primary identity function is :func:`content_hash`,
    which hashes over CBOR.
    """
    digest = hashlib.sha256(canonical_bytes_json(module)).hexdigest()
    return f"sha256:{digest}"


def content_hash(module: Module) -> str:
    """SHA-256 of the canonical CBOR byte form, hex-prefixed with `sha256:`.

    This is a Module's primary content identity. Stable across
    implementations because the CBOR byte form is deterministic under
    RFC 8949 §4.2.
    """
    digest = hashlib.sha256(canonical_bytes(module)).hexdigest()
    return f"sha256:{digest}"


def canonical_cbor_bytes(module: Module) -> bytes:
    """Deterministic CBOR byte serialization of a Module.

    Alias of :func:`canonical_bytes` post the 2026-05-11 migration —
    both return CBOR bytes. The explicit ``_cbor_bytes`` name is kept
    so callers that spell out their intent at the call site continue to
    work unchanged.
    """
    from .cbor import canonical_cbor

    return canonical_cbor(to_canonical(module))


def content_hash_cbor(module: Module) -> str:
    """SHA-256 of canonical CBOR bytes, hex-prefixed with `sha256:`.

    Alias of :func:`content_hash` post the 2026-05-11 migration —
    both hash over CBOR bytes. Kept as an explicit name for callers
    that want "this is the CBOR hash" obvious at the call site.
    """
    digest = hashlib.sha256(canonical_cbor_bytes(module)).hexdigest()
    return f"sha256:{digest}"


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
    obj: Dict[str, Any] = {
        "kind": "candidate",
        "intent": c.intent,
        "guard": _expr_to_json(c.guard) if c.guard is not None else None,
        "body": _expr_to_json(c.body),
    }
    # Only emit ``cost`` when present. This keeps the canonical bytes
    # of un-costed candidates identical to the pre-amendment form, so
    # no existing content hash is invalidated by the amendment. See
    # dispatches/2026-05-11-cost-based-dispatch-proposal.readout.md.
    if c.cost is not None:
        obj["cost"] = c.cost
    return obj


def _cand_from_json(obj: Dict[str, Any]) -> Candidate:
    guard = obj.get("guard")
    cost = obj.get("cost")
    # Canonical form typing: cost MUST be a non-negative integer when
    # present. A float or negative value is a spec violation and is
    # rejected by the Candidate constructor. The parser is responsible
    # for raising at parse time for the surface syntax; this branch
    # catches canonical input that slipped through a non-conforming
    # producer.
    if cost is not None and (
        not isinstance(cost, int)
        or isinstance(cost, bool)
        or cost < 0
    ):
        raise ValueError(
            f"canonical form: candidate.cost must be a non-negative integer, "
            f"got {cost!r}"
        )
    return Candidate(
        body=_expr_from_json(obj["body"]),
        intent=obj.get("intent", "default"),
        guard=_expr_from_json(guard) if guard is not None else None,
        cost=cost,
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
    if isinstance(e, If):
        return {
            "kind": "if",
            "cond": _expr_to_json(e.cond),
            "then": _expr_to_json(e.then_),
            "else": _expr_to_json(e.else_),
        }
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
    if k == "if":
        return If(
            cond=_expr_from_json(obj["cond"]),
            then_=_expr_from_json(obj["then"]),
            else_=_expr_from_json(obj["else"]),
        )
    raise ValueError(f"unknown expression kind: {k!r}")
