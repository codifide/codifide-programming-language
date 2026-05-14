"""Capability manifest generator.

Produces a structured description of the Codifide language's interface
for agent consumers. The manifest is derived from the implementation —
the primitive registry, the AST class hierarchy, the typed error
classes — so implementation and manifest cannot drift without a test
catching it.

See ``docs/CAPABILITY.md`` for the schema. See the conformance test
in ``tests/test_capability.py`` for the agreement checks.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import __version__
from .core import types as ast_types
from .runtime import errors as error_types
from .runtime.primitives import EffectTrace, build_default_registry


CAPABILITY_SCHEMA_VERSION = "0.1"
CODIFIDE_SCHEMA_VERSION = "0.1"


def generate_capability() -> Dict[str, Any]:
    """Build the capability manifest from the current implementation.

    The returned dict is JSON-compatible and deterministic: calling this
    twice on the same code produces byte-identical canonical form under
    the same rules that apply to modules.
    """
    return {
        "codifide_capability": CAPABILITY_SCHEMA_VERSION,
        "codifide_schema": CODIFIDE_SCHEMA_VERSION,
        "generator": f"codifide-python-{__version__}",
        "docs": _docs(),
        "ast_kinds": _ast_kinds(),
        "primitives": _primitives(),
        "effects": _effects(),
        "errors": _errors(),
        "literal_types": _literal_types(),
        "surface_keywords": _surface_keywords(),
    }


# ---------------------------------------------------------------------------
# Docs field (REQ-V2-4)
# ---------------------------------------------------------------------------


def _docs() -> Dict[str, str]:
    """Stable URLs for key agent-facing documents.

    An agent that fetches the capability manifest can discover the
    cookbook, quickref, and onboarding guide from this field without
    reading the README or browsing the repository.

    URLs point to the canonical public location (codifide.com). The
    manifest drift test verifies these keys are present.
    """
    return {
        "for_agents":    "https://codifide.com/docs/FOR_AGENTS.md",
        "quickref":      "https://codifide.com/docs/AGENT_QUICKREF.md",
        "cookbook":      "https://codifide.com/docs/AGENT_COOKBOOK.md",
        "capability":    "https://codifide.com/capability.json",
        "capability_cbor": "https://codifide.com/capability.cbor",
    }


# ---------------------------------------------------------------------------
# AST kinds
# ---------------------------------------------------------------------------


def _ast_kinds() -> Dict[str, Any]:
    """One entry per canonical AST node kind.

    The descriptions and field shapes are hand-curated because they
    describe the *canonical* form — what a second implementation must
    honor — not the Python dataclass details. We deliberately do not
    introspect the Python classes here: a Rust or Go implementation
    would have different classes but the same canonical shape, and
    the manifest describes the shape.
    """
    return {
        "lit": {
            "description": (
                "A literal value carrying its type, confidence, and "
                "provenance — the small knowledge-graph shape of every "
                "Codifide value."
            ),
            "fields": [
                {"name": "value",      "type": "json"},
                {"name": "type",       "type": "string"},
                {"name": "conf",       "type": "float"},
                {"name": "provenance", "type": "string"},
            ],
        },
        "ref": {
            "description": "A reference to a bound name in the current environment.",
            "fields": [
                {"name": "name", "type": "string"},
            ],
        },
        "call": {
            "description": (
                "A call to a named function or primitive. User functions "
                "resolve against the module's symbols and imports; "
                "unresolved names fall through to the primitive registry."
            ),
            "fields": [
                {"name": "fn",   "type": "string"},
                {"name": "args", "type": "array<Expr>"},
            ],
        },
        "bind": {
            "description": (
                "Introduce a local binding for the scope of the body "
                "expression. ``name`` is in scope inside ``in``, not "
                "inside ``expr``."
            ),
            "fields": [
                {"name": "name", "type": "string"},
                {"name": "expr", "type": "Expr"},
                {"name": "in",   "type": "Expr"},
            ],
        },
        "seq": {
            "description": (
                "Sequential composition. Steps run in order; the result "
                "is the last step's value. Present for side-effect "
                "composition in the tree-walking runtime; a dataflow "
                "runtime would infer order from dependencies."
            ),
            "fields": [
                {"name": "steps", "type": "array<Expr>"},
            ],
        },
        "believe": {
            "description": (
                "Belief dispatch. Arms are evaluated in order; the "
                "first arm whose condition is truthy returns its "
                "value. The subject is bound to the local name ``it`` "
                "inside every arm and inside ``else``. The ``else`` "
                "arm is required; partial belief dispatch is a "
                "structural error."
            ),
            "fields": [
                {"name": "subject", "type": "Expr"},
                {"name": "arms",    "type": "array<pairs<Expr,Expr>>"},
                {"name": "else",    "type": "Expr"},
            ],
        },
        "bottom": {
            "description": (
                "First-class refusal. Callers must handle it in a "
                "``believe`` arm or at a call site; an unhandled "
                "``bottom`` propagating to the top-level caller "
                "raises ``RefusalError``. The optional ``reason`` "
                "field (V3-3) carries a human-readable explanation "
                "of why the refusal occurred; it is propagated "
                "through ``RefusalError`` for diagnostics but does "
                "not affect dispatch or canonical identity. Bare "
                "``bottom`` (no reason) is backward-compatible — "
                "its canonical bytes are unchanged."
            ),
            "fields": [
                {"name": "reason", "type": "string", "optional": True},
            ],
        },
        "concat": {
            "description": (
                "String concatenation. Kept distinct from ``call`` so "
                "the result type stays statically ``String`` without "
                "requiring a type system."
            ),
            "fields": [
                {"name": "parts", "type": "array<Expr>"},
            ],
        },
        "attr": {
            "description": (
                "Field access on a value that exposes a mapping-like "
                "interface. Also used for dotted primitive names like "
                "``clock.now`` when the target is an unbound reference."
            ),
            "fields": [
                {"name": "target", "type": "Expr"},
                {"name": "name",   "type": "string"},
            ],
        },
        "if": {
            "description": (
                "Inline conditional expression. Evaluates ``cond``; "
                "then evaluates EXACTLY ONE of ``then`` or ``else`` "
                "based on truthiness. Short-circuit — unlike "
                "candidate-dispatch guards, which all evaluate before "
                "selection, this expression does not evaluate the "
                "un-taken branch. Added in the 2026-05-11 spec "
                "amendment."
            ),
            "fields": [
                {"name": "cond", "type": "Expr"},
                {"name": "then", "type": "Expr"},
                {"name": "else", "type": "Expr"},
            ],
        },
    }


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def _primitives() -> List[Dict[str, Any]]:
    """Enumerate every primitive exposed by the default registry.

    The primitive registry is the runtime's authoritative surface — if
    a primitive isn't registered, user code cannot call it. So the
    registry is the right source for the manifest.
    """
    trace = EffectTrace.fresh()
    reg = build_default_registry(trace)
    out: List[Dict[str, Any]] = []
    for name in sorted(reg._prims.keys()):  # noqa: SLF001 - module-local use
        spec = reg._prims[name]  # noqa: SLF001
        entry: Dict[str, Any] = {
            "name":    spec.name,
            "effect":  spec.effect,
            "returns": spec.returns,
        }
        if spec.note is not None:
            entry["note"] = spec.note
        out.append(entry)
    return out


def _effects() -> List[str]:
    """Every effect label any primitive produces, sorted and deduplicated.

    Drawn from the primitive registry so the manifest's effect
    vocabulary is exactly what programs can legally declare. An effect
    that appears in no primitive is unreachable.
    """
    trace = EffectTrace.fresh()
    reg = build_default_registry(trace)
    labels = set()
    for spec in reg._prims.values():  # noqa: SLF001
        if spec.effect is not None:
            labels.add(spec.effect)
    return sorted(labels)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def _errors() -> List[Dict[str, Any]]:
    """Every typed error class defined in the runtime.

    The set is closed: implementations MUST raise from this set and
    never leak a host-language exception. See ``docs/CANONICAL.md
    §Errors``.
    """
    # Hand-curated because the "when" and "fatal" fields are editorial
    # — introspection could give us class names and docstrings but not
    # the specific phrasing we want in the manifest. We verify in the
    # test that every class in ``codifide.runtime.errors`` that subclasses
    # ``CodifideError`` appears here, so drift is caught.
    return [
        {
            "name":  "CodifideError",
            "when":  "Base class for all Codifide-level errors. Not raised directly.",
            "fatal": False,
        },
        {
            "name":  "ParseError",
            "when":  "The surface syntax does not parse.",
            "fatal": True,
        },
        {
            "name":  "EffectViolation",
            "when":  "A primitive or user call's effect is not in the budget.",
            "fatal": True,
        },
        {
            "name":  "ContractViolation",
            "when":  "A pre or post clause did not hold.",
            "fatal": True,
        },
        {
            "name":  "DispatchError",
            "when":  "No candidate guard matched and no default exists.",
            "fatal": True,
        },
        {
            "name":  "RefusalError",
            "when":  "⊥ escaped a context with no handler.",
            "fatal": True,
        },
        {
            "name":  "RecursionLimitError",
            "when":  "Call depth exceeded the interpreter's bound.",
            "fatal": True,
        },
        {
            "name":  "PrimitiveError",
            "when":  "A primitive call failed in the host (e.g., divide by zero).",
            "fatal": True,
        },
        {
            "name":  "BottomPropagationError",
            "when":  "⊥ reached a primitive that cannot consume it.",
            "fatal": True,
        },
    ]


# ---------------------------------------------------------------------------
# Literal types
# ---------------------------------------------------------------------------


def _literal_types() -> List[str]:
    """Type tags the default primitive set produces.

    The ``type`` field on a ``lit`` node is a free-form string in the
    canonical form; user code can annotate a literal as any string it
    likes. The manifest's ``literal_types`` is a hint — what the
    default primitives will produce — not a closed enum.
    """
    return [
        "Any",
        "Bool",
        "Clock",
        "Float",
        "Image",
        "Int",
        "Label",
        "List",
        "Number",
        "String",
        "Unit",
    ]


# ---------------------------------------------------------------------------
# Surface keywords
# ---------------------------------------------------------------------------


def _surface_keywords() -> Dict[str, Any]:
    """The ASCII keyword table plus its unicode glyph aliases.

    Included because an agent producing .cod surface text needs to know
    which spellings are accepted. An agent producing canonical JSON
    directly (the preferred path) can ignore this section.
    """
    # Built from codifide.parser.tokens so the table cannot drift.
    from .parser import tokens as _tokens

    # Group keywords into (ascii, [glyph]) pairs. The keyword table
    # maps every form (ascii and glyph) to the same canonical name.
    canonical_to_forms: Dict[str, List[str]] = {}
    for form, canonical in _tokens.KEYWORDS.items():
        canonical_to_forms.setdefault(canonical, []).append(form)

    # Present them in a stable shape: one entry per canonical keyword
    # with its ASCII and glyph spellings.
    out = []
    for canonical in sorted(canonical_to_forms.keys()):
        forms = canonical_to_forms[canonical]
        ascii_forms = [f for f in forms if f.isascii()]
        glyph_forms = [f for f in forms if not f.isascii()]
        out.append({
            "canonical": canonical,
            "ascii":     sorted(ascii_forms),
            "glyphs":    sorted(glyph_forms),
        })

    # Also include the expression-level operators, which have their own
    # table. Same shape.
    op_out = []
    op_to_forms: Dict[str, List[str]] = {}
    for form, canonical in _tokens.OPERATORS.items():
        op_to_forms.setdefault(canonical, []).append(form)
    for canonical in sorted(op_to_forms.keys()):
        forms = op_to_forms[canonical]
        ascii_forms = [f for f in forms if f.isascii()]
        glyph_forms = [f for f in forms if not f.isascii()]
        op_out.append({
            "canonical": canonical,
            "ascii":     sorted(ascii_forms),
            "glyphs":    sorted(glyph_forms),
        })

    return {
        "keywords":  out,
        "operators": op_out,
    }
