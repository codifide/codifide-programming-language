"""Recursive-descent parser for Codifide expressions.

Grammar (v0):

    expr    := bind | concat
    bind    := ident "<-" concat ";" expr
    concat  := atom ("++" atom)*
    atom    := number
             | string
             | "bottom"
             | ident "(" args ")"        -- call
             | ident                     -- ref / dotted ref
             | "(" expr ")"
    args    := expr ("," expr)*

Comparisons and booleans used in pre/post/guard expressions are surfaced as
calls to primitive names: `lt(a, b)`, `ge(a, b)`, `and(...)`, etc. The surface
layer therefore supports `<`, `<=`, `>`, `>=`, `==`, `!=` as infix sugar that
desugars to those primitives. This keeps the core AST tiny.

Believe-dispatch and sequences are handled by the line-oriented outer parser,
not here. This module parses a single expression fragment.
"""
from __future__ import annotations

from typing import List, Optional

from ..core.types import (
    Attr,
    BottomExpr,
    Call,
    Concat,
    Expr,
    If,
    Lit,
    Ref,
)
from .lexer import Token, lex_expr


class ExprParseError(Exception):
    pass


# Infix comparison operators that desugar to primitive calls. Ordered by
# length so `<=` is matched before `<`.
_INFIX = [
    ("<=", "le"),
    (">=", "ge"),
    ("==", "eq"),
    ("!=", "ne"),
    ("<",  "lt"),
    (">",  "gt"),
    ("and", "and"),
    ("or",  "or"),
]


def parse_expr(src: str) -> Expr:
    """Parse a single expression fragment to a canonical Expr."""
    # Rewrite infix comparisons to function-call syntax before lexing. This is
    # a cheap way to keep the lexer and parser tiny while still offering a
    # familiar surface for humans bootstrapping tests.
    rewritten = _desugar_infix(src)
    tokens = lex_expr(rewritten)
    parser = _Parser(tokens)
    result = parser.parse_expr()
    if not parser.eof():
        raise ExprParseError(f"trailing tokens after expression: {parser.peek()}")
    return result


def _desugar_infix(src: str) -> str:
    # We only desugar top-level occurrences outside strings. Because the
    # surface is simple, a character scan suffices.
    out: List[str] = []
    i = 0
    n = len(src)
    in_str = False
    while i < n:
        c = src[i]
        if c == '"':
            in_str = not in_str
            out.append(c)
            i += 1
            continue
        if in_str:
            out.append(c)
            i += 1
            continue
        matched = False
        for op, name in _INFIX:
            if src.startswith(op, i):
                # Word operators require boundaries; symbolic ones do not.
                if op.isalpha():
                    # ``_`` is part of an identifier as far as Codifide
                    # names are concerned. Without treating it as
                    # alphanumeric, the substring ``or`` inside
                    # ``greet_or_refuse`` passes the boundary check
                    # (``_`` is not alphanumeric in Python's sense)
                    # and the desugarer splits the identifier. Same
                    # class of bug as the ``and(...)`` case below;
                    # both caught while writing the 2026-05-11
                    # assessment battery.
                    def _is_ident_char(ch: str) -> bool:
                        return ch.isalnum() or ch == "_"
                    left_ok = i == 0 or not _is_ident_char(src[i - 1])
                    right_ok = (
                        i + len(op) >= n
                        or not _is_ident_char(src[i + len(op)])
                    )
                    if not (left_ok and right_ok):
                        continue
                    # If the word operator is followed (after optional
                    # whitespace) by '(', it's a function call, not
                    # infix. Example: `and(p, q)` is a call to the
                    # ``and`` primitive with two arguments, NOT an
                    # infix expression. Without this guard the
                    # desugarer tried to extract left/right operands
                    # from `and(...)` and choked — found while writing
                    # the 2026-05-11 assessment programs.
                    k = i + len(op)
                    while k < n and src[k].isspace():
                        k += 1
                    if k < n and src[k] == "(":
                        continue
                # Rewrite `a OP b` as `name(a, b)`. We find the left operand by
                # walking back through whitespace and a balanced parenthesis
                # or identifier; and the right operand by a lazy bracket scan.
                left, out = _pop_operand(out)
                right, j = _take_operand(src, i + len(op))
                out.append(f"{name}({left}, {right})")
                i = j
                matched = True
                break
        if not matched:
            out.append(c)
            i += 1
    return "".join(out)


def _pop_operand(buf: List[str]) -> (str, List[str]):
    # Collect the trailing operand from the output buffer. We walk back until
    # we've captured a balanced parenthesis group, or an identifier/number.
    s = "".join(buf).rstrip()
    if not s:
        return "", []
    if s.endswith(")"):
        depth = 0
        i = len(s) - 1
        while i >= 0:
            if s[i] == ")":
                depth += 1
            elif s[i] == "(":
                depth -= 1
                if depth == 0:
                    # Include any leading callable identifier.
                    j = i - 1
                    while j >= 0 and (s[j].isalnum() or s[j] in "._"):
                        j -= 1
                    operand = s[j + 1:]
                    return operand, list(s[: j + 1])
            i -= 1
        raise ExprParseError("unbalanced parentheses in infix desugaring")
    # Identifier/number run.
    j = len(s) - 1
    while j >= 0 and (s[j].isalnum() or s[j] in "._"):
        j -= 1
    return s[j + 1:], list(s[: j + 1])


def _take_operand(src: str, start: int) -> (str, int):
    i = start
    n = len(src)
    while i < n and src[i].isspace():
        i += 1
    if i >= n:
        raise ExprParseError("missing right operand")
    # Balanced paren group.
    if src[i] == "(":
        depth = 1
        j = i + 1
        while j < n and depth > 0:
            if src[j] == "(":
                depth += 1
            elif src[j] == ")":
                depth -= 1
            j += 1
        return src[i:j], j
    # Identifier or call.
    j = i
    while j < n and (src[j].isalnum() or src[j] in "._"):
        j += 1
    if j < n and src[j] == "(":
        depth = 1
        j += 1
        while j < n and depth > 0:
            if src[j] == "(":
                depth += 1
            elif src[j] == ")":
                depth -= 1
            j += 1
    return src[i:j], j


class _Parser:
    # Maximum nesting depth for parenthesized sub-expressions. A
    # recursive-descent parser with no bound blows the Python stack on
    # adversarial input (``((...(1)...))`` with a few hundred parens),
    # leaking RecursionError to the host. The fuzz harness at
    # tests/test_parser_fuzz.py catches this; the bound here keeps
    # pathological input from reaching the Python stack limit.
    MAX_PAREN_DEPTH = 256

    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self._paren_depth = 0

    def eof(self) -> bool:
        return self.pos >= len(self.tokens)

    def peek(self) -> Optional[Token]:
        return None if self.eof() else self.tokens[self.pos]

    def take(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse_expr(self) -> Expr:
        return self.parse_concat()

    def parse_concat(self) -> Expr:
        left = self.parse_atom()
        parts: List[Expr] = [left]
        while not self.eof() and self.peek().kind == "op" and self.peek().text in ("++", "⊕"):
            self.take()
            parts.append(self.parse_atom())
        if len(parts) == 1:
            return left
        return Concat(tuple(parts))

    def parse_atom(self) -> Expr:
        tok = self.peek()
        if tok is None:
            raise ExprParseError("unexpected end of expression")
        if tok.kind == "num":
            self.take()
            if "." in tok.text:
                return Lit(float(tok.text), type="Float")
            return Lit(int(tok.text), type="Int")
        if tok.kind == "str":
            self.take()
            return Lit(tok.text, type="String")
        if tok.kind == "ident":
            if tok.text == "bottom":
                self.take()
                # Optional reason string: bottom "reason text"
                nxt = self.peek()
                if nxt is not None and nxt.kind == "str":
                    self.take()
                    return BottomExpr(reason=nxt.text)
                return BottomExpr()
            if tok.text == "true":
                self.take()
                return Lit(True, type="Bool")
            if tok.text == "false":
                self.take()
                return Lit(False, type="Bool")
            if tok.text == "if":
                # Inline conditional: ``if cond then a else b``.
                # Short-circuit, unlike candidate-dispatch guards.
                # Added 2026-05-11 (spec amendment).
                self.take()
                cond = self.parse_expr()
                nxt = self.peek()
                if nxt is None or nxt.kind != "ident" or nxt.text != "then":
                    raise ExprParseError(
                        "expected 'then' after `if <cond>`"
                    )
                self.take()
                then_branch = self.parse_expr()
                nxt = self.peek()
                if nxt is None or nxt.kind != "ident" or nxt.text != "else":
                    raise ExprParseError(
                        "expected 'else' after `if <cond> then <expr>`"
                    )
                self.take()
                else_branch = self.parse_expr()
                return If(cond=cond, then_=then_branch, else_=else_branch)
            self.take()
            # Function call?
            nxt = self.peek()
            if nxt is not None and nxt.kind == "punct" and nxt.text == "(":
                self.take()  # (
                args: List[Expr] = []
                p = self.peek()
                if p is None:
                    raise ExprParseError(
                        f"unexpected end of expression after '{tok.text}('"
                    )
                if not (p.kind == "punct" and p.text == ")"):
                    args.append(self.parse_expr())
                    while True:
                        p = self.peek()
                        if p is None:
                            raise ExprParseError(
                                f"unexpected end of expression inside "
                                f"arguments of '{tok.text}'"
                            )
                        if not (p.kind == "punct" and p.text == ","):
                            break
                        self.take()
                        args.append(self.parse_expr())
                closer = self.peek()
                if closer is None or not (
                    closer.kind == "punct" and closer.text == ")"
                ):
                    raise ExprParseError(
                        f"expected ')' to close call to '{tok.text}'"
                    )
                self.take()  # )
                return self._call_or_attr(tok.text, tuple(args))
            # Reference or dotted reference (treated as an Attr chain rooted
            # at the first segment, so `clock.now.hm` becomes
            # Attr(Attr(Ref("clock"), "now"), "hm")).
            return self._dotted_ref(tok.text)
        if tok.kind == "punct" and tok.text == "(":
            self.take()
            if self._paren_depth >= self.MAX_PAREN_DEPTH:
                raise ExprParseError(
                    f"parenthesis nesting exceeds {self.MAX_PAREN_DEPTH}"
                )
            self._paren_depth += 1
            try:
                inner = self.parse_expr()
            finally:
                self._paren_depth -= 1
            closer = self.peek()
            if closer is None or not (
                closer.kind == "punct" and closer.text == ")"
            ):
                raise ExprParseError("expected ')'")
            self.take()
            return inner
        raise ExprParseError(f"unexpected token {tok}")

    # -- helpers ---------------------------------------------------------

    def _dotted_ref(self, name: str) -> Expr:
        if "." not in name:
            return Ref(name)
        head, *rest = name.split(".")
        node: Expr = Ref(head)
        for seg in rest:
            node = Attr(node, seg)
        return node

    def _call_or_attr(self, name: str, args: tuple) -> Expr:
        # A dotted call like `io.say("...")` is still a single Call node whose
        # `fn` is the dotted name. The interpreter resolves that name against
        # both the module symbols and the primitive registry.
        return Call(name, args)
