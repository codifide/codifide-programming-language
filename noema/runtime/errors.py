"""Noema runtime errors.

All errors inherit from NoemaError so an embedding host can catch Noema-level
failures separately from Python-level ones. Contract and effect violations are
distinguished because they indicate different authoring mistakes:

    - EffectViolation: the function's signature lied about its effects.
    - ContractViolation: the function's body did not deliver on pre/post.
    - DispatchError: no candidate guard matched the current context.
    - RefusalError: a caller did not handle a ⊥ it received.
    - ParseError: the surface syntax was not valid Noema.
"""
from __future__ import annotations

from typing import Any, List, Optional


class NoemaError(Exception):
    """Base for all Noema-level errors."""


class ParseError(NoemaError):
    """Raised by the surface parser for malformed input."""

    def __init__(self, message: str, line: Optional[int] = None) -> None:
        # Line is optional because some errors (e.g. missing intent) are
        # produced after the line has been consumed.
        self.line = line
        location = f" (line {line})" if line else ""
        super().__init__(f"{message}{location}")


class EffectViolation(NoemaError):
    """Raised when a body performs an effect its signature did not declare."""

    def __init__(self, fn: str, declared: frozenset, observed: str) -> None:
        self.fn = fn
        self.declared = declared
        self.observed = observed
        super().__init__(
            f"'{fn}' performed effect '{observed}' which is not in its "
            f"declared set {sorted(declared) or '{}'}"
        )


class ContractViolation(NoemaError):
    """Raised when a precondition or postcondition does not hold."""

    def __init__(self, fn: str, kind: str, clause: str, intent: str) -> None:
        self.fn = fn
        self.kind = kind  # "pre" or "post"
        self.clause = clause
        self.intent = intent
        super().__init__(
            f"'{fn}' failed {kind}condition `{clause}`. The function exists "
            f"because: {intent!r}"
        )


class DispatchError(NoemaError):
    """Raised when no candidate guard matched during dispatch."""

    def __init__(self, fn: str) -> None:
        self.fn = fn
        super().__init__(
            f"No candidate of '{fn}' matched. Add a default candidate (one "
            f"with no `when` guard) to guarantee dispatch."
        )


class RefusalError(NoemaError):
    """Raised when bottom escapes a context that did not choose to handle it."""

    def __init__(self, fn: str) -> None:
        self.fn = fn
        super().__init__(
            f"'{fn}' returned ⊥ (refusal) and no caller chose to handle it. "
            f"Refusal is first-class in Noema; handle it in a `believe` arm "
            f"or at the call site."
        )
