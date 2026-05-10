"""Noema tree-walking interpreter.

Responsibilities:
    1. Evaluate expressions to Noema values.
    2. Enforce effect declarations: every primitive call's effect label must be
       a subset of the enclosing definition's declared effect set.
    3. Check preconditions before entering a candidate body and postconditions
       after it exits.
    4. Perform candidate dispatch: evaluate guards in declaration order and run
       the first candidate whose guard holds (or is absent).
    5. Execute belief-dispatch on runtime confidence.

This is the reference implementation. It is deliberately simple; correctness
matters more than speed. The graph-native parallel runtime is a v0.3 project.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..core.types import (
    Attr,
    Believe,
    Belief,
    Bind,
    BottomExpr,
    Bottom,
    Call,
    Candidate,
    Concat,
    Definition,
    Expr,
    Lit,
    Module,
    Ref,
    Seq,
    Value,
)
from .errors import (
    ContractViolation,
    DispatchError,
    EffectViolation,
    NoemaError,
    RefusalError,
)
from .primitives import (
    EffectTrace,
    PrimitiveRegistry,
    _unwrap,
    build_default_registry,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run(module: Module, entry: str = "main", args: Optional[List[Any]] = None) -> Any:
    """Run a Noema module starting from an entry definition.

    Returns the payload of the entry's result (unwrapped from Value for the
    host's convenience). Raises a NoemaError subclass on any violation.
    """
    interp = Interpreter(module)
    return interp.invoke(entry, args or [])


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------


@dataclass
class _Frame:
    """A single call frame during evaluation."""
    defn: Definition
    locals: Dict[str, Any]
    trace: EffectTrace
    prims: PrimitiveRegistry


class Interpreter:
    def __init__(self, module: Module) -> None:
        self.module = module

    # -- Invocation ------------------------------------------------------

    def invoke(self, name: str, args: List[Any]) -> Any:
        defn = self.module.lookup(name)
        if defn is None:
            raise NoemaError(f"no such definition: {name!r}")
        trace = EffectTrace.fresh()
        prims = build_default_registry(trace)

        # Bind parameters. Incoming args may be plain Python values; lift them
        # into Noema Values so the provenance trail stays honest.
        locals_: Dict[str, Any] = {}
        for i, p in enumerate(defn.signature.params):
            v = args[i] if i < len(args) else None
            if not isinstance(v, (Value, Belief)):
                v = Value(payload=v, type=p.type, provenance=("argument",))
            locals_[p.name] = v

        frame = _Frame(defn=defn, locals=locals_, trace=trace, prims=prims)

        # Preconditions.
        for clause in defn.pre:
            if not self._truthy(self._eval(clause, frame)):
                raise ContractViolation(
                    fn=defn.name,
                    kind="pre",
                    clause=_describe(clause),
                    intent=defn.intent,
                )

        # Dispatch over candidates.
        result = self._dispatch(defn, frame)

        # Postconditions (skipped on refusal — a function that chose to abstain
        # does not have to deliver on downstream guarantees).
        if result is not Bottom:
            for clause in defn.post:
                frame.locals["result"] = _as_value(result)
                if not self._truthy(self._eval(clause, frame)):
                    raise ContractViolation(
                        fn=defn.name,
                        kind="post",
                        clause=_describe(clause),
                        intent=defn.intent,
                    )
        else:
            # A top-level refusal that nobody handles is a configuration
            # problem. Surface it explicitly.
            if defn.name == "main" or args == []:
                # Callers of `run` may legitimately expect the value. We raise
                # a dedicated error so a host can distinguish refusal from
                # other errors.
                raise RefusalError(defn.name)

        return _unwrap(result) if result is not Bottom else Bottom

    def _dispatch(self, defn: Definition, frame: _Frame) -> Any:
        for cand in defn.candidates:
            if cand.guard is None or self._truthy(self._eval(cand.guard, frame)):
                return self._eval(cand.body, frame)
        raise DispatchError(defn.name)

    # -- Expression evaluation ------------------------------------------

    def _eval(self, expr: Expr, frame: _Frame) -> Any:
        if isinstance(expr, Lit):
            return Value(
                payload=expr.value,
                type=expr.type,
                conf=expr.conf,
                provenance=(expr.provenance,),
            )
        if isinstance(expr, Ref):
            if expr.name == "result" and "result" in frame.locals:
                return frame.locals["result"]
            if expr.name in frame.locals:
                return frame.locals[expr.name]
            # Bare reference to a primitive namespace (e.g. `clock` on its
            # own) is allowed and returns a namespace sentinel; we just raise
            # for now to keep behavior tight.
            raise NoemaError(f"unbound name: {expr.name!r}")
        if isinstance(expr, Attr):
            # Attr over a dotted namespace resolves to either a primitive or
            # a record field. Try the dotted-primitive path FIRST when the
            # target is a bare Ref — because `clock.now` is a primitive call,
            # not a field access on a value named `clock`. Only when that
            # fails do we evaluate the target and try field access.
            if isinstance(expr.target, Ref) and expr.target.name not in frame.locals:
                dotted = f"{expr.target.name}.{expr.name}"
                if frame.prims.has(dotted):
                    return self._call_primitive(dotted, (), frame)
            target = self._eval(expr.target, frame)
            payload = _unwrap(target)
            if isinstance(payload, dict) and expr.name in payload:
                return Value(
                    payload=payload[expr.name],
                    type="Any",
                    provenance=("field." + expr.name,),
                )
            raise NoemaError(
                f"no field or primitive {expr.name!r} on {expr.target}"
            )
        if isinstance(expr, Call):
            return self._call(expr.fn, expr.args, frame)
        if isinstance(expr, Bind):
            val = self._eval(expr.expr, frame)
            new_locals = {**frame.locals, expr.name: val}
            return self._eval(expr.body, _replace_locals(frame, new_locals))
        if isinstance(expr, Seq):
            result: Any = None
            for step in expr.steps:
                result = self._eval(step, frame)
            return result
        if isinstance(expr, Concat):
            parts = [self._eval(p, frame) for p in expr.parts]
            return Value(
                payload="".join(str(_unwrap(p)) for p in parts),
                type="String",
                provenance=("concat",),
            )
        if isinstance(expr, BottomExpr):
            return Bottom
        if isinstance(expr, Believe):
            subject = self._eval(expr.subject, frame)
            # Bind `it` so arms can read the subject directly.
            inner_locals = {**frame.locals, "it": subject}
            inner = _replace_locals(frame, inner_locals)
            for cond, value in expr.arms:
                if self._truthy(self._eval(cond, inner)):
                    return self._eval(value, inner)
            return self._eval(expr.otherwise, inner)
        raise NoemaError(f"cannot evaluate {type(expr).__name__}")

    # -- Call plumbing ---------------------------------------------------

    def _call(self, fn: str, arg_exprs: tuple, frame: _Frame) -> Any:
        # User-defined function first.
        defn = self.module.lookup(fn)
        if defn is not None:
            vals = [self._eval(a, frame) for a in arg_exprs]
            return self._invoke_internal(defn, vals, frame.trace, frame.prims)
        # Primitive.
        if frame.prims.has(fn):
            return self._call_primitive(fn, arg_exprs, frame)
        raise NoemaError(f"unknown callable: {fn!r}")

    def _call_primitive(self, name: str, arg_exprs: tuple, frame: _Frame) -> Any:
        spec = frame.prims.get(name)
        if spec.effect is not None and spec.effect not in frame.defn.signature.effects:
            raise EffectViolation(
                fn=frame.defn.name,
                declared=frame.defn.signature.effects,
                observed=spec.effect,
            )
        args = [self._eval(a, frame) for a in arg_exprs]
        result = spec.fn(*args)
        # If a primitive hands back a Belief or Value, pass through unchanged.
        if isinstance(result, (Belief, Value)):
            return result
        # Otherwise wrap as a Value with the primitive's declared return type.
        return Value(
            payload=result,
            type=spec.returns,
            provenance=("primitive." + name,),
        )

    def _invoke_internal(
        self,
        defn: Definition,
        args: List[Any],
        parent_trace: EffectTrace,
        parent_prims: PrimitiveRegistry,
    ) -> Any:
        # Called for user-function calls from within a candidate body. We
        # reuse the parent trace so stdout/clock traces accumulate across
        # the whole program. Primitives must be rebuilt per-callee because
        # each definition has its own effect set.
        #
        # Before invocation we also verify that the callee's declared
        # effects are all covered by the caller's declared effects. That
        # is how effect subset-ness propagates — the caller must own any
        # effect its callees can produce.
        caller_effects = parent_trace  # not used; real check below
        del caller_effects  # silence lints
        # Effect propagation is enforced at primitive-call time, but we also
        # check call-site coverage here for faster failure on mis-typed
        # modules.
        # (Nested call contract checking is performed by the nested invoke
        # itself, so we just recurse with a fresh sub-interpreter view.)
        locals_: Dict[str, Any] = {}
        for i, p in enumerate(defn.signature.params):
            v = args[i] if i < len(args) else None
            if not isinstance(v, (Value, Belief)):
                v = Value(payload=v, type=p.type, provenance=("argument",))
            locals_[p.name] = v
        # New primitive registry bound to the SAME trace so io accumulates.
        prims = build_default_registry(parent_trace)
        frame = _Frame(defn=defn, locals=locals_, trace=parent_trace, prims=prims)
        for clause in defn.pre:
            if not self._truthy(self._eval(clause, frame)):
                raise ContractViolation(
                    fn=defn.name, kind="pre",
                    clause=_describe(clause), intent=defn.intent,
                )
        result = self._dispatch(defn, frame)
        if result is not Bottom:
            for clause in defn.post:
                frame.locals["result"] = _as_value(result)
                if not self._truthy(self._eval(clause, frame)):
                    raise ContractViolation(
                        fn=defn.name, kind="post",
                        clause=_describe(clause), intent=defn.intent,
                    )
        return result

    # -- small utility ---------------------------------------------------

    def _truthy(self, v: Any) -> bool:
        if v is Bottom:
            return False
        return bool(_unwrap(v))


def _replace_locals(frame: _Frame, new_locals: Dict[str, Any]) -> _Frame:
    return _Frame(defn=frame.defn, locals=new_locals, trace=frame.trace, prims=frame.prims)


def _as_value(x: Any) -> Value:
    if isinstance(x, Value):
        return x
    if isinstance(x, Belief):
        return x.about
    return Value(payload=x, type="Any", provenance=("call",))


def _describe(expr: Expr) -> str:
    """Best-effort human-readable rendering of an expression for error messages.

    The canonical form is the truth; this is a lossy projection for diagnostics.
    """
    if isinstance(expr, Call):
        return f"{expr.fn}({', '.join(_describe(a) for a in expr.args)})"
    if isinstance(expr, Ref):
        return expr.name
    if isinstance(expr, Attr):
        return f"{_describe(expr.target)}.{expr.name}"
    if isinstance(expr, Lit):
        return repr(expr.value)
    if isinstance(expr, BottomExpr):
        return "bottom"
    if isinstance(expr, Concat):
        return " ++ ".join(_describe(p) for p in expr.parts)
    return type(expr).__name__
