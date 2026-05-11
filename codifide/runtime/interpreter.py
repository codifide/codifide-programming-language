"""Codifide tree-walking interpreter.

Responsibilities:
    1. Evaluate expressions to Codifide values.
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
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..store import SymbolStore

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
    CodifideError,
    BottomPropagationError,
    PrimitiveError,
    RecursionLimitError,
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


def run(
    module: Module,
    entry: str = "main",
    args: Optional[List[Any]] = None,
    *,
    store: Optional["SymbolStore"] = None,
) -> Any:
    """Run a Codifide module starting from an entry definition.

    Returns the payload of the entry's result (unwrapped from Value for the
    host's convenience). Raises a CodifideError subclass on any violation.

    A module-level static check runs before execution: every user-defined
    callee's declared effects must be a subset of every caller's declared
    effects. This is the transitive half of the effect algebra
    (`docs/CANONICAL.md §Effect algebra`). Without it, a pure function can
    launder effects through an impure callee, which would make the
    language's central soundness claim false.

    If the module has imports, ``store`` is required so the interpreter
    can resolve them. Imports are bound by content identity; the same
    identity resolves to the same definition every time, which is the
    property content addressing exists to provide.
    """
    # Lazy import to avoid a cycle: store -> canonical -> core.types is
    # fine, but runtime -> store -> ... at import time would pull in
    # store-level symbols before the runtime module is fully defined
    # during some test discovery orderings.
    from ..store import SymbolStore as _SymbolStore  # noqa: F401

    resolved = _ResolvedImports.from_module(module, store)
    _check_transitive_effects(module, resolved)
    interp = Interpreter(module, imports=resolved)
    try:
        return interp.invoke(entry, args or [])
    except RecursionError as exc:
        # Defense in depth. The Interpreter.max_depth bound should trip
        # first; if Python's own stack limit wins the race, map it back
        # to a typed Codifide error so the host never sees a bare
        # RecursionError.
        raise RecursionLimitError(interp.max_depth) from exc


def _check_transitive_effects(
    module: Module,
    resolved: "_ResolvedImports",
) -> None:
    """Verify callee-effects ⊆ caller-effects across the whole call graph.

    For every definition ``d`` and every user-function call site ``c`` in
    any expression reachable from any candidate body, guard, precondition,
    or postcondition of ``d``, the callee's declared effect set must be a
    subset of ``d``'s declared effect set. This is a static pass — it runs
    once per module and rejects ill-typed modules before any code executes.

    Imports participate in the check the same way local definitions do:
    an imported callee's declared effects (recovered from its canonical
    JSON in the store) must be a subset of the caller's declared effects.
    The store and content hashes are what make this sound — an imported
    symbol cannot lie about its effect set without changing its identity.

    Why a static pass rather than a call-site runtime check: errors here
    are authoring mistakes, not execution-time accidents. Surfacing them
    before dispatch makes the failure mode the same whether the bug is on
    a cold path or a hot one.
    """
    for caller in module.symbols:
        caller_effects = caller.signature.effects
        for expr in _all_exprs_of(caller):
            for call_fn in _call_targets(expr):
                callee = module.lookup(call_fn)
                if callee is not None:
                    callee_effects = callee.signature.effects
                elif resolved.has(call_fn):
                    callee_effects = resolved.effects_of(call_fn)
                else:
                    # Not a user function and not an import; primitive-call
                    # effect checking happens at runtime in _call_primitive.
                    continue
                missing = callee_effects - caller_effects
                if missing:
                    # Report against the caller — it promised something it
                    # cannot deliver on without the callee's effect budget.
                    raise EffectViolation(
                        fn=caller.name,
                        declared=caller_effects,
                        observed=sorted(missing)[0],
                    )


def _all_exprs_of(defn: Definition):
    """Yield every expression node reachable from a definition.

    Order does not matter for the subset check; we just need completeness.
    """
    for clause in defn.pre:
        yield from _walk(clause)
    for clause in defn.post:
        yield from _walk(clause)
    for cand in defn.candidates:
        if cand.guard is not None:
            yield from _walk(cand.guard)
        yield from _walk(cand.body)


def _walk(expr: Expr):
    yield expr
    if isinstance(expr, Call):
        for a in expr.args:
            yield from _walk(a)
    elif isinstance(expr, Bind):
        yield from _walk(expr.expr)
        yield from _walk(expr.body)
    elif isinstance(expr, Seq):
        for s in expr.steps:
            yield from _walk(s)
    elif isinstance(expr, Concat):
        for p in expr.parts:
            yield from _walk(p)
    elif isinstance(expr, Believe):
        yield from _walk(expr.subject)
        for c, v in expr.arms:
            yield from _walk(c)
            yield from _walk(v)
        yield from _walk(expr.otherwise)
    elif isinstance(expr, Attr):
        yield from _walk(expr.target)


def _call_targets(expr: Expr):
    """Every user-callable name invoked in this subtree.

    We yield the ``fn`` name of every ``Call`` node. The transitive check
    resolves these names against the module; primitives are simply absent
    from the module's symbols and are skipped.
    """
    if isinstance(expr, Call):
        yield expr.fn


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
    # When set, overrides the signature's declared effect set for primitive
    # checking. Used during contract (pre/post/guard) evaluation to enforce
    # contract purity: contracts describe state, they do not modify it.
    effect_budget: Optional[frozenset] = None


class _ResolvedImports:
    """Imports resolved from identities to full Definitions via the store.

    Resolution happens once at module load, not per call site. Two benefits:

    1. A module with unreachable imports fails fast (before any body runs)
       if the store cannot serve the identity. Late binding would surface
       the same error at a random call site, which is harder to diagnose.
    2. Effect-subset checking can treat imported symbols uniformly with
       local ones.

    An imported symbol's canonical JSON lives in the store keyed by its
    content identity. Loading it round-trips the canonical form back into
    a Definition — the same type local `def`s produce.
    """

    def __init__(self, bindings: Dict[str, Definition]) -> None:
        self._bindings = bindings

    @classmethod
    def empty(cls) -> "_ResolvedImports":
        return cls({})

    @classmethod
    def from_module(
        cls, module: Module, store: Optional["SymbolStore"]
    ) -> "_ResolvedImports":
        if not module.imports:
            return cls.empty()
        if store is None:
            raise CodifideError(
                f"module {module.name!r} has imports but no store was "
                f"provided to resolve them. Pass `store=` to run()."
            )
        bindings: Dict[str, Definition] = {}
        # Lazy imports to avoid cycles.
        from ..projection.canonical import from_canonical

        for local_name, identity in module.imports:
            try:
                obj = store.get(identity)
            except Exception as exc:  # StoreError, NotFound, IntegrityError
                raise CodifideError(
                    f"cannot resolve import {local_name!r} = {identity}: {exc}"
                ) from exc
            # The canonical form for a single symbol is a module envelope
            # (`module.symbols` has one key). Unwrap it to a Definition.
            imported_module = from_canonical(obj)
            if len(imported_module.symbols) != 1:
                raise CodifideError(
                    f"import {identity} does not resolve to a single "
                    f"symbol (found {len(imported_module.symbols)})"
                )
            bindings[local_name] = imported_module.symbols[0]
        return cls(bindings)

    def has(self, name: str) -> bool:
        return name in self._bindings

    def lookup(self, name: str) -> Optional[Definition]:
        return self._bindings.get(name)

    def effects_of(self, name: str) -> frozenset:
        """Effect set of an imported symbol, for the transitive check."""
        defn = self._bindings.get(name)
        if defn is None:
            return frozenset()
        return defn.signature.effects


class Interpreter:
    # Default maximum Codifide call depth. A Codifide program is untrusted input
    # to the host; this bound keeps pathological modules from exhausting
    # the Python stack. Default is conservative because each Codifide frame
    # costs roughly 5 Python frames; 64 keeps us well below Python's
    # default recursion limit of 1000 even with future parser/runtime
    # changes that add stack cost.
    DEFAULT_MAX_DEPTH = 64

    def __init__(
        self,
        module: Module,
        *,
        max_depth: int = DEFAULT_MAX_DEPTH,
        imports: Optional["_ResolvedImports"] = None,
    ) -> None:
        self.module = module
        self.max_depth = max_depth
        self._depth = 0
        self.imports = imports if imports is not None else _ResolvedImports.empty()
        # Intent chain: a live stack of (fn, intent) tuples, innermost
        # frame first. Populated as we enter/leave definitions so error
        # messages can walk the intent graph — "the function exists
        # because: ..." at every level. Roadmap v0.1 item.
        self._intent_chain: List[tuple[str, str]] = []

    # -- Invocation ------------------------------------------------------

    def invoke(self, name: str, args: List[Any]) -> Any:
        defn = self.module.lookup(name)
        if defn is None:
            raise CodifideError(f"no such definition: {name!r}")
        self._push_depth()
        self._intent_chain.append((defn.name, defn.intent))
        try:
            trace = EffectTrace.fresh()
            prims = build_default_registry(trace)

            # Bind parameters. Incoming args may be plain Python values; lift them
            # into Codifide Values so the provenance trail stays honest.
            locals_: Dict[str, Any] = {}
            for i, p in enumerate(defn.signature.params):
                v = args[i] if i < len(args) else None
                if not isinstance(v, (Value, Belief)):
                    v = Value(payload=v, type=p.type, provenance=("argument",))
                locals_[p.name] = v

            frame = _Frame(defn=defn, locals=locals_, trace=trace, prims=prims)

            # Preconditions (evaluated with pure effect budget).
            pure_frame = _with_pure_budget(frame)
            for clause in defn.pre:
                if not self._truthy(self._eval(clause, pure_frame)):
                    raise ContractViolation(
                        fn=defn.name,
                        kind="pre",
                        clause=_describe(clause),
                        intent=defn.intent,
                        intent_chain=list(self._intent_chain),
                    )

            # Dispatch over candidates.
            result = self._dispatch(defn, frame)

            # Postconditions (skipped on refusal — a function that chose to abstain
            # does not have to deliver on downstream guarantees).
            if result is not Bottom:
                for clause in defn.post:
                    frame.locals["result"] = _as_value(result)
                    post_frame = _with_pure_budget(frame)
                    if not self._truthy(self._eval(clause, post_frame)):
                        raise ContractViolation(
                            fn=defn.name,
                            kind="post",
                            clause=_describe(clause),
                            intent=defn.intent,
                            intent_chain=list(self._intent_chain),
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
        finally:
            self._intent_chain.pop()
            self._pop_depth()

    def _push_depth(self) -> None:
        if self._depth >= self.max_depth:
            raise RecursionLimitError(self.max_depth)
        # Defense in depth: if the Python stack exceeds its own recursion
        # limit before our Codifide counter trips, map that back to a typed
        # Codifide error so hosts never see a bare RecursionError.
        self._depth += 1

    def _pop_depth(self) -> None:
        self._depth -= 1

    def _pop_depth(self) -> None:
        self._depth -= 1

    def _dispatch(self, defn: Definition, frame: _Frame) -> Any:
        # Guards, like pre/post, are contract expressions and run pure.
        pure_frame = _with_pure_budget(frame)
        for cand in defn.candidates:
            if cand.guard is None or self._truthy(self._eval(cand.guard, pure_frame)):
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
            raise CodifideError(f"unbound name: {expr.name!r}")
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
            raise CodifideError(
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
        raise CodifideError(f"cannot evaluate {type(expr).__name__}")

    # -- Call plumbing ---------------------------------------------------

    def _call(self, fn: str, arg_exprs: tuple, frame: _Frame) -> Any:
        # User-defined function in this module first.
        defn = self.module.lookup(fn)
        if defn is not None:
            vals = [self._eval(a, frame) for a in arg_exprs]
            return self._invoke_internal(defn, vals, frame.trace, frame.prims)
        # Imported symbol next. Imports are resolved to full Definitions
        # via the symbol store at module-load time, so call semantics are
        # identical to a local def: same effect check, same contract
        # discipline, same candidate dispatch. The local name bound by
        # the `import` declaration is the one the body sees here.
        imported = self.imports.lookup(fn)
        if imported is not None:
            vals = [self._eval(a, frame) for a in arg_exprs]
            return self._invoke_internal(imported, vals, frame.trace, frame.prims)
        # Primitive.
        if frame.prims.has(fn):
            return self._call_primitive(fn, arg_exprs, frame)
        raise CodifideError(f"unknown callable: {fn!r}")

    def _call_primitive(self, name: str, arg_exprs: tuple, frame: _Frame) -> Any:
        spec = frame.prims.get(name)
        # Contract evaluation runs with an effect budget of ∅: contracts
        # describe state, they do not modify it. During normal body
        # evaluation ``effect_budget`` is None and the signature applies.
        allowed = (
            frame.effect_budget
            if frame.effect_budget is not None
            else frame.defn.signature.effects
        )
        if spec.effect is not None and spec.effect not in allowed:
            raise EffectViolation(
                fn=frame.defn.name,
                declared=allowed,
                observed=spec.effect,
                intent_chain=list(self._intent_chain),
            )
        args = [self._eval(a, frame) for a in arg_exprs]
        # Refusal propagation: primitives should not have to cope with ⊥ as
        # an argument. A program that wants to compute over a possibly-refused
        # value must handle it explicitly in a `believe` arm. Without this
        # check, arithmetic on ⊥ surfaces as a host TypeError.
        for a in args:
            if a is Bottom:
                raise BottomPropagationError(fn=name)
        try:
            result = spec.fn(*args)
        except CodifideError:
            # Typed Codifide errors pass through — primitives that already
            # classify their failures should not be re-wrapped.
            raise
        except Exception as exc:
            # Wrap host exceptions in a typed Codifide error so hosts can
            # classify failures uniformly. Preserves the original via
            # `raise ... from exc`.
            raise PrimitiveError(fn=name, args=args, cause=exc) from exc
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
        # Transitive effect subset is checked statically at module-load time
        # in ``_check_transitive_effects``; call-site runtime checks are
        # unnecessary here.
        self._push_depth()
        self._intent_chain.append((defn.name, defn.intent))
        try:
            locals_: Dict[str, Any] = {}
            for i, p in enumerate(defn.signature.params):
                v = args[i] if i < len(args) else None
                if not isinstance(v, (Value, Belief)):
                    v = Value(payload=v, type=p.type, provenance=("argument",))
                locals_[p.name] = v
            # New primitive registry bound to the SAME trace so io accumulates.
            prims = build_default_registry(parent_trace)
            frame = _Frame(defn=defn, locals=locals_, trace=parent_trace, prims=prims)
            pure_frame = _with_pure_budget(frame)
            for clause in defn.pre:
                if not self._truthy(self._eval(clause, pure_frame)):
                    raise ContractViolation(
                        fn=defn.name, kind="pre",
                        clause=_describe(clause), intent=defn.intent,
                        intent_chain=list(self._intent_chain),
                    )
            result = self._dispatch(defn, frame)
            if result is not Bottom:
                for clause in defn.post:
                    frame.locals["result"] = _as_value(result)
                    post_frame = _with_pure_budget(frame)
                    if not self._truthy(self._eval(clause, post_frame)):
                        raise ContractViolation(
                            fn=defn.name, kind="post",
                            clause=_describe(clause), intent=defn.intent,
                            intent_chain=list(self._intent_chain),
                        )
            return result
        finally:
            self._intent_chain.pop()
            self._pop_depth()

    # -- small utility ---------------------------------------------------

    def _truthy(self, v: Any) -> bool:
        if v is Bottom:
            return False
        return bool(_unwrap(v))


def _replace_locals(frame: _Frame, new_locals: Dict[str, Any]) -> _Frame:
    return _Frame(
        defn=frame.defn,
        locals=new_locals,
        trace=frame.trace,
        prims=frame.prims,
        effect_budget=frame.effect_budget,
    )


def _with_pure_budget(frame: _Frame) -> _Frame:
    """Return a frame that forbids all effects during contract evaluation.

    Security audit P2-1: pre/post/guard clauses should not be able to
    perform side effects. Overriding the effect budget for the duration of
    contract evaluation enforces this without changing the signature.
    """
    return _Frame(
        defn=frame.defn,
        locals=frame.locals,
        trace=frame.trace,
        prims=frame.prims,
        effect_budget=frozenset(),
    )


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
