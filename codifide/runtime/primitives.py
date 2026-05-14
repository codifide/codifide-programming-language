"""Primitive registry.

Arithmetic, comparison, and effectful operations are delegated to trusted
primitives implemented in Python. A Codifide function body may call any primitive
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

from ..core.types import Belief, Bottom, BottomWithReason, Value, _BottomType


@dataclass
class PrimitiveSpec:
    """A primitive is a callable, the effect label it produces, and its return type."""
    name: str
    effect: Optional[str]        # None means pure (effect = ∅)
    returns: str
    fn: Callable[..., Any]
    note: Optional[str] = None   # Optional caveat for the capability manifest


class PrimitiveRegistry:
    """Registry of primitive callables keyed by Codifide name."""

    def __init__(self) -> None:
        self._prims: Dict[str, PrimitiveSpec] = {}

    def register(
        self,
        name: str,
        fn: Callable[..., Any],
        *,
        effect: Optional[str] = None,
        returns: str = "Any",
        note: Optional[str] = None,
    ) -> None:
        self._prims[name] = PrimitiveSpec(name=name, effect=effect, returns=returns, fn=fn, note=note)

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
    them into Codifide `Value` / `Belief` as needed.
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

    # Non-mutating reverse. Polymorphic over string and list because the
    # semantics transfer cleanly and the return shape is unambiguous:
    # reverse a string, get a string; reverse a list, get a list.
    # This establishes the rule for primitive design going forward
    # (see docs/CAPABILITY.md §Primitive polymorphism).
    def _reverse(xs: Any) -> Any:
        v = _unwrap(xs)
        if isinstance(v, str):
            return v[::-1]
        return list(reversed(v))

    reg.register("reverse", _reverse, returns="Any")
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

    # -- Indexed access (pure, polymorphic over string and list) ------------
    #
    # These four primitives close a gap surfaced by the 2026-05-11
    # six-program assessment: Codifide could test string properties
    # (starts_with, ends_with, contains) but could not access characters
    # or substrings by position. The balanced-brackets example
    # degenerated to a count-only check because there was no way to
    # walk characters.
    #
    # Polymorphism: `slice` and `at` work on both strings and lists
    # (following the same rule reverse established — pure primitives
    # are polymorphic when semantics transfer cleanly and return
    # shape is unambiguous). `char_at` and `indexof` are string-only
    # because character indexing on a list would need a separate
    # name (`head`/`tail` are the list-indexing family).

    def _slice(seq: Any, start: Any, end: Any) -> Any:
        """Half-open slice [start, end) over a string or list.

        Out-of-range indices are clamped Python-style rather than
        raising: ``slice("abc", -10, 100) == "abc"``. This matches
        agent expectations and avoids ``PrimitiveError`` on what
        readers treat as a total function.
        """
        v = _unwrap(seq)
        s = int(_num(start))
        e = int(_num(end))
        if isinstance(v, str):
            return v[s:e]
        # Materialize list slice so downstream mutation of the source
        # (unlikely in Codifide but possible at the host level) does
        # not leak.
        return list(v)[s:e]

    reg.register("slice", _slice, returns="Any")

    def _at(seq: Any, i: Any) -> Any:
        """Return the element at index ``i`` of a string or list.

        For strings, returns a single-character string. Negative
        indices count from the end (Python semantics). Out-of-range
        indices raise; the interpreter wraps the IndexError as a
        PrimitiveError so the typed-error discipline holds.
        """
        v = _unwrap(seq)
        idx = int(_num(i))
        return v[idx]

    reg.register("at", _at, returns="Any")

    def _char_at(s: Any, i: Any) -> str:
        """Explicit string-only accessor. Equivalent to ``at(s, i)`` when
        the input is a string; rejects non-strings up front so a typo
        like passing a list is caught before the IndexError path.
        """
        v = _unwrap(s)
        if not isinstance(v, str):
            raise TypeError(
                f"char_at expects a string, got {type(v).__name__}"
            )
        return v[int(_num(i))]

    reg.register("char_at", _char_at, returns="String")

    def _indexof(haystack: Any, needle: Any) -> int:
        """Return the first index of ``needle`` in ``haystack``, or -1.

        Polymorphic: works on strings (substring search) and lists
        (element search). Python's ``str.find`` returns -1 for
        "not found"; we mirror that rather than raising, because
        "-1" is the idiomatic sentinel agents will reach for.
        """
        h = _unwrap(haystack)
        n = _unwrap(needle)
        if isinstance(h, str):
            return h.find(str(n))
        try:
            return list(h).index(n)
        except ValueError:
            return -1

    reg.register("indexof", _indexof, returns="Int")

    # -- Confidence (pure) ---------------------------------------------------
    reg.register("conf", _conf, returns="Float")

    # Construct a Belief from a value and a confidence score. Lets user
    # code produce confidence-annotated values without needing a model
    # primitive — useful for deterministic classifiers, rule-based
    # heuristics, and anywhere else confidence is derived from the
    # input rather than measured by a model.
    def _mk_belief(value: Any, conf: Any) -> Belief:
        unwrapped = _unwrap(value)
        wrapped = (
            value if isinstance(value, Value)
            else Value(payload=unwrapped, type="Any", provenance=("belief",))
        )
        c = float(_num(conf))
        if c < 0.0 or c > 1.0:
            raise ValueError(
                f"belief confidence must be in [0.0, 1.0], got {c}"
            )
        return Belief(about=wrapped, conf=c)

    reg.register("belief", _mk_belief, returns="Any")

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
    reg.register(
        "is_bottom",
        lambda x: isinstance(x, _BottomType),
        returns="Bool",
        note=(
            "Value inspector only. Returns true when passed a literal `bottom` "
            "value (with or without a reason string). Cannot catch a `bottom` "
            "that propagated through a bind — "
            "`bottom` raises BottomPropagationError before this primitive sees it. "
            "To handle propagated refusals, use a `believe` arm with `else => bottom`."
        ),
    )

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
# Helpers for unwrapping Codifide Values inside primitives
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
