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

import math
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

    # Absolute value, two-arg min/max, and power. These exist because agents
    # reach for them constantly in numeric guards and postconditions; open-
    # coding them per-caller makes contracts harder to read. `min`/`max` are
    # deliberately two-arg — a variadic form over a list lives under
    # `min_of`/`max_of` below, keeping the shapes distinct.
    reg.register("abs",  lambda x: abs(_num(x)), returns="Number")
    reg.register("min",  lambda a, b: min(_num(a), _num(b)), returns="Number")
    reg.register("max",  lambda a, b: max(_num(a), _num(b)), returns="Number")
    reg.register("pow",  lambda b, e: _num(b) ** _num(e), returns="Number")

    # Rounding. `floor` and `ceil` always return an int (mirroring Python's
    # `math.floor`/`math.ceil`); `round` returns Python's built-in rounding,
    # which is int-valued when called on a number without a digit count.
    reg.register("floor", lambda x: math.floor(_num(x)), returns="Int")
    reg.register("ceil",  lambda x: math.ceil(_num(x)),  returns="Int")
    reg.register("round", lambda x: round(_num(x)),       returns="Int")

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

    # Aggregates. `min_of`/`max_of` take a list; empty input raises, and the
    # interpreter's `_call_primitive` wraps that as a typed `PrimitiveError`.
    # `sum` on an empty list is defined to return 0 because postconditions
    # often reduce over possibly-empty collections, and raising there would
    # force every caller to guard length before asking a simple question.
    reg.register("min_of", lambda xs: min(_unwrap(xs)), returns="Any")
    reg.register("max_of", lambda xs: max(_unwrap(xs)), returns="Any")
    reg.register("sum",    lambda xs: sum(_unwrap(xs)) if _unwrap(xs) else 0, returns="Number")

    # Non-mutating list ops. `reverse` and `append` always return fresh
    # Python lists so Noema's value semantics are preserved — a caller who
    # still holds the input sees the input, not the result.
    reg.register("reverse", lambda xs: list(reversed(_unwrap(xs))), returns="List")
    reg.register(
        "append",
        lambda xs, item: [*_unwrap(xs), _unwrap(item)],
        returns="List",
    )

    # Membership on a list, distinct from the string-substring `contains`
    # below. Named `contains_item` so the two never shadow each other.
    reg.register(
        "contains_item",
        lambda xs, item: _unwrap(item) in _unwrap(xs),
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

    # Case and whitespace trimming. Agents frequently normalize inputs
    # before comparison; having these as primitives avoids ad-hoc Python
    # escape hatches and keeps the resulting programs effect-free.
    reg.register("upper", lambda s: str(_unwrap(s)).upper(),  returns="String")
    reg.register("lower", lambda s: str(_unwrap(s)).lower(),  returns="String")
    reg.register("trim",  lambda s: str(_unwrap(s)).strip(),  returns="String")

    # Prefix/suffix tests and substring substitution. These are the
    # minimal set of string checks postconditions tend to want — anything
    # fancier belongs in user-defined code.
    reg.register(
        "starts_with",
        lambda s, prefix: str(_unwrap(s)).startswith(str(_unwrap(prefix))),
        returns="Bool",
    )
    reg.register(
        "ends_with",
        lambda s, suffix: str(_unwrap(s)).endswith(str(_unwrap(suffix))),
        returns="Bool",
    )
    reg.register(
        "replace",
        lambda s, old, new: str(_unwrap(s)).replace(
            str(_unwrap(old)), str(_unwrap(new))
        ),
        returns="String",
    )

    # Split returns a list of plain Python strings; join consumes one and
    # produces a string. The items inside an unwrapped list are already
    # plain Python values, so `join` does not re-unwrap them.
    reg.register(
        "split",
        lambda s, sep: str(_unwrap(s)).split(str(_unwrap(sep))),
        returns="List",
    )
    reg.register(
        "join",
        lambda sep, xs: str(_unwrap(sep)).join(str(item) for item in _unwrap(xs)),
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
