//! Recursive-descent expression parser for Codifide.
//! Mirrors `codifide/parser/expr_parser.py`.
//!
//! Grammar:
//!   expr    := concat
//!   concat  := atom ("++" atom)*
//!   atom    := number | string | "bottom" | "true" | "false"
//!            | "if" expr "then" expr "else" expr
//!            | ident "(" args ")"
//!            | ident
//!            | "(" expr ")"

use codifide_canonical::ast::{Expr};
use super::lexer::{lex_expr, LexError, Token, TokenKind};
use super::tokens::INFIX_OPS;

#[derive(Debug)]
pub struct ExprParseError(pub String);

impl std::fmt::Display for ExprParseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl From<LexError> for ExprParseError {
    fn from(e: LexError) -> Self { ExprParseError(e.0) }
}

pub fn parse_expr(src: &str) -> Result<Expr, ExprParseError> {
    let rewritten = desugar_infix(src);
    let tokens = lex_expr(&rewritten)?;
    let mut p = Parser::new(tokens);
    let result = p.parse_expr()?;
    if !p.eof() {
        let tok = p.peek().unwrap();
        return Err(ExprParseError(format!("trailing tokens after expression: {:?}", tok.text)));
    }
    Ok(result)
}

// ---------------------------------------------------------------------------
// Infix desugaring — mirrors Python's _desugar_infix
// ---------------------------------------------------------------------------

fn desugar_infix(src: &str) -> String {
    let chars: Vec<char> = src.chars().collect();
    let n = chars.len();
    let mut out: Vec<char> = Vec::with_capacity(n);
    let mut i = 0usize;
    let mut in_str = false;

    while i < n {
        let c = chars[i];
        if c == '"' {
            in_str = !in_str;
            out.push(c);
            i += 1;
            continue;
        }
        if in_str {
            out.push(c);
            i += 1;
            continue;
        }

        let rest: String = chars[i..].iter().collect();
        let mut matched = false;
        for (op, name) in INFIX_OPS {
            if !rest.starts_with(op) { continue; }
            let op_chars: Vec<char> = op.chars().collect();
            let op_len = op_chars.len();

            // Word operators need boundaries
            if op.chars().all(|c| c.is_alphabetic()) {
                let is_ident = |ch: char| ch.is_alphanumeric() || ch == '_';
                let left_ok = i == 0 || !is_ident(chars[i - 1]);
                let right_i = i + op_len;
                let right_ok = right_i >= n || !is_ident(chars[right_i]);
                if !left_ok || !right_ok { continue; }
                // If followed by '(' it's a function call, not infix
                let mut k = i + op_len;
                while k < n && chars[k].is_whitespace() { k += 1; }
                if k < n && chars[k] == '(' { continue; }
            }

            // Pop left operand from out buffer
            let out_str: String = out.iter().collect();
            let (left, new_out) = pop_operand(&out_str);
            out = new_out.chars().collect();

            // Take right operand from src
            let (right, j) = take_operand(&chars, i + op_len);

            // Emit name(left, right)
            let repl = format!("{}({}, {})", name, left, right);
            out.extend(repl.chars());
            i = j;
            matched = true;
            break;
        }
        if !matched {
            out.push(c);
            i += 1;
        }
    }
    out.iter().collect()
}

fn pop_operand(buf: &str) -> (String, String) {
    let s = buf.trim_end();
    if s.is_empty() { return (String::new(), String::new()); }
    if s.ends_with(')') {
        let bytes: Vec<char> = s.chars().collect();
        let mut depth = 0i32;
        let mut i = bytes.len();
        loop {
            if i == 0 { break; }
            i -= 1;
            match bytes[i] {
                ')' => depth += 1,
                '(' => {
                    depth -= 1;
                    if depth == 0 {
                        // Include leading callable identifier
                        let mut j = i;
                        while j > 0 && (bytes[j-1].is_alphanumeric() || bytes[j-1] == '_' || bytes[j-1] == '.') {
                            j -= 1;
                        }
                        let operand: String = bytes[j..].iter().collect();
                        let prefix: String = bytes[..j].iter().collect();
                        return (operand, prefix);
                    }
                }
                _ => {}
            }
        }
        return (s.to_string(), String::new());
    }
    // Identifier/number run
    let bytes: Vec<char> = s.chars().collect();
    let mut j = bytes.len();
    while j > 0 && (bytes[j-1].is_alphanumeric() || bytes[j-1] == '_' || bytes[j-1] == '.') {
        j -= 1;
    }
    let operand: String = bytes[j..].iter().collect();
    let prefix: String = bytes[..j].iter().collect();
    (operand, prefix)
}

fn take_operand(chars: &[char], start: usize) -> (String, usize) {
    let n = chars.len();
    let mut i = start;
    while i < n && chars[i].is_whitespace() { i += 1; }
    if i >= n { return (String::new(), i); }
    if chars[i] == '(' {
        let mut depth = 1i32;
        let mut j = i + 1;
        while j < n && depth > 0 {
            match chars[j] { '(' => depth += 1, ')' => depth -= 1, _ => {} }
            j += 1;
        }
        return (chars[i..j].iter().collect(), j);
    }
    let mut j = i;
    while j < n && (chars[j].is_alphanumeric() || chars[j] == '_' || chars[j] == '.') { j += 1; }
    if j < n && chars[j] == '(' {
        let mut depth = 1i32;
        j += 1;
        while j < n && depth > 0 {
            match chars[j] { '(' => depth += 1, ')' => depth -= 1, _ => {} }
            j += 1;
        }
    }
    (chars[i..j].iter().collect(), j)
}

// ---------------------------------------------------------------------------
// Recursive-descent parser
// ---------------------------------------------------------------------------

const MAX_PAREN_DEPTH: usize = 256;

struct Parser {
    tokens: Vec<Token>,
    pos: usize,
    paren_depth: usize,
}

impl Parser {
    fn new(tokens: Vec<Token>) -> Self { Parser { tokens, pos: 0, paren_depth: 0 } }
    fn eof(&self) -> bool { self.pos >= self.tokens.len() }
    fn peek(&self) -> Option<&Token> { self.tokens.get(self.pos) }
    fn take(&mut self) -> &Token { let t = &self.tokens[self.pos]; self.pos += 1; t }

    fn parse_expr(&mut self) -> Result<Expr, ExprParseError> {
        self.parse_concat()
    }

    fn parse_concat(&mut self) -> Result<Expr, ExprParseError> {
        let left = self.parse_atom()?;
        let mut parts = vec![left];
        while let Some(tok) = self.peek() {
            if tok.kind == TokenKind::Op && (tok.text == "++" || tok.text == "⊕") {
                self.take();
                parts.push(self.parse_atom()?);
            } else {
                break;
            }
        }
        if parts.len() == 1 { return Ok(parts.remove(0)); }
        Ok(Expr::Concat { parts })
    }

    fn parse_atom(&mut self) -> Result<Expr, ExprParseError> {
        let tok = self.peek().ok_or_else(|| ExprParseError("unexpected end of expression".into()))?;

        match tok.kind {
            TokenKind::Num => {
                let text = self.take().text.clone();
                if text.contains('.') {
                    let v: f64 = text.parse().map_err(|_| ExprParseError(format!("invalid number: {}", text)))?;
                    Ok(Expr::Lit { value: serde_json::json!(v), type_: "Float".into(), conf: 1.0, provenance: "literal".into() })
                } else {
                    let v: i64 = text.parse().map_err(|_| ExprParseError(format!("invalid integer: {}", text)))?;
                    Ok(Expr::Lit { value: serde_json::json!(v), type_: "Int".into(), conf: 1.0, provenance: "literal".into() })
                }
            }
            TokenKind::Str => {
                let text = self.take().text.clone();
                Ok(Expr::Lit { value: serde_json::json!(text), type_: "String".into(), conf: 1.0, provenance: "literal".into() })
            }
            TokenKind::Ident => {
                let text = tok.text.clone();
                match text.as_str() {
                    "bottom" => {
                        self.take();
                        // Optional reason string: bottom "reason text"
                        let reason = if let Some(next) = self.peek() {
                            if next.kind == TokenKind::Str {
                                let r = self.take().text.clone();
                                Some(r)
                            } else {
                                None
                            }
                        } else {
                            None
                        };
                        Ok(Expr::Bottom { reason })
                    }
                    "true"   => { self.take(); Ok(Expr::Lit { value: serde_json::json!(true),  type_: "Bool".into(), conf: 1.0, provenance: "literal".into() }) }
                    "false"  => { self.take(); Ok(Expr::Lit { value: serde_json::json!(false), type_: "Bool".into(), conf: 1.0, provenance: "literal".into() }) }
                    "if" => {
                        self.take();
                        let cond = self.parse_expr()?;
                        // expect "then"
                        match self.peek() {
                            Some(t) if t.kind == TokenKind::Ident && t.text == "then" => { self.take(); }
                            _ => return Err(ExprParseError("expected 'then' after `if <cond>`".into())),
                        }
                        let then_ = self.parse_expr()?;
                        // expect "else"
                        match self.peek() {
                            Some(t) if t.kind == TokenKind::Ident && t.text == "else" => { self.take(); }
                            _ => return Err(ExprParseError("expected 'else' after `if <cond> then <expr>`".into())),
                        }
                        let else_ = self.parse_expr()?;
                        Ok(Expr::If { cond: Box::new(cond), then_: Box::new(then_), else_: Box::new(else_) })
                    }
                    _ => {
                        self.take();
                        // Function call?
                        if let Some(next) = self.peek() {
                            if next.kind == TokenKind::Punct && next.text == "(" {
                                self.take(); // (
                                let mut args = Vec::new();
                                if let Some(p) = self.peek() {
                                    if !(p.kind == TokenKind::Punct && p.text == ")") {
                                        args.push(self.parse_expr()?);
                                        loop {
                                            match self.peek() {
                                                Some(p) if p.kind == TokenKind::Punct && p.text == "," => {
                                                    self.take();
                                                    args.push(self.parse_expr()?);
                                                }
                                                _ => break,
                                            }
                                        }
                                    }
                                }
                                match self.peek() {
                                    Some(p) if p.kind == TokenKind::Punct && p.text == ")" => { self.take(); }
                                    _ => return Err(ExprParseError(format!("expected ')' to close call to '{}'", text))),
                                }
                                return Ok(Expr::Call { fn_: text, args });
                            }
                        }
                        // Dotted ref: clock.now → Attr(Ref("clock"), "now")
                        Ok(dotted_ref(&text))
                    }
                }
            }
            TokenKind::Punct if tok.text == "(" => {
                self.take();
                if self.paren_depth >= MAX_PAREN_DEPTH {
                    return Err(ExprParseError(format!("parenthesis nesting exceeds {}", MAX_PAREN_DEPTH)));
                }
                self.paren_depth += 1;
                let inner = self.parse_expr()?;
                self.paren_depth -= 1;
                match self.peek() {
                    Some(p) if p.kind == TokenKind::Punct && p.text == ")" => { self.take(); }
                    _ => return Err(ExprParseError("expected ')'".into())),
                }
                Ok(inner)
            }
            _ => Err(ExprParseError(format!("unexpected token {:?}", tok.text))),
        }
    }
}

fn dotted_ref(name: &str) -> Expr {
    if !name.contains('.') {
        return Expr::Ref { name: name.to_string() };
    }
    let parts: Vec<&str> = name.splitn(2, '.').collect();
    let head = Expr::Ref { name: parts[0].to_string() };
    // Recursively build Attr chain for multi-segment names
    build_attr(head, parts[1])
}

fn build_attr(target: Expr, rest: &str) -> Expr {
    if !rest.contains('.') {
        return Expr::Attr { target: Box::new(target), name: rest.to_string() };
    }
    let parts: Vec<&str> = rest.splitn(2, '.').collect();
    let mid = Expr::Attr { target: Box::new(target), name: parts[0].to_string() };
    build_attr(mid, parts[1])
}
