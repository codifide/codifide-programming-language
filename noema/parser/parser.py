"""Line-oriented outer parser for Noema source files.

The outer parser consumes a source file and produces a `Module`. It delegates
expression parsing to `expr_parser.parse_expr`. The file grammar is:

    file        := moduleDecl? definition*
    moduleDecl  := "module" ident
    definition  := "def" ident
                   intentLine
                   sigLine
                   effectsLine?
                   preLine*
                   postLine*
                   candidate+
    intentLine  := "intent" string
    sigLine     := "sig" "(" params? ")" "->" type
    effectsLine := "effects" "{" idents? "}"
    preLine     := "pre"  expr
    postLine    := "post" expr
    candidate   := "cand" intentLine? guardLine? stepLine+
    guardLine   := "when" expr
    stepLine    := bindLine | believeBlock | expr
    bindLine    := ident "<-" expr
    believeBlock:= "believe" expr
                   (expr "=>" expr)+
                   "else" "=>" expr

Indentation is whitespace-significant inside a definition but only in the most
permissive sense: any line more indented than the `def` header belongs to the
definition. Candidates are delimited by the `cand` keyword.

This is deliberately minimal — we are building the smallest surface that can
express the interesting ideas. The canonical form carries the real meaning.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..core.types import (
    Believe,
    Bind,
    Call,
    Candidate,
    Definition,
    Expr,
    Lit,
    Module,
    Param,
    Ref,
    Seq,
    Signature,
)
from ..runtime.errors import ParseError
from .expr_parser import ExprParseError, parse_expr
from .tokens import KEYWORDS


@dataclass
class _Line:
    indent: int
    text: str
    raw: str
    lineno: int


def parse(source: str, module_name: str = "main") -> Module:
    """Parse Noema source to a canonical Module."""
    lines = _preprocess(source)
    i = 0
    defs: List[Definition] = []
    name = module_name
    while i < len(lines):
        line = lines[i]
        head, rest = _head(line.text)
        if head == "module" or line.text.startswith("module "):
            # Optional module declaration at top of file. `module` is a
            # top-level-only keyword, so we handle it inline rather than
            # adding it to the general keyword table (where it might collide
            # with a future `module` expression).
            _, payload = line.text.split(" ", 1)
            name = payload.strip() or module_name
            i += 1
            continue
        if head == "def":
            defn, i = _parse_definition(lines, i)
            defs.append(defn)
            continue
        raise ParseError(
            f"unexpected top-level line: {line.raw!r}", line=line.lineno
        )
    return Module(name=name, symbols=tuple(defs))


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------


def _preprocess(source: str) -> List[_Line]:
    """Strip comments, blank lines; record original line numbers and indents."""
    out: List[_Line] = []
    for n, raw in enumerate(source.splitlines(), start=1):
        stripped = raw.split("#", 1)[0].rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip())
        out.append(_Line(indent=indent, text=stripped.strip(), raw=raw, lineno=n))
    return out


def _head(text: str) -> Tuple[str, str]:
    # Split off the leading keyword (ASCII or glyph) and return its canonical
    # form plus the remainder of the line.
    for kw, canon in KEYWORDS.items():
        if text == kw:
            return canon, ""
        if text.startswith(kw + " ") or text.startswith(kw + "\t"):
            return canon, text[len(kw):].strip()
    return "", text


# ---------------------------------------------------------------------------
# Definition parser
# ---------------------------------------------------------------------------


def _parse_definition(lines: List[_Line], i: int) -> Tuple[Definition, int]:
    header = lines[i]
    _, rest = _head(header.text)
    name = rest.strip()
    if not name:
        raise ParseError("definition missing a name", line=header.lineno)
    base_indent = header.indent
    i += 1

    intent: Optional[str] = None
    sig = Signature()
    pre: List[Expr] = []
    post: List[Expr] = []
    candidates: List[Candidate] = []

    # Consume body lines until a line at or below header indent.
    while i < len(lines) and lines[i].indent > base_indent:
        line = lines[i]
        head, rest = _head(line.text)
        if head == "intent":
            intent = _parse_string_literal(rest, line.lineno)
            i += 1
        elif head == "sig":
            sig = _parse_signature(rest, line.lineno, existing_effects=sig.effects)
            i += 1
        elif head == "effects":
            effs = _parse_effects(rest, line.lineno)
            sig = Signature(params=sig.params, returns=sig.returns, effects=effs)
            i += 1
        elif head == "pre":
            pre.append(_safe_parse_expr(rest, line.lineno))
            i += 1
        elif head == "post":
            post.append(_safe_parse_expr(rest, line.lineno))
            i += 1
        elif head == "cand":
            cand, i = _parse_candidate(lines, i)
            candidates.append(cand)
        else:
            raise ParseError(
                f"unexpected line in definition '{name}': {line.raw!r}",
                line=line.lineno,
            )

    if intent is None:
        raise ParseError(
            f"definition '{name}' is missing `intent`. Every Noema definition "
            f"must declare its intent.",
            line=header.lineno,
        )
    if not candidates:
        raise ParseError(
            f"definition '{name}' has no `cand` blocks.", line=header.lineno
        )

    return (
        Definition(
            name=name,
            intent=intent,
            signature=sig,
            pre=tuple(pre),
            post=tuple(post),
            candidates=tuple(candidates),
        ),
        i,
    )


def _parse_candidate(lines: List[_Line], i: int) -> Tuple[Candidate, int]:
    header = lines[i]
    base_indent = header.indent
    i += 1

    cand_intent = "default"
    guard: Optional[Expr] = None
    steps: List[Expr] = []

    while i < len(lines) and lines[i].indent > base_indent:
        line = lines[i]
        head, rest = _head(line.text)
        if head == "intent":
            cand_intent = _parse_string_literal(rest, line.lineno)
            i += 1
            continue
        if head == "when":
            guard = _safe_parse_expr(rest, line.lineno)
            i += 1
            continue
        if head == "believe":
            block, i = _parse_believe(lines, i)
            steps.append(block)
            continue
        # Bind line: `name <- expr`
        if _is_bind(line.text):
            steps.append(_parse_bind(line))
            i += 1
            continue
        # Plain expression line.
        steps.append(_safe_parse_expr(line.text, line.lineno))
        i += 1

    if not steps:
        raise ParseError(
            "candidate has no body. Add at least one expression line.",
            line=header.lineno,
        )

    body = _compose_steps(steps)
    return Candidate(body=body, intent=cand_intent, guard=guard), i


def _parse_believe(lines: List[_Line], i: int) -> Tuple[Expr, int]:
    header = lines[i]
    _, rest = _head(header.text)
    subject = _safe_parse_expr(rest, header.lineno)
    base_indent = header.indent
    i += 1

    arms: List[Tuple[Expr, Expr]] = []
    otherwise: Optional[Expr] = None

    while i < len(lines) and lines[i].indent > base_indent:
        line = lines[i]
        text = line.text
        # `else => expr` or `else ⇒ expr`
        if text.startswith("else") and ("=>" in text or "⇒" in text):
            op = "=>" if "=>" in text else "⇒"
            _, right = text.split(op, 1)
            otherwise = _safe_parse_expr(right.strip(), line.lineno)
            i += 1
            continue
        if "=>" in text or "⇒" in text:
            op = "=>" if "=>" in text else "⇒"
            left, right = text.split(op, 1)
            arms.append(
                (
                    _safe_parse_expr(left.strip(), line.lineno),
                    _safe_parse_expr(right.strip(), line.lineno),
                )
            )
            i += 1
            continue
        raise ParseError(
            f"unexpected line in believe block: {line.raw!r}", line=line.lineno
        )

    if otherwise is None:
        raise ParseError(
            "believe block is missing `else => ...` arm. All dispatches must "
            "be total; use `else => bottom` to refuse.",
            line=header.lineno,
        )
    return Believe(subject=subject, arms=tuple(arms), otherwise=otherwise), i


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _is_bind(text: str) -> bool:
    # A bind line is `ident <- expr` where the operator appears outside any
    # string literal. We just check whether `<-` or `←` occurs before the
    # first `"`.
    q = text.find('"')
    cut = len(text) if q < 0 else q
    return ("<-" in text[:cut]) or ("←" in text[:cut])


def _parse_bind(line: _Line) -> Expr:
    text = line.text
    op = "<-" if "<-" in text else "←"
    left, right = text.split(op, 1)
    name = left.strip()
    if not name.isidentifier():
        raise ParseError(f"invalid bind name: {name!r}", line=line.lineno)
    return Bind(name=name, expr=_safe_parse_expr(right.strip(), line.lineno), body=Lit(None, type="Unit"))


def _compose_steps(steps: List[Expr]) -> Expr:
    # Rewrite a flat list of candidate steps into a nested expression tree so
    # bindings are properly scoped. Each Bind becomes a let that wraps the
    # remainder of the steps as its body. Other steps fall through into a Seq.
    if len(steps) == 1:
        return steps[0]
    head, *tail = steps
    if isinstance(head, Bind):
        return Bind(name=head.name, expr=head.expr, body=_compose_steps(tail))
    return Seq(steps=(head, _compose_steps(tail)))


def _parse_string_literal(s: str, line: int) -> str:
    s = s.strip()
    if not s.startswith('"') or not s.endswith('"') or len(s) < 2:
        raise ParseError(f"expected quoted string, got {s!r}", line=line)
    return s[1:-1].encode("utf-8").decode("unicode_escape")


def _parse_signature(rest: str, line: int, existing_effects) -> Signature:
    # Expected shape: `(p1: T1, p2: T2) -> ReturnType`
    arrow = None
    for needle in ("->", "→"):
        if needle in rest:
            arrow = needle
            break
    if arrow is None:
        raise ParseError("signature missing `->`", line=line)
    lhs, rhs = rest.split(arrow, 1)
    lhs = lhs.strip()
    rhs = rhs.strip()
    if not (lhs.startswith("(") and lhs.endswith(")")):
        raise ParseError("signature params must be in parentheses", line=line)
    inside = lhs[1:-1].strip()
    params: List[Param] = []
    if inside:
        for raw in _split_top_level_commas(inside):
            if ":" not in raw:
                raise ParseError(
                    f"param without type annotation: {raw!r}", line=line
                )
            pname, ptype = raw.split(":", 1)
            params.append(Param(name=pname.strip(), type=ptype.strip()))
    return Signature(params=tuple(params), returns=rhs, effects=existing_effects)


def _parse_effects(rest: str, line: int):
    rest = rest.strip()
    if not (rest.startswith("{") and rest.endswith("}")):
        raise ParseError("effect set must be `{...}`", line=line)
    inside = rest[1:-1].strip()
    if not inside:
        return frozenset()
    items = [x.strip() for x in inside.split(",") if x.strip()]
    return frozenset(items)


def _split_top_level_commas(s: str) -> List[str]:
    out: List[str] = []
    depth = 0
    cur: List[str] = []
    for c in s:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
            continue
        cur.append(c)
    if cur:
        out.append("".join(cur).strip())
    return out


def _safe_parse_expr(text: str, line: int) -> Expr:
    try:
        return parse_expr(text)
    except ExprParseError as e:
        raise ParseError(str(e), line=line) from e
