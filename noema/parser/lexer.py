"""Expression-level lexer.

The outer parser is line-oriented: it reads a Noema source file one logical
line at a time, classifies each line by its leading keyword, and then hands
the payload to this lexer to produce an expression token stream.

The token stream is intentionally tiny because the surface syntax is tiny.
Every token is a (kind, text, column) triple.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .tokens import OPERATORS


@dataclass(frozen=True)
class Token:
    kind: str        # "ident" | "num" | "str" | "op" | "punct"
    text: str
    col: int


class LexError(Exception):
    pass


# Operator text ordered by length descending so we greedily match multi-char
# operators before their single-char prefixes.
_OP_TEXTS = sorted(OPERATORS.keys(), key=len, reverse=True)


def lex_expr(src: str) -> List[Token]:
    """Tokenize a single expression fragment.

    Supports:
        identifiers:   [A-Za-z_][A-Za-z0-9_.]*
        numbers:       integer or decimal, optionally negative
        strings:       double-quoted, with \\" escape
        punctuation:   ( ) , { } [ ]
        operators:     from the OPERATORS table
    """
    tokens: List[Token] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
            continue
        # Strings
        if c == '"':
            start = i
            i += 1
            buf: List[str] = []
            while i < n and src[i] != '"':
                if src[i] == "\\" and i + 1 < n:
                    buf.append(src[i + 1])
                    i += 2
                else:
                    buf.append(src[i])
                    i += 1
            if i >= n:
                raise LexError(f"unterminated string at column {start}")
            i += 1  # closing quote
            tokens.append(Token("str", "".join(buf), start))
            continue
        # Numbers — including a leading minus when it is clearly numeric.
        if c.isdigit() or (
            c == "-"
            and i + 1 < n
            and src[i + 1].isdigit()
            and (not tokens or tokens[-1].kind in ("op", "punct"))
        ):
            start = i
            if c == "-":
                i += 1
            while i < n and (src[i].isdigit() or src[i] == "."):
                i += 1
            tokens.append(Token("num", src[start:i], start))
            continue
        # Operators, longest match first.
        op_match: Optional[str] = None
        for op in _OP_TEXTS:
            if src.startswith(op, i):
                op_match = op
                break
        if op_match:
            tokens.append(Token("op", op_match, i))
            i += len(op_match)
            continue
        # Punctuation.
        if c in "(),[]{}:":
            tokens.append(Token("punct", c, i))
            i += 1
            continue
        # Identifiers. We allow dots so that dotted names like `io.say` and
        # `clock.now.hm` lex as a single identifier. The parser will not split
        # them; the interpreter resolves them against the primitive namespace.
        if c.isalpha() or c == "_":
            start = i
            while i < n and (src[i].isalnum() or src[i] in "_."):
                i += 1
            tokens.append(Token("ident", src[start:i], start))
            continue
        raise LexError(f"unexpected character {c!r} at column {i}")
    return tokens
