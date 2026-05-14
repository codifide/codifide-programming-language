"""Canonical types for Codifide.

The canonical form of a Codifide program is a typed hypergraph. These dataclasses
are the in-memory representation of that graph. Serialization to and from JSON
lives in codifide.projection.canonical.

Invariants enforced at construction time:
    - Every Definition has a non-empty intent string.
    - Every Candidate's guard is either None or an Expr.
    - EffectSet is always a frozenset of strings.
    - Values always carry type, confidence, and provenance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, FrozenSet, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Expression AST
# ---------------------------------------------------------------------------
# We model the AST as a tagged-union of dataclasses. Every node knows how to
# describe itself (`kind`) so the JSON projection is trivial and
# pattern-matching in the interpreter is exhaustive.


@dataclass(frozen=True)
class Lit:
    """A literal value lifted into the knowledge-graph form.

    In Codifide, every value carries more than its payload: a type label, a
    confidence in [0, 1], and a provenance tag. Literals default to confidence
    1.0 and provenance "literal" because that is the source of ground truth for
    written code.
    """
    value: Any
    type: str = "Any"
    conf: float = 1.0
    provenance: str = "literal"
    kind: str = field(default="lit", init=False)


@dataclass(frozen=True)
class Ref:
    """A reference to a bound name in the current environment."""
    name: str
    kind: str = field(default="ref", init=False)


@dataclass(frozen=True)
class Call:
    """A call to a named function, which may be a user definition or primitive."""
    fn: str
    args: Tuple["Expr", ...]
    kind: str = field(default="call", init=False)


@dataclass(frozen=True)
class Bind:
    """`name <- expr ; body` — introduces a local binding for the scope of body."""
    name: str
    expr: "Expr"
    body: "Expr"
    kind: str = field(default="bind", init=False)


@dataclass(frozen=True)
class Seq:
    """Sequential composition. Each step runs in order; the last value is the result.

    Present because v0 is still side-effect-ful. Once the dataflow runtime
    exists, most Seq nodes will be inferable from dependency edges.
    """
    steps: Tuple["Expr", ...]
    kind: str = field(default="seq", init=False)


@dataclass(frozen=True)
class Believe:
    """Belief dispatch. Arms are (condition, result) pairs evaluated top-to-bottom.

    The `subject` is bound to the name `it` inside each arm, so arms can read
    confidence and other metadata without re-computing the expression.
    """
    subject: "Expr"
    arms: Tuple[Tuple["Expr", "Expr"], ...]
    otherwise: "Expr"
    kind: str = field(default="believe", init=False)


@dataclass(frozen=True)
class BottomExpr:
    """First-class refusal. Callers must handle; it is not an exception.

    The optional ``reason`` field (added V3-3) carries a human-readable
    explanation of why the refusal occurred. It is purely informational:
    the runtime propagates it through ``RefusalError`` so callers can
    surface it in diagnostics, but it does not affect dispatch or
    canonical identity. Bare ``bottom`` (no reason) is backward-compatible
    — its canonical bytes are unchanged.
    """
    reason: Optional[str] = None
    kind: str = field(default="bottom", init=False)


@dataclass(frozen=True)
class Concat:
    """String concatenation, separated so we can keep the type static at `String`."""
    parts: Tuple["Expr", ...]
    kind: str = field(default="concat", init=False)


@dataclass(frozen=True)
class Attr:
    """Field access on a value that exposes a mapping-like interface.

    Primitive namespaces (e.g. `clock.now`) are also modeled as Attr nodes so
    that the parser and interpreter share one path for dotted names.
    """
    target: "Expr"
    name: str
    kind: str = field(default="attr", init=False)


@dataclass(frozen=True)
class If:
    """Inline conditional expression: ``if cond then a else b``.

    Added 2026-05-11 as a spec amendment. Unlike candidate dispatch
    guards — which all evaluate in one pass before selection —
    an ``If`` expression is **short-circuit**: exactly one of
    ``then_`` or ``else_`` evaluates at runtime. This matters when a
    branch would otherwise raise (e.g. indexing a string whose
    length was the condition's check).

    The condition is evaluated in the enclosing frame's effect
    budget. The chosen branch is evaluated in the same budget. If
    the ``If`` appears inside a guard or contract clause, the
    enclosing effect budget is ∅ (same rule as every other
    expression in a pure context).

    See ``dispatches/2026-05-11-inline-conditional-proposal.md``.
    """
    cond: "Expr"
    then_: "Expr"
    else_: "Expr"
    kind: str = field(default="if", init=False)


Expr = Union[Lit, Ref, Call, Bind, Seq, Believe, BottomExpr, Concat, Attr, If]


# ---------------------------------------------------------------------------
# Signatures, effects, definitions
# ---------------------------------------------------------------------------


EffectSet = FrozenSet[str]


@dataclass(frozen=True)
class Param:
    """A single parameter in a signature."""
    name: str
    type: str = "Any"


@dataclass(frozen=True)
class Signature:
    """Type + effect signature of a definition."""
    params: Tuple[Param, ...] = ()
    returns: str = "Any"
    effects: EffectSet = frozenset()


@dataclass(frozen=True)
class Candidate:
    """One implementation of a definition's contract.

    The optional ``cost`` field (added 2026-05-11) lets a candidate
    declare its dispatcher cost. Among candidates whose guards are
    satisfied, the dispatcher picks the one with the smallest cost;
    declaration order is the tiebreaker. A candidate without a
    ``cost`` field has effective cost ``+∞`` for dispatch purposes —
    it is chosen only if every satisfied candidate is also uncosted,
    preserving v0 semantics when no annotations are present. See
    ``dispatches/2026-05-11-cost-based-dispatch-proposal.readout.md``.
    """
    body: Expr
    intent: str = "default"
    guard: Optional[Expr] = None
    cost: Optional[int] = None

    def __post_init__(self) -> None:
        if self.cost is not None:
            if not isinstance(self.cost, int) or isinstance(self.cost, bool):
                raise ValueError(
                    f"candidate cost must be a non-negative integer, "
                    f"got {type(self.cost).__name__}: {self.cost!r}"
                )
            if self.cost < 0:
                raise ValueError(
                    f"candidate cost must be non-negative, got {self.cost}"
                )


@dataclass(frozen=True)
class Definition:
    """A function definition. Contract-primary, implementations plural.

    The contract is (intent, signature, pre, post). Any number of candidates
    can satisfy it; the runtime picks one by evaluating guards in declaration
    order.
    """
    name: str
    intent: str
    signature: Signature
    pre: Tuple[Expr, ...] = ()
    post: Tuple[Expr, ...] = ()
    candidates: Tuple[Candidate, ...] = ()

    def __post_init__(self) -> None:
        if not self.intent or not self.intent.strip():
            # Enforced at construction because an intent-less definition defeats
            # the core premise of the language. Users can write a terse intent
            # but they cannot omit it.
            raise ValueError(
                f"Definition '{self.name}' is missing its intent. Every "
                f"definition in Codifide must declare why it exists."
            )
        if not self.candidates:
            raise ValueError(
                f"Definition '{self.name}' has no candidate bodies."
            )


@dataclass(frozen=True)
class Module:
    """A collection of definitions under a module name.

    `imports` is a tuple of (local_name, identity) pairs where identity is
    a content-hash of the form `sha256:<hex>`. Imports are resolved
    through a :class:`~codifide.store.SymbolStore` at runtime; the canonical
    form of a module that imports is therefore shorter than a module that
    inlines the same bodies, because it references them by identity.

    The order of `imports` is preserved in the AST but does not affect
    canonical byte form: the canonical JSON layer emits imports as a
    sorted object (map from local name to identity). Two modules that
    differ only in import declaration order produce identical canonical
    bytes and the same content hash.
    """
    name: str
    symbols: Tuple[Definition, ...] = ()
    imports: Tuple[Tuple[str, str], ...] = ()

    def lookup(self, name: str) -> Optional[Definition]:
        for d in self.symbols:
            if d.name == name:
                return d
        return None

    def import_identity(self, name: str) -> Optional[str]:
        """Return the content identity bound to a local import name."""
        for n, identity in self.imports:
            if n == name:
                return identity
        return None


# ---------------------------------------------------------------------------
# Runtime values
# ---------------------------------------------------------------------------
# Runtime values are distinct from AST literals because they track derived
# metadata (e.g. confidence after composition).


@dataclass(frozen=True)
class Value:
    """A runtime value. Always carries type, confidence, and provenance."""
    payload: Any
    type: str = "Any"
    conf: float = 1.0
    provenance: Tuple[str, ...] = ("literal",)

    def with_conf(self, conf: float) -> "Value":
        return Value(self.payload, self.type, conf, self.provenance)

    def with_provenance(self, *tags: str) -> "Value":
        return Value(self.payload, self.type, self.conf, self.provenance + tags)


@dataclass(frozen=True)
class Belief:
    """A value wrapped with an explicit belief score.

    Functions that return from a probabilistic primitive (classifiers, model
    calls) yield Belief so the caller can dispatch on confidence without
    reaching into Value internals.
    """
    about: Value
    conf: float

    @property
    def payload(self) -> Any:
        return self.about.payload


class _BottomType:
    """Singleton refusal value. Handled explicitly by callers; never raised."""
    _instance: Optional["_BottomType"] = None

    def __new__(cls) -> "_BottomType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "⊥"

    def __bool__(self) -> bool:  # Refusal is not truthy.
        return False


Bottom = _BottomType()


class BottomWithReason(_BottomType):
    """A refusal value carrying a human-readable reason string (V3-3).

    Subclasses ``_BottomType`` so that ``isinstance(x, _BottomType)``
    catches both bare ``Bottom`` and reasoned refusals. The ``reason``
    field is purely informational — it does not affect dispatch, canonical
    identity, or truthiness.
    """

    def __new__(cls, reason: str) -> "BottomWithReason":
        # Do NOT use the singleton pattern from _BottomType; each
        # BottomWithReason is a distinct instance carrying its own reason.
        return object.__new__(cls)

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def __repr__(self) -> str:
        return f"⊥({self.reason!r})"

    def __bool__(self) -> bool:
        return False
