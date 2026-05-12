//! Keyword and operator tables for Codifide surface syntax.
//! Mirrors `codifide/parser/tokens.py`.

/// Map surface keyword (ASCII or Unicode glyph) to canonical name.
pub fn keyword_canon(s: &str) -> Option<&'static str> {
    match s {
        "def" | "≡"      => Some("def"),
        "intent" | "⟡"   => Some("intent"),
        "sig" | "σ"      => Some("sig"),
        "effects" | "⚡"  => Some("effects"),
        "pre" | "⊢"      => Some("pre"),
        "post" | "⊣"     => Some("post"),
        "cand" | "ƒ"     => Some("cand"),
        "when" | "¿"     => Some("when"),
        "cost"           => Some("cost"),
        "believe" | "⊨"  => Some("believe"),
        "else"           => Some("else"),
        "bottom" | "⊥"   => Some("bottom"),
        _ => None,
    }
}

/// Operator spellings (longest first for greedy matching).
pub const OPERATORS: &[(&str, &str)] = &[
    ("<-",  "bind"),
    ("←",   "bind"),
    ("=>",  "arm"),
    ("⇒",   "arm"),
    ("++",  "concat"),
    ("⊕",   "concat"),
    ("->",  "arrow"),
    ("→",   "arrow"),
];

/// Infix comparison/logical operators that desugar to primitive calls.
/// Ordered longest-first so `<=` matches before `<`.
pub const INFIX_OPS: &[(&str, &str)] = &[
    ("<=", "le"),
    (">=", "ge"),
    ("==", "eq"),
    ("!=", "ne"),
    ("<",  "lt"),
    (">",  "gt"),
    ("and","and"),
    ("or", "or"),
];
