"""Codifide runtime errors.

All errors inherit from CodifideError so an embedding host can catch Codifide-level
failures separately from Python-level ones. Contract and effect violations are
distinguished because they indicate different authoring mistakes:

    - EffectViolation: the function's signature lied about its effects.
    - ContractViolation: the function's body did not deliver on pre/post.
    - DispatchError: no candidate guard matched the current context.
    - RefusalError: a caller did not handle a ⊥ it received.
    - ParseError: the surface syntax was not valid Codifide.
"""
from __future__ import annotations

from typing import Any, List, Optional


class CodifideError(Exception):
    """Base for all Codifide-level errors."""


class ParseError(CodifideError):
    """Raised by the surface parser for malformed input."""

    def __init__(self, message: str, line: Optional[int] = None) -> None:
        # Line is optional because some errors (e.g. missing intent) are
        # produced after the line has been consumed.
        self.line = line
        location = f" (line {line})" if line else ""
        super().__init__(f"{message}{location}")


class EffectViolation(CodifideError):
    """Raised when a body performs an effect its signature did not declare."""

    def __init__(
        self,
        fn: str,
        declared: frozenset,
        observed: str,
        intent_chain: Optional[List[tuple[str, str]]] = None,
    ) -> None:
        self.fn = fn
        self.declared = declared
        self.observed = observed
        self.intent_chain = intent_chain or []
        msg = (
            f"'{fn}' performed effect '{observed}' which is not in its "
            f"declared set {sorted(declared) or '{}'}"
        )
        if self.intent_chain:
            msg += "\n" + _format_intent_chain(self.intent_chain)
        super().__init__(msg)


class ContractViolation(CodifideError):
    """Raised when a precondition or postcondition does not hold."""

    def __init__(
        self,
        fn: str,
        kind: str,
        clause: str,
        intent: str,
        intent_chain: Optional[List[tuple[str, str]]] = None,
    ) -> None:
        self.fn = fn
        self.kind = kind  # "pre" or "post"
        self.clause = clause
        self.intent = intent
        self.intent_chain = intent_chain or []
        msg = (
            f"'{fn}' failed {kind}condition `{clause}`. The function exists "
            f"because: {intent!r}"
        )
        if self.intent_chain:
            msg += "\n" + _format_intent_chain(self.intent_chain)
        super().__init__(msg)


def _format_intent_chain(chain: List[tuple[str, str]]) -> str:
    """Render an intent chain as a readable call path.

    Prints innermost first. Each frame shows the function name and its
    intent string, so the reader can trace why the failing call
    happened. Intent is first-class; a good error message respects
    that by showing it.
    """
    lines = ["  called from:"]
    for i, (fn, intent) in enumerate(chain):
        indent = "    " + "  " * i
        lines.append(f"{indent}{fn}: {intent!r}")
    return "\n".join(lines)


class DispatchError(CodifideError):
    """Raised when no candidate guard matched during dispatch."""

    def __init__(self, fn: str) -> None:
        self.fn = fn
        super().__init__(
            f"No candidate of '{fn}' matched. Add a default candidate (one "
            f"with no `when` guard) to guarantee dispatch."
        )


class RefusalError(CodifideError):
    """Raised when bottom escapes a context that did not choose to handle it."""

    def __init__(self, fn: str) -> None:
        self.fn = fn
        super().__init__(
            f"'{fn}' returned ⊥ (refusal) and no caller chose to handle it. "
            f"Refusal is first-class in Codifide; handle it in a `believe` arm "
            f"or at the call site."
        )


class RecursionLimitError(CodifideError):
    """Raised when Codifide call depth exceeds the interpreter's limit.

    Exists because a Codifide program is untrusted input to a host. Without an
    explicit bound, a pathological module could exhaust the Python stack
    and crash the embedding process.
    """

    def __init__(self, depth: int) -> None:
        self.depth = depth
        super().__init__(
            f"Codifide call depth exceeded {depth}. Raise the limit on the "
            f"Interpreter or refactor the program to avoid unbounded recursion."
        )


class PrimitiveError(CodifideError):
    """Raised when a primitive call fails.

    Wraps host-language exceptions (arithmetic, indexing, type) in a
    Codifide-level error so hosts can classify failures uniformly. The
    underlying Python exception is preserved as ``__cause__`` for
    diagnostics; the ``fn`` and ``args`` attributes carry the call site.
    """

    def __init__(self, fn: str, args: Any, cause: BaseException) -> None:
        self.fn = fn
        self.args = args
        self.cause = cause
        super().__init__(
            f"primitive '{fn}' failed: {type(cause).__name__}: {cause}"
        )


class BottomPropagationError(CodifideError):
    """Raised when bottom reaches an operation that cannot consume it.

    Refusal is first-class; operations that need a concrete value should
    refuse explicitly in a ``believe`` arm rather than trying to combine
    ⊥ with an arithmetic or collection primitive. This error surfaces
    the authoring mistake as a typed Codifide error rather than a Python
    ``TypeError``.
    """

    def __init__(self, fn: str) -> None:
        self.fn = fn
        super().__init__(
            f"primitive '{fn}' received ⊥ (refusal) as an argument. "
            f"Handle the refusal in a `believe` arm before calling "
            f"primitives that need a concrete value."
        )
