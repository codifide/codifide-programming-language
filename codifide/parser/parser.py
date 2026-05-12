"""Line-oriented outer parser for Codifide source files.

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

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from ..store import SymbolStore

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
from .lexer import LexError
from .tokens import KEYWORDS


@dataclass
class _Line:
    indent: int
    text: str
    raw: str
    lineno: int


_MODULE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")
_IDENTITY_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# Keyword heads that terminate an expression's continuation scan. If a
# physical line leaves brackets unbalanced, we assemble subsequent lines
# into the same expression until brackets balance — unless we hit a
# keyword head, at which point something is genuinely wrong and we
# raise instead of silently eating the next clause or definition.
# Keyword heads that terminate an expression's continuation scan. If a
# physical line leaves brackets unbalanced, we assemble subsequent lines
# into the same expression until brackets balance — unless we hit a
# keyword head, at which point something is genuinely wrong and we
# raise instead of silently eating the next clause or definition.
#
# Notable exclusion: ``else`` is NOT in this set, because it can legitimately
# begin a continuation line of a multi-line inline ``if`` expression.
# ``believe``'s own ``else =>`` arm is handled structurally by the
# believe-block parser without traversing ``_gather_expr``, so nothing
# relies on ``else`` being treated as a stop-head.
_EXPR_STOP_HEADS = frozenset(
    {
        "intent", "sig", "effects", "pre", "post",
        "cand", "when", "cost", "believe",
        "module", "def", "from", "import",
    }
)


def _bracket_balance(text: str) -> int:
    """Net change in bracket depth over `text`, respecting string literals.

    Used to decide whether an expression fragment has closed all of its
    open parentheses/brackets/braces. Strings are scanned for ``\\"``
    escapes so a close bracket inside a string literal does not reduce
    the depth. This is a surface-level utility; the canonical form is
    indifferent to how brackets were distributed across physical lines.
    """
    depth = 0
    i = 0
    n = len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            i += 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        i += 1
    return depth


def _count_keyword_outside_strings(text: str, keyword: str) -> int:
    """Count occurrences of ``keyword`` as a whole word outside strings.

    Used by the multi-line continuation logic to detect unfinished
    ``if``/``then``/``else`` chains. A whole-word match requires
    non-identifier characters (or bounds) on both sides so that
    ``self`` doesn't count as an ``elf`` hit.
    """
    count = 0
    i = 0
    n = len(text)
    in_str = False
    kwlen = len(keyword)
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            i += 1
            continue
        if text.startswith(keyword, i):
            left_ok = i == 0 or not (
                text[i - 1].isalnum() or text[i - 1] == "_"
            )
            j = i + kwlen
            right_ok = j >= n or not (text[j].isalnum() or text[j] == "_")
            if left_ok and right_ok:
                count += 1
                i = j
                continue
        i += 1
    return count


def _ends_with_dangling_keyword(text: str) -> bool:
    """Does ``text`` end with ``if``, ``then``, or ``else`` as its
    last token? These keywords demand an expression follow them;
    their bare appearance at end-of-line signals continuation.
    """
    tail = text.rstrip()
    for kw in ("if", "then", "else"):
        if tail.endswith(kw):
            prefix = tail[: -len(kw)]
            if not prefix or not (prefix[-1].isalnum() or prefix[-1] == "_"):
                return True
    return False


def _has_unclosed_if(text: str) -> bool:
    """Is there an ``if`` in ``text`` whose ``then`` hasn't appeared yet?

    Counts ``if`` and ``then`` tokens outside strings. If there
    are more ``if``s than ``then``s, we are mid-conditional and
    need more input. Same for ``then`` vs ``else`` — each ``if``
    demands a ``then`` and then an ``else``.
    """
    if_count = _count_keyword_outside_strings(text, "if")
    then_count = _count_keyword_outside_strings(text, "then")
    else_count = _count_keyword_outside_strings(text, "else")
    return if_count > then_count or then_count > else_count


def _gather_expr(
    lines: List["_Line"],
    i: int,
    first_text: str,
) -> Tuple[str, int]:
    """Assemble an expression that may span multiple physical lines.

    Starting at ``lines[i]`` with its keyword (if any) already stripped
    into ``first_text``, absorb subsequent physical lines while the
    expression is "obviously not finished." Triggers for continuation:

    - Bracket depth is unbalanced.
    - The line ends with a dangling expression keyword — ``if``,
      ``then``, or ``else`` — that requires more tokens to close.

    Returns the assembled text and the new index (one past the last
    consumed line). Reasons we stop:

    1. Brackets balance AND the tail doesn't end with a dangling
       keyword. This is the normal case.
    2. The next physical line starts with a keyword head (``intent``,
       ``sig``, ``cand``, ``pre``, ``post``, ``when``, etc). A multi-line
       expression cannot plausibly contain one of these at the start
       of a physical line; treating it as continuation would eat the
       next clause or definition silently, which would be far worse
       than a clean ``ParseError``.
    3. End of file.

    If brackets do not balance at stop time, raise ``ParseError``. That
    is a surface bug the author needs to fix, not something the parser
    should paper over.
    """
    depth = _bracket_balance(first_text)
    if depth < 0:
        raise ParseError(
            "unbalanced brackets: too many closers",
            line=lines[i].lineno,
        )
    if (
        depth == 0
        and not _ends_with_dangling_keyword(first_text)
        and not _has_unclosed_if(first_text)
    ):
        return first_text, i + 1

    start_lineno = lines[i].lineno
    parts: List[str] = [first_text]
    j = i + 1
    while j < len(lines) and (
        depth > 0
        or _ends_with_dangling_keyword(parts[-1])
        or _has_unclosed_if(" ".join(parts))
    ):
        nxt = lines[j]
        head, _ = _head(nxt.text)
        if head in _EXPR_STOP_HEADS:
            # A continuation line with a keyword head is almost
            # certainly not a continuation at all. Stop and let the
            # balance check below report the real problem.
            break
        parts.append(nxt.text)
        depth += _bracket_balance(nxt.text)
        if depth < 0:
            raise ParseError(
                "unbalanced brackets: too many closers in continuation",
                line=nxt.lineno,
            )
        j += 1
    if depth != 0:
        raise ParseError(
            f"unbalanced brackets in expression starting at line "
            f"{start_lineno}: {depth} unclosed",
            line=start_lineno,
        )
    joined = " ".join(parts)
    if _ends_with_dangling_keyword(parts[-1]):
        raise ParseError(
            f"expression ending with `if`/`then`/`else` needs more — "
            f"the keyword must be followed by an expression.",
            line=start_lineno,
        )
    if _has_unclosed_if(joined):
        raise ParseError(
            f"`if` expression started at line {start_lineno} is "
            f"missing a matching `then` or `else`.",
            line=start_lineno,
        )
    return joined, j


def parse(
    source: str,
    module_name: str = "main",
    *,
    store: Optional["SymbolStore"] = None,
) -> Module:
    """Parse Codifide source to a canonical Module.

    When the source uses ``from <identity> import <name>`` to resolve
    names through a stored index module, ``store`` must be provided.
    Plain ``import name = sha256:<hex>`` lines never require a store at
    parse time; they are resolved at runtime instead.
    """
    lines = _preprocess(source)
    i = 0
    defs: List[Definition] = []
    imports: List[Tuple[str, str]] = []
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
            candidate = payload.strip() or module_name
            # Security audit P2-2: reject free-form module names. They are
            # echoed into canonical form and human-facing displays; anything
            # that looks like injected code in those surfaces is a spec bug.
            if not _MODULE_NAME_RE.match(candidate):
                raise ParseError(
                    f"invalid module name: {candidate!r}. Module names match "
                    f"[A-Za-z_][A-Za-z0-9_.-]*",
                    line=line.lineno,
                )
            name = candidate
            i += 1
            continue
        if line.text.startswith("from "):
            resolved = _parse_from_import(line, store)
            imports.extend(resolved)
            i += 1
            continue
        if line.text.startswith("import "):
            local_name, identity = _parse_import(line)
            imports.append((local_name, identity))
            i += 1
            continue
        if head == "def":
            defn, i = _parse_definition(lines, i)
            defs.append(defn)
            continue
        raise ParseError(
            f"unexpected top-level line: {line.raw!r}", line=line.lineno
        )
    return Module(name=name, symbols=tuple(defs), imports=tuple(imports))


def _parse_from_import(
    line: "_Line",
    store: Optional["SymbolStore"],
) -> List[Tuple[str, str]]:
    """Parse ``from <identity> import <name1>, <name2>``.

    Resolved at parse time against ``store``. Each requested name must
    appear in the target module's ``imports`` map. Local symbols of the
    target module are not resolvable through ``from``; to re-export a
    locally-defined symbol, the target module must import it by its own
    content identity first. This keeps the rule simple: an index is a
    module whose ``imports`` map is its export table, and ``from``
    looks up names in that table only.
    """
    payload = line.text[len("from ") :].strip()
    if " import " not in payload:
        raise ParseError(
            "from-import requires `import`: expected "
            "`from <identity> import <name>[, <name>]*`",
            line=line.lineno,
        )
    identity_part, names_part = payload.split(" import ", 1)
    identity = identity_part.strip()
    if not _IDENTITY_RE.match(identity):
        raise ParseError(
            f"invalid from-import identity: {identity!r}. Expected "
            f"`sha256:<64 lowercase hex>`",
            line=line.lineno,
        )
    requested = [n.strip() for n in names_part.split(",") if n.strip()]
    if not requested:
        raise ParseError(
            "from-import requires at least one name", line=line.lineno
        )
    for n in requested:
        if not n.isidentifier():
            raise ParseError(
                f"invalid from-import name: {n!r}", line=line.lineno
            )
    if store is None:
        raise ParseError(
            f"from-import requires a store to resolve {identity}. Pass "
            f"store= to parse() or use `import <name> = sha256:<hex>` "
            f"for direct identity binding.",
            line=line.lineno,
        )
    # Resolve names against the target module's imports table. We fetch
    # the target module's canonical JSON and read its imports map; this
    # avoids dragging the whole from_canonical machinery into the parser
    # and keeps the cycle shorter.
    try:
        target_obj = store.get(identity)
    except Exception as exc:
        raise ParseError(
            f"cannot resolve from-import {identity}: {exc}",
            line=line.lineno,
        ) from exc
    target_imports = target_obj.get("imports", {}) or {}
    out: List[Tuple[str, str]] = []
    for name in requested:
        target_identity = target_imports.get(name)
        if target_identity is None:
            raise ParseError(
                f"from-import {identity} does not export {name!r}. "
                f"The target module's imports table has "
                f"{sorted(target_imports.keys()) or 'no entries'}.",
                line=line.lineno,
            )
        out.append((name, target_identity))
    return out


def _parse_import(line: "_Line") -> Tuple[str, str]:
    """Parse `import <local_name> = sha256:<hex>`.

    The syntax is deliberately tight: import names follow the same
    grammar as identifiers, identities follow the on-the-wire form used
    by the symbol store. Anything else is a parse error — imports are
    trust boundaries and we do not want to make them forgiving.
    """
    payload = line.text[len("import ") :].strip()
    if "=" not in payload:
        raise ParseError(
            "import requires `=`: expected `import <name> = sha256:<hex>`",
            line=line.lineno,
        )
    left, right = payload.split("=", 1)
    local_name = left.strip()
    identity = right.strip()
    if not local_name.isidentifier():
        raise ParseError(
            f"invalid import name: {local_name!r}", line=line.lineno
        )
    if not _IDENTITY_RE.match(identity):
        raise ParseError(
            f"invalid import identity: {identity!r}. Expected "
            f"`sha256:<64 lowercase hex>`",
            line=line.lineno,
        )
    return local_name, identity


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
            text, i = _gather_expr(lines, i, rest)
            pre.append(_safe_parse_expr(text, line.lineno))
        elif head == "post":
            text, i = _gather_expr(lines, i, rest)
            post.append(_safe_parse_expr(text, line.lineno))
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
            f"definition '{name}' is missing `intent`. Every Codifide definition "
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
    cost: Optional[int] = None
    steps: List[Expr] = []

    while i < len(lines) and lines[i].indent > base_indent:
        line = lines[i]
        head, rest = _head(line.text)
        if head == "intent":
            cand_intent = _parse_string_literal(rest, line.lineno)
            i += 1
            continue
        if head == "cost":
            # ``cost <non-negative-integer>``. Rejects floats,
            # negatives, and non-numeric text with a typed ParseError
            # — the canonical form contract (see
            # docs/CANONICAL.md §Candidate dispatch) requires a
            # non-negative integer.
            cost_text = rest.strip()
            if not cost_text:
                raise ParseError(
                    "cost requires a non-negative integer argument",
                    line=line.lineno,
                )
            try:
                cost_value = int(cost_text)
            except ValueError as exc:
                raise ParseError(
                    f"cost must be a non-negative integer, got {cost_text!r}",
                    line=line.lineno,
                ) from exc
            if cost_value < 0:
                raise ParseError(
                    f"cost must be non-negative, got {cost_value}",
                    line=line.lineno,
                )
            cost = cost_value
            i += 1
            continue
        if head == "when":
            text, i = _gather_expr(lines, i, rest)
            guard = _safe_parse_expr(text, line.lineno)
            continue
        if head == "believe":
            block, i = _parse_believe(lines, i)
            steps.append(block)
            continue
        # Bind line: `name <- expr`
        if _is_bind(line.text):
            bind_node, i = _parse_bind_multiline(lines, i)
            steps.append(bind_node)
            continue
        # Plain expression line, possibly spanning multiple physical lines
        # while brackets are unbalanced.
        text, i = _gather_expr(lines, i, line.text)
        steps.append(_safe_parse_expr(text, line.lineno))

    if not steps:
        raise ParseError(
            "candidate has no body. Add at least one expression line.",
            line=header.lineno,
        )

    body = _compose_steps(steps)
    return Candidate(body=body, intent=cand_intent, guard=guard, cost=cost), i


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
    # Retained for callers that already have a single-line bind text.
    # Multi-line bind assembly goes through ``_parse_bind_multiline``.
    text = line.text
    op = "<-" if "<-" in text else "←"
    left, right = text.split(op, 1)
    name = left.strip()
    if not name.isidentifier():
        raise ParseError(f"invalid bind name: {name!r}", line=line.lineno)
    return Bind(name=name, expr=_safe_parse_expr(right.strip(), line.lineno), body=Lit(None, type="Unit"))


def _parse_bind_multiline(
    lines: List[_Line], i: int
) -> Tuple[Expr, int]:
    """Parse a bind line whose right-hand side may span multiple physical lines.

    The bind operator (``<-`` or ``←``) is always on the first physical
    line; only the expression on the right may continue. We hand the
    right-hand side to ``_gather_expr`` and build the ``Bind`` node
    with a placeholder body — the composition pass in
    ``_compose_steps`` replaces the body with the remaining steps.
    """
    line = lines[i]
    text = line.text
    op = "<-" if "<-" in text else "←"
    left, right = text.split(op, 1)
    name = left.strip()
    if not name.isidentifier():
        raise ParseError(f"invalid bind name: {name!r}", line=line.lineno)
    rhs_text, new_i = _gather_expr(lines, i, right.strip())
    return (
        Bind(
            name=name,
            expr=_safe_parse_expr(rhs_text, line.lineno),
            body=Lit(None, type="Unit"),
        ),
        new_i,
    )


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
    # Security audit P0-2: the previous implementation ran
    # `s.encode("utf-8").decode("unicode_escape")` which misinterprets any
    # non-ASCII character already in ``s`` as a sequence of Latin-1 bytes
    # and produces mojibake. We instead decode backslash-escapes manually so
    # non-ASCII characters pass through untouched.
    s = s.strip()
    if not s.startswith('"') or not s.endswith('"') or len(s) < 2:
        raise ParseError(f"expected quoted string, got {s!r}", line=line)
    inner = s[1:-1]
    out: List[str] = []
    i = 0
    n = len(inner)
    while i < n:
        c = inner[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        if i + 1 >= n:
            raise ParseError("trailing backslash in string literal", line=line)
        esc = inner[i + 1]
        i += 2
        if esc == "n":
            out.append("\n")
        elif esc == "t":
            out.append("\t")
        elif esc == "r":
            out.append("\r")
        elif esc == "\\":
            out.append("\\")
        elif esc == '"':
            out.append('"')
        elif esc == "0":
            out.append("\0")
        elif esc == "u":
            # \uXXXX four-hex-digit escape — matches the lexer and the
            # canonical byte form's escape alphabet.
            if i + 4 > n:
                raise ParseError(
                    "\\u escape needs four hex digits", line=line
                )
            hex4 = inner[i : i + 4]
            i += 4
            try:
                out.append(chr(int(hex4, 16)))
            except ValueError as exc:
                raise ParseError(
                    f"invalid \\u escape: {hex4!r}", line=line
                ) from exc
        else:
            # Unknown escapes are preserved literally; a future spec may
            # tighten this to an error.
            out.append("\\")
            out.append(esc)
    return "".join(out)


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
    except LexError as e:
        # Security audit 2026-05-10 P1-3: the lexer raises LexError for
        # unterminated strings, unknown characters, and stray operators.
        # Without this wrapper those escaped the parser's ParseError
        # contract and leaked to the host as a bare LexError — which a
        # fuzz harness reliably triggered with unclosed quotes, non-ASCII
        # outside strings, and double bind operators. Wrap it here so
        # the `parse() -> Module | ParseError` contract holds.
        raise ParseError(str(e), line=line) from e
