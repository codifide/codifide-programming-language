"""Keyword table for Codifide surface syntax.

Each keyword has an ASCII form (the primary spelling while we bootstrap on a
US keyboard) and an optional unicode glyph (the canonical display form). The
parser accepts either.
"""
from __future__ import annotations

from typing import Dict

# Keyword -> canonical name used by the parser internally.
KEYWORDS: Dict[str, str] = {
    # ASCII
    "def":     "def",
    "intent":  "intent",
    "sig":     "sig",
    "effects": "effects",
    "pre":     "pre",
    "post":    "post",
    "cand":    "cand",
    "when":    "when",
    "believe": "believe",
    "else":    "else",
    "bottom":  "bottom",
    # Unicode glyphs
    "≡":       "def",
    "⟡":       "intent",
    "σ":       "sig",
    "⚡":       "effects",
    "⊢":       "pre",
    "⊣":       "post",
    "ƒ":       "cand",
    "¿":       "when",
    "⊨":       "believe",
    "⊥":       "bottom",
}

# Operator spellings.
OPERATORS: Dict[str, str] = {
    "<-": "bind",
    "←":  "bind",
    "=>": "arm",
    "⇒":  "arm",
    "++": "concat",
    "⊕":  "concat",
    "->": "arrow",
    "→":  "arrow",
}
