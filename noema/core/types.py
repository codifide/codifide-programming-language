"""Canonical types for Noema.

The canonical form of a Noema program is a typed hypergraph. These dataclasses
are the in-memory representation of that graph. Serialization to and from JSON
lives in noema.projection.canonical.

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

    In Noema, every value carries more than its payload: a type label, a
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
    """First-class refusal. Callers must handle; it is not an exception."""
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


Expr = Union[Lit, Ref, Call, Bind, Seq, Believe, BottomExpr, Concat, Attr]


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
    """One implementation of a definition's contract."""
    body: Expr
    intent: str = "default"
    guard: Optional[Expr] = None


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
                f"definition in Noema must declare why it exists."
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
    through a :class:`~noema.store.SymbolStore` at runtime; the canonical
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
