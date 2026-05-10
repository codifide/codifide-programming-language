"""Primitive registry.

Arithmetic, comparison, and effectful operations are delegated to trusted
primitives implemented in Python. A Noema function body may call any primitive
whose effect label is declared in its signature's effect set; any other call is
statically rejected by the effect tracker.

Why delegate at all? Because exact arithmetic, clock reads, I/O, and model
calls are operations that neither the language nor the agents authoring code
in it should reimplement by hand. The language provides *one* blessed way to
reach these capabilities and that is through this registry.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..core.types import Belief, Bottom, Value


@dataclass
class PrimitiveSpec:
    """A primitive is a callable, the effect label it produces, and its return type."""
    name: str
    effect: Optional[str]        # None means pure (effect = ∅)
    returns: str
    fn: Callable[..., Any]


class PrimitiveRegistry:
    """Registry of primitive callables keyed by Noema name."""

    def __init__(self) -> None:
        self._prims: Dict[str, PrimitiveSpec] = {}

    def register(
        self,
        name: str,
        fn: Callable[..., Any],
        *,
        effect: Optional[str] = None,
        returns: str = "Any",
    ) -> None:
        self._prims[name] = PrimitiveSpec(name=name, effect=effect, returns=returns, fn=fn)

    def has(self, name: str) -> bool:
        return name in self._prims

    def get(self, name: str) -> PrimitiveSpec:
        return self._prims[name]


# ---------------------------------------------------------------------------
# Effect trace
# ---------------------------------------------------------------------------


@dataclass
class EffectTrace:
    """Mutable record of effects performed during one function call.

    Postconditions can reference fields here: `io.stdout.tail`, `net.sent`,
    etc. Keeping the trace explicit means postcondition evaluation is a pure
    function of the trace, not a side-channel inspection of the world.
    """
    stdout: List[str]
    stdin_consumed: List[str]
    clock_reads: List[float]
    net_calls: List[Tuple[str, Any]]
    model_calls: List[Tuple[str, Any]]

    @classmethod
    def fresh(cls) -> "EffectTrace":
        return cls(stdout=[], stdin_consumed=[], clock_reads=[], net_calls=[], model_calls=[])

    def stdout_concat(self) -> str:
        return "".join(self.stdout)


# ---------------------------------------------------------------------------
# Standard primitive set
# ---------------------------------------------------------------------------


def build_default_registry(trace: EffectTrace) -> PrimitiveRegistry:
    """Build the default primitive set bound to a specific effect trace.

    Effectful primitives write into the trace. Pure primitives operate on
    values directly. Both return plain Python values; the interpreter lifts
    them into Noema `Value` / `Belief` as needed.
    """
    reg = PrimitiveRegistry()

    # -- Arithmetic & comparison (pure) --------------------------------------
    reg.register("add",  lambda a, b: _num(a) + _num(b), returns="Number")
    reg.register("sub",  lambda a, b: _num(a) - _num(b), returns="Number")
    reg.register("mul",  lambda a, b: _num(a) * _num(b), returns="Number")
    reg.register("div",  lambda a, b: _num(a) / _num(b), returns="Number")
    reg.register("mod",  lambda a, b: _num(a) % _num(b), returns="Int")
    reg.register("neg",  lambda a: -_num(a), returns="Number")

    reg.register("eq",   lambda a, b: _unwrap(a) == _unwrap(b), returns="Bool")
    reg.register("ne",   lambda a, b: _unwrap(a) != _unwrap(b), returns="Bool")
    reg.register("lt",   lambda a, b: _num(a) <  _num(b), returns="Bool")
    reg.register("le",   lambda a, b: _num(a) <= _num(b), returns="Bool")
    reg.register("gt",   lambda a, b: _num(a) >  _num(b), returns="Bool")
    reg.register("ge",   lambda a, b: _num(a) >= _num(b), returns="Bool")

    reg.register("and",  lambda *xs: all(bool(_unwrap(x)) for x in xs), returns="Bool")
    reg.register("or",   lambda *xs: any(bool(_unwrap(x)) for x in xs), returns="Bool")
    reg.register("not",  lambda x: not bool(_unwrap(x)), returns="Bool")

    # -- Collections (pure) --------------------------------------------------
    reg.register("len",  lambda xs: len(_unwrap(xs)), returns="Int")
    reg.register("list", lambda *xs: [_unwrap(x) for x in xs], returns="List")
    reg.register("head", lambda xs: _unwrap(xs)[0], returns="Any")
    reg.register("tail", lambda xs: _unwrap(xs)[1:], returns="List")
    reg.register("is_sorted", lambda xs: _is_sorted(_unwrap(xs)), returns="Bool")
    reg.register(
        "is_permutation",
        lambda xs, ys: sorted(_unwrap(xs)) == sorted(_unwrap(ys)),
        returns="Bool",
    )

    # -- Strings (pure) ------------------------------------------------------
    reg.register(
        "contains",
        lambda haystack, needle: str(_unwrap(needle)) in str(_unwrap(haystack)),
        returns="Bool",
    )
    reg.register(
        "str",
        lambda x: str(_unwrap(x)),
        returns="String",
    )

    # -- Confidence (pure) ---------------------------------------------------
    reg.register("conf", _conf, returns="Float")

    # -- I/O -----------------------------------------------------------------
    def io_say(msg: Any) -> Any:
        text = str(_unwrap(msg))
        trace.stdout.append(text + "\n")
        print(text, file=sys.stdout)
        return text

    reg.register("io.say", io_say, effect="io.stdout", returns="String")

    # -- Clock ---------------------------------------------------------------
    def clock_now() -> Dict[str, Any]:
        # Returned as a small record with `hm` (hour:minute) and `unix`.
        ts = time.time()
        trace.clock_reads.append(ts)
        local = time.localtime(ts)
        return {
            "hm": f"{local.tm_hour:02d}:{local.tm_min:02d}",
            "unix": ts,
        }

    reg.register("clock.now", clock_now, effect="clock.read", returns="Clock")

    # -- Model (stubbed; deterministic for v0) -------------------------------
    def vision_classify(img: Any) -> Belief:
        # v0 stub: classify by a tag the caller supplied. Real vision models
        # would live behind this same interface. Deterministic behavior keeps
        # the examples reproducible without a network dependency.
        payload = _unwrap(img)
        if isinstance(payload, dict) and "tag" in payload and "conf" in payload:
            return Belief(
                about=Value(payload=payload["tag"], type="Label", provenance=("model.vision",)),
                conf=float(payload["conf"]),
            )
        return Belief(
            about=Value(payload="unknown", type="Label", provenance=("model.vision",)),
            conf=0.0,
        )

    def _vision_classify_traced(img: Any) -> Belief:
        result = vision_classify(img)
        trace.model_calls.append(("vision.classify", result.payload))
        return result

    reg.register(
        "vision.classify",
        _vision_classify_traced,
        effect="model.vision",
        returns="Label",
    )

    # -- Refusal helpers -----------------------------------------------------
    reg.register("is_bottom", lambda x: x is Bottom, returns="Bool")

    # -- Escalate stub (for classify example) --------------------------------
    def escalate(img: Any, label: Any) -> str:
        trace.model_calls.append(("escalate", (_unwrap(img), _unwrap(label))))
        return f"escalated:{_unwrap(label)}"

    reg.register("escalate", escalate, effect="model.vision", returns="String")

    # -- Host bridges --------------------------------------------------------
    # These are the "trusted primitive" escape hatches for v0. Pure in effect;
    # they defer to the host's implementations of operations we do not want
    # agents reimplementing by hand (sorting, image construction).
    reg.register("host_sorted", lambda xs: sorted(list(_unwrap(xs))), returns="List")
    reg.register(
        "host_image",
        lambda tag, conf: {"tag": _unwrap(tag), "conf": float(_unwrap(conf))},
        returns="Image",
    )

    return reg


# ---------------------------------------------------------------------------
# Helpers for unwrapping Noema Values inside primitives
# ---------------------------------------------------------------------------


def _unwrap(x: Any) -> Any:
    if isinstance(x, Value):
        return x.payload
    if isinstance(x, Belief):
        return x.about.payload
    return x


def _num(x: Any) -> Any:
    v = _unwrap(x)
    if isinstance(v, (int, float)):
        return v
    raise TypeError(f"expected a number, got {type(v).__name__}")


def _is_sorted(xs: Any) -> bool:
    xs = list(xs)
    return all(xs[i] <= xs[i + 1] for i in range(len(xs) - 1))


def _conf(x: Any) -> float:
    if isinstance(x, Belief):
        return x.conf
    if isinstance(x, Value):
        return x.conf
    return 1.0
