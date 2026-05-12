//! Expression-level lexer for Codifide surface syntax.
//! Mirrors `codifide/parser/lexer.py`.

use super::tokens::OPERATORS;

#[derive(Debug, Clone, PartialEq)]
pub enum TokenKind {
    Ident,
    Num,
    Str,
    Op,
    Punct,
}

#[derive(Debug, Clone)]
pub struct Token {
    pub kind: TokenKind,
    pub text: String,
    pub col: usize,
}

#[derive(Debug)]
pub struct LexError(pub String);

impl std::fmt::Display for LexError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

pub fn lex_expr(src: &str) -> Result<Vec<Token>, LexError> {
    let chars: Vec<char> = src.chars().collect();
    let n = chars.len();
    let mut tokens = Vec::new();
    let mut i = 0usize;

    while i < n {
        let c = chars[i];
        if c.is_whitespace() { i += 1; continue; }

        // String literal
        if c == '"' {
            let start = i;
            i += 1;
            let mut buf = String::new();
            loop {
                if i >= n {
                    return Err(LexError(format!("unterminated string at column {}", start)));
                }
                let ch = chars[i];
                if ch == '"' { i += 1; break; }
                if ch == '\\' && i + 1 < n {
                    buf.push(chars[i + 1]);
                    i += 2;
                } else {
                    buf.push(ch);
                    i += 1;
                }
            }
            tokens.push(Token { kind: TokenKind::Str, text: buf, col: start });
            continue;
        }

        // Number (including leading minus when clearly numeric)
        let prev_is_op_or_punct = tokens.last().map(|t: &Token| {
            matches!(t.kind, TokenKind::Op | TokenKind::Punct)
        }).unwrap_or(true);
        if c.is_ascii_digit() || (c == '-' && i + 1 < n && chars[i+1].is_ascii_digit() && prev_is_op_or_punct) {
            let start = i;
            if c == '-' { i += 1; }
            while i < n && (chars[i].is_ascii_digit() || chars[i] == '.') { i += 1; }
            let text: String = chars[start..i].iter().collect();
            tokens.push(Token { kind: TokenKind::Num, text, col: start });
            continue;
        }

        // Operators (longest match first)
        let rest: String = chars[i..].iter().collect();
        let mut op_matched = false;
        // Sort by length descending for greedy match
        let mut ops: Vec<(&str, &str)> = OPERATORS.to_vec();
        ops.sort_by(|a, b| b.0.len().cmp(&a.0.len()));
        for (op, _) in &ops {
            if rest.starts_with(op) {
                tokens.push(Token { kind: TokenKind::Op, text: op.to_string(), col: i });
                i += op.chars().count();
                op_matched = true;
                break;
            }
        }
        if op_matched { continue; }

        // Punctuation
        if "(),[]{}:".contains(c) {
            tokens.push(Token { kind: TokenKind::Punct, text: c.to_string(), col: i });
            i += 1;
            continue;
        }

        // Identifiers (allow dots for dotted names like io.say)
        if c.is_alphabetic() || c == '_' {
            let start = i;
            while i < n && (chars[i].is_alphanumeric() || chars[i] == '_' || chars[i] == '.') {
                i += 1;
            }
            let text: String = chars[start..i].iter().collect();
            tokens.push(Token { kind: TokenKind::Ident, text, col: start });
            continue;
        }

        // Unknown character — hint for common infix operators
        let hint = match c {
            '%' => Some("use `mod(a, b)` — Codifide exposes arithmetic as named primitives, not infix operators"),
            '+' => Some("use `add(a, b)` for arithmetic, or `++` for string concatenation"),
            '*' => Some("use `mul(a, b)`"),
            '/' => Some("use `div(a, b)`"),
            _ => None,
        };
        let base = format!("unexpected character {:?} at column {}", c, i);
        let msg = if let Some(h) = hint {
            format!("{}\n  hint: {}", base, h)
        } else {
            base
        };
        return Err(LexError(msg));
    }
    Ok(tokens)
}
