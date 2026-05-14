//! Codifide surface-syntax parser — Rust implementation.
//! Mirrors `codifide/parser/parser.py`.

pub mod expr_parser;
pub mod lexer;
pub mod tokens;

use codifide_canonical::ast::{Candidate, Definition, Expr, Module, Param, Signature};
use expr_parser::{parse_expr, ExprParseError};
use lexer::LexError;
use tokens::keyword_canon;

// ---------------------------------------------------------------------------
// Public error type
// ---------------------------------------------------------------------------

#[derive(Debug)]
pub struct ParseError {
    pub message: String,
    pub line: Option<usize>,
}

impl std::fmt::Display for ParseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if let Some(l) = self.line {
            write!(f, "{} (line {})", self.message, l)
        } else {
            write!(f, "{}", self.message)
        }
    }
}

impl std::error::Error for ParseError {}

fn parse_err(msg: impl Into<String>, line: Option<usize>) -> ParseError {
    ParseError { message: msg.into(), line }
}

impl From<ExprParseError> for ParseError {
    fn from(e: ExprParseError) -> Self { ParseError { message: e.0, line: None } }
}
impl From<LexError> for ParseError {
    fn from(e: LexError) -> Self { ParseError { message: e.0, line: None } }
}

// ---------------------------------------------------------------------------
// Preprocessed line
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
struct Line {
    indent: usize,
    text: String,
    lineno: usize,
}

// ---------------------------------------------------------------------------
// Stop heads for expression continuation
// ---------------------------------------------------------------------------

fn is_stop_head(s: &str) -> bool {
    matches!(s, "intent"|"sig"|"effects"|"pre"|"post"|"cand"|"when"|"cost"|"believe"|"module"|"def"|"from"|"import")
}

// ---------------------------------------------------------------------------
// Public entry points
// ---------------------------------------------------------------------------

/// Parse Codifide source without store access.
/// `from`-imports will fail with a clear error directing the user to
/// `parse_with_store` or `CODIFIDE_RUNTIME=python`.
pub fn parse(source: &str, module_name: &str) -> Result<Module, ParseError> {
    parse_with_store(source, module_name, None)
}

/// Parse Codifide source with optional store path for `from`-import resolution.
///
/// When `store_root` is `Some(path)`, `from <hash> import name` lines are
/// resolved by reading the target module's canonical JSON from the store
/// filesystem and looking up the requested names in its imports table.
///
/// This mirrors the Python parser's `parse(source, store=store)` behaviour.
pub fn parse_with_store(
    source: &str,
    module_name: &str,
    store_root: Option<&std::path::Path>,
) -> Result<Module, ParseError> {
    let lines = preprocess(source);
    let mut i = 0usize;
    let mut defs: Vec<(String, Definition)> = Vec::new();
    let mut imports: Vec<(String, String)> = Vec::new();
    let mut name = module_name.to_string();

    while i < lines.len() {
        let line = &lines[i];
        let (head, rest) = split_head(&line.text);

        if head == "module" || line.text.starts_with("module ") {
            let candidate = if line.text.starts_with("module ") {
                line.text["module ".len()..].trim().to_string()
            } else {
                rest.trim().to_string()
            };
            let candidate = if candidate.is_empty() { module_name.to_string() } else { candidate };
            if !is_valid_module_name(&candidate) {
                return Err(parse_err(
                    format!("invalid module name: {:?}. Module names match [A-Za-z_][A-Za-z0-9_.-]*", candidate),
                    Some(line.lineno),
                ));
            }
            name = candidate;
            i += 1;
            continue;
        }
        if line.text.starts_with("import ") {
            let (local_name, identity) = parse_import(line)?;
            imports.push((local_name, identity));
            i += 1;
            continue;
        }
        if line.text.starts_with("from ") {
            let resolved = parse_from_import(line, store_root)?;
            imports.extend(resolved);
            i += 1;
            continue;
        }
        if head == "def" {
            let (defn_name, defn, new_i) = parse_definition(&lines, i)?;
            defs.push((defn_name, defn));
            i = new_i;
            continue;
        }
        return Err(parse_err(
            format!("unexpected top-level line: {:?}", line.text),
            Some(line.lineno),
        ));
    }

    Ok(Module { name, symbols: defs, imports })
}

// ---------------------------------------------------------------------------
// Import parsing
// ---------------------------------------------------------------------------

fn parse_import(line: &Line) -> Result<(String, String), ParseError> {
    let payload = line.text["import ".len()..].trim();
    if !payload.contains('=') {
        return Err(parse_err(
            "import requires `=`: expected `import <name> = sha256:<hex>`",
            Some(line.lineno),
        ));
    }
    let eq = payload.find('=').unwrap();
    let local_name = payload[..eq].trim().to_string();
    let identity = payload[eq+1..].trim().to_string();
    if !local_name.chars().all(|c| c.is_alphanumeric() || c == '_') || local_name.is_empty() {
        return Err(parse_err(format!("invalid import name: {:?}", local_name), Some(line.lineno)));
    }
    if !is_valid_identity(&identity) {
        return Err(parse_err(
            format!("invalid import identity: {:?}. Expected `sha256:<64 lowercase hex>`", identity),
            Some(line.lineno),
        ));
    }
    Ok((local_name, identity))
}

fn is_valid_identity(s: &str) -> bool {
    s.starts_with("sha256:") && s.len() == 71 && s[7..].chars().all(|c| c.is_ascii_hexdigit() && !c.is_uppercase())
}

/// Parse `from <identity> import name1, name2` and resolve names against
/// the target module's imports table in the store.
///
/// The store layout is: `<root>/sha256/<XX>/<remaining>.json` or `.cbor`.
/// We try JSON first (legacy), then CBOR. The target module's `imports`
/// field maps name → identity; we look up each requested name there.
fn parse_from_import(
    line: &Line,
    store_root: Option<&std::path::Path>,
) -> Result<Vec<(String, String)>, ParseError> {
    let payload = line.text["from ".len()..].trim();
    if !payload.contains(" import ") {
        return Err(parse_err(
            "from-import requires `import`: expected `from <identity> import <name>[, <name>]*`",
            Some(line.lineno),
        ));
    }
    let import_pos = payload.find(" import ").unwrap();
    let identity = payload[..import_pos].trim();
    let names_part = payload[import_pos + " import ".len()..].trim();

    if !is_valid_identity(identity) {
        return Err(parse_err(
            format!("invalid from-import identity: {:?}. Expected `sha256:<64 lowercase hex>`", identity),
            Some(line.lineno),
        ));
    }

    let requested: Vec<&str> = names_part.split(',')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .collect();
    if requested.is_empty() {
        return Err(parse_err("from-import requires at least one name", Some(line.lineno)));
    }
    for n in &requested {
        if !n.chars().all(|c| c.is_alphanumeric() || c == '_') || n.is_empty() {
            return Err(parse_err(format!("invalid from-import name: {:?}", n), Some(line.lineno)));
        }
    }

    let store = match store_root {
        Some(p) => p,
        None => {
            return Err(parse_err(
                format!(
                    "from-import requires a store. Pass --store <path> to the Rust runtime, \
                     or use `CODIFIDE_RUNTIME=python python3 -m codifide run ...` to enable \
                     from-imports without a store flag. \
                     (`import name = sha256:<hex>` only imports a single symbol and does not \
                     carry transitive dependencies.)"
                ),
                Some(line.lineno),
            ));
        }
    };

    // Read the target module from the store.
    let digest = &identity[7..]; // strip "sha256:"
    let shard = &digest[..2];
    let rest = &digest[2..];
    let base = store.join("sha256").join(shard);

    // Try JSON first, then CBOR.
    let target_obj: serde_json::Value = {
        let json_path = base.join(format!("{}.json", rest));
        let cbor_path = base.join(format!("{}.cbor", rest));
        if json_path.exists() {
            let data = std::fs::read(&json_path).map_err(|e| parse_err(
                format!("cannot read store object {}: {}", identity, e),
                Some(line.lineno),
            ))?;
            serde_json::from_slice(&data).map_err(|e| parse_err(
                format!("cannot decode store object {}: {}", identity, e),
                Some(line.lineno),
            ))?
        } else if cbor_path.exists() {
            let data = std::fs::read(&cbor_path).map_err(|e| parse_err(
                format!("cannot read store object {}: {}", identity, e),
                Some(line.lineno),
            ))?;
            // Decode CBOR using the canonical crate's decoder.
            codifide_canonical::decode_canonical_cbor(&data).map_err(|e| parse_err(
                format!("cannot decode CBOR store object {}: {}", identity, e),
                Some(line.lineno),
            ))?
        } else {
            return Err(parse_err(
                format!("from-import {}: not found in store at {}", identity, store.display()),
                Some(line.lineno),
            ));
        }
    };

    // Extract the imports table from the target module.
    let target_imports = target_obj.get("imports")
        .and_then(|v| v.as_object())
        .cloned()
        .unwrap_or_default();

    let mut out = Vec::new();
    for name in &requested {
        match target_imports.get(*name) {
            Some(serde_json::Value::String(target_identity)) => {
                out.push((name.to_string(), target_identity.clone()));
            }
            _ => {
                let available: Vec<&str> = target_imports.keys().map(|s| s.as_str()).collect();
                return Err(parse_err(
                    format!(
                        "from-import {} does not export {:?}. \
                         The target module's imports table has: {:?}",
                        identity, name,
                        if available.is_empty() { vec!["(none)"] } else { available }
                    ),
                    Some(line.lineno),
                ));
            }
        }
    }
    Ok(out)
}

fn is_valid_module_name(s: &str) -> bool {
    let mut chars = s.chars();
    match chars.next() {
        Some(c) if c.is_alphabetic() || c == '_' => {}
        _ => return false,
    }
    chars.all(|c| c.is_alphanumeric() || c == '_' || c == '.' || c == '-')
}

// ---------------------------------------------------------------------------
// Definition parser
// ---------------------------------------------------------------------------

fn parse_definition(lines: &[Line], i: usize) -> Result<(String, Definition, usize), ParseError> {
    let header = &lines[i];
    let (_, rest) = split_head(&header.text);
    let def_name = rest.trim().to_string();
    if def_name.is_empty() {
        return Err(parse_err("definition missing a name", Some(header.lineno)));
    }
    let base_indent = header.indent;
    let mut i = i + 1;

    let mut intent: Option<String> = None;
    let mut params: Vec<Param> = Vec::new();
    let mut returns = "Any".to_string();
    let mut effects: Vec<String> = Vec::new();
    let mut pre: Vec<Expr> = Vec::new();
    let mut post: Vec<Expr> = Vec::new();
    let mut candidates: Vec<Candidate> = Vec::new();

    while i < lines.len() && lines[i].indent > base_indent {
        let line = &lines[i];
        let (head, rest) = split_head(&line.text);
        match head.as_str() {
            "intent" => {
                intent = Some(parse_string_literal(rest.trim(), line.lineno)?);
                i += 1;
            }
            "sig" => {
                let (p, r) = parse_signature(rest.trim(), line.lineno)?;
                params = p;
                returns = r;
                i += 1;
            }
            "effects" => {
                effects = parse_effects(rest.trim(), line.lineno)?;
                i += 1;
            }
            "pre" => {
                let (text, new_i) = gather_expr(lines, i, rest.trim())?;
                pre.push(safe_parse_expr(&text, line.lineno)?);
                i = new_i;
            }
            "post" => {
                let (text, new_i) = gather_expr(lines, i, rest.trim())?;
                post.push(safe_parse_expr(&text, line.lineno)?);
                i = new_i;
            }
            "cand" => {
                let (cand, new_i) = parse_candidate(lines, i)?;
                candidates.push(cand);
                i = new_i;
            }
            _ => {
                return Err(parse_err(
                    format!("unexpected line in definition {:?}: {:?}", def_name, line.text),
                    Some(line.lineno),
                ));
            }
        }
    }

    let intent = intent.ok_or_else(|| parse_err(
        format!("definition {:?} is missing `intent`. Every Codifide definition must declare its intent.", def_name),
        Some(lines[i.saturating_sub(1)].lineno),
    ))?;
    if candidates.is_empty() {
        return Err(parse_err(
            format!("definition {:?} has no `cand` blocks.", def_name),
            None,
        ));
    }

    let sig = Signature { params, returns, effects };
    let defn = Definition { intent, signature: sig, pre, post, candidates };
    Ok((def_name, defn, i))
}

// ---------------------------------------------------------------------------
// Candidate parser
// ---------------------------------------------------------------------------

fn parse_candidate(lines: &[Line], i: usize) -> Result<(Candidate, usize), ParseError> {
    let header = &lines[i];
    let base_indent = header.indent;
    let mut i = i + 1;

    let mut cand_intent = "default".to_string();
    let mut guard: Option<Expr> = None;
    let mut cost: Option<u64> = None;
    let mut steps: Vec<Expr> = Vec::new();
    // Track (name, lineno) of binds seen before any `when` guard.
    // Used for REQ-V2-2: static bind-before-when detection.
    let mut bound_before_guard: Vec<(String, usize)> = Vec::new();

    while i < lines.len() && lines[i].indent > base_indent {
        let line = &lines[i];
        let (head, rest) = split_head(&line.text);
        match head.as_str() {
            "intent" => {
                cand_intent = parse_string_literal(rest.trim(), line.lineno)?;
                i += 1;
            }
            "cost" => {
                let cost_text = rest.trim();
                if cost_text.is_empty() {
                    return Err(parse_err("cost requires a non-negative integer argument", Some(line.lineno)));
                }
                // Reject floats explicitly
                if cost_text.contains('.') {
                    return Err(parse_err(
                        format!("cost must be a non-negative integer, got {:?}", cost_text),
                        Some(line.lineno),
                    ));
                }
                let v: i64 = cost_text.parse().map_err(|_| parse_err(
                    format!("cost must be a non-negative integer, got {:?}", cost_text),
                    Some(line.lineno),
                ))?;
                if v < 0 {
                    return Err(parse_err(format!("cost must be non-negative, got {}", v), Some(line.lineno)));
                }
                cost = Some(v as u64);
                i += 1;
            }
            "when" => {
                // REQ-V2-2: Static bind-before-when detection.
                // `when` guards execute before the candidate body. Any name
                // bound with `<-` in the body does not exist yet when the
                // guard runs.
                if !bound_before_guard.is_empty() {
                    let names: Vec<String> = bound_before_guard
                        .iter()
                        .map(|(n, ln)| format!("'{}' (line {})", n, ln))
                        .collect();
                    let is_are = if bound_before_guard.len() == 1 { "is" } else { "are" };
                    return Err(parse_err(
                        format!(
                            "bind-before-when: the `when` guard executes before the \
                             candidate body, but {} {} bound in the body with `<-` and \
                             will not exist yet. Fix: move the bind into the body and \
                             use `if/then/else` to route on the result instead of a \
                             `when` guard.",
                            names.join(", "),
                            is_are,
                        ),
                        Some(line.lineno),
                    ));
                }
                let (text, new_i) = gather_expr(lines, i, rest.trim())?;
                guard = Some(safe_parse_expr(&text, line.lineno)?);
                i = new_i;
            }
            "believe" => {
                let (block, new_i) = parse_believe(lines, i)?;
                steps.push(block);
                i = new_i;
            }
            _ => {
                // Bind line?
                if is_bind(&line.text) {
                    let (bind_node, new_i) = parse_bind_multiline(lines, i)?;
                    // Record the bound name for bind-before-when detection.
                    if let Expr::Bind { ref name, .. } = bind_node {
                        bound_before_guard.push((name.clone(), line.lineno));
                    }
                    steps.push(bind_node);
                    i = new_i;
                } else {
                    let (text, new_i) = gather_expr(lines, i, &line.text)?;
                    steps.push(safe_parse_expr(&text, line.lineno)?);
                    i = new_i;
                }
            }
        }
    }

    if steps.is_empty() {
        return Err(parse_err(
            "candidate has no body. Add at least one expression line.",
            Some(header.lineno),
        ));
    }

    let body = compose_steps(steps);
    Ok((Candidate { intent: cand_intent, guard, body, cost }, i))
}

// ---------------------------------------------------------------------------
// Believe block parser
// ---------------------------------------------------------------------------

fn parse_believe(lines: &[Line], i: usize) -> Result<(Expr, usize), ParseError> {
    let header = &lines[i];
    let (_, rest) = split_head(&header.text);
    let subject = safe_parse_expr(rest.trim(), header.lineno)?;
    let base_indent = header.indent;
    let mut i = i + 1;

    let mut arms: Vec<(Expr, Expr)> = Vec::new();
    let mut otherwise: Option<Expr> = None;

    while i < lines.len() && lines[i].indent > base_indent {
        let line = &lines[i];
        let text = &line.text;
        let has_fat_arrow = text.contains("=>") || text.contains("⇒");
        if !has_fat_arrow {
            return Err(parse_err(
                format!("unexpected line in believe block: {:?}", text),
                Some(line.lineno),
            ));
        }
        let op = if text.contains("=>") { "=>" } else { "⇒" };
        let split_pos = text.find(op).unwrap();
        let left = text[..split_pos].trim();
        let right = text[split_pos + op.len()..].trim();
        if left == "else" {
            otherwise = Some(safe_parse_expr(right, line.lineno)?);
        } else {
            arms.push((safe_parse_expr(left, line.lineno)?, safe_parse_expr(right, line.lineno)?));
        }
        i += 1;
    }

    let otherwise = otherwise.ok_or_else(|| parse_err(
        "believe block is missing `else => ...` arm. All dispatches must be total; use `else => bottom` to refuse.",
        Some(lines[i.saturating_sub(1)].lineno),
    ))?;

    Ok((Expr::Believe {
        subject: Box::new(subject),
        arms,
        otherwise: Box::new(otherwise),
    }, i))
}

// ---------------------------------------------------------------------------
// Multi-line expression gathering
// ---------------------------------------------------------------------------

fn bracket_balance(text: &str) -> i32 {
    let mut depth = 0i32;
    let mut in_str = false;
    let chars: Vec<char> = text.chars().collect();
    let n = chars.len();
    let mut i = 0;
    while i < n {
        let c = chars[i];
        if in_str {
            if c == '\\' && i + 1 < n { i += 2; continue; }
            if c == '"' { in_str = false; }
            i += 1; continue;
        }
        if c == '"' { in_str = true; i += 1; continue; }
        match c { '('|'['|'{' => depth += 1, ')'|']'|'}' => depth -= 1, _ => {} }
        i += 1;
    }
    depth
}

fn count_keyword_outside_strings(text: &str, keyword: &str) -> usize {
    let chars: Vec<char> = text.chars().collect();
    let n = chars.len();
    let kw_chars: Vec<char> = keyword.chars().collect();
    let kw_len = kw_chars.len();
    let mut count = 0usize;
    let mut i = 0;
    let mut in_str = false;
    while i < n {
        let c = chars[i];
        if in_str {
            if c == '\\' && i + 1 < n { i += 2; continue; }
            if c == '"' { in_str = false; }
            i += 1; continue;
        }
        if c == '"' { in_str = true; i += 1; continue; }
        if chars[i..].starts_with(&kw_chars) {
            let is_ident = |ch: char| ch.is_alphanumeric() || ch == '_';
            let left_ok = i == 0 || !is_ident(chars[i - 1]);
            let j = i + kw_len;
            let right_ok = j >= n || !is_ident(chars[j]);
            if left_ok && right_ok { count += 1; i = j; continue; }
        }
        i += 1;
    }
    count
}

fn ends_with_dangling_keyword(text: &str) -> bool {
    let tail = text.trim_end();
    for kw in &["if", "then", "else"] {
        if tail.ends_with(kw) {
            let prefix = &tail[..tail.len() - kw.len()];
            if prefix.is_empty() || !prefix.ends_with(|c: char| c.is_alphanumeric() || c == '_') {
                return true;
            }
        }
    }
    false
}

fn has_unclosed_if(text: &str) -> bool {
    let if_count = count_keyword_outside_strings(text, "if");
    let then_count = count_keyword_outside_strings(text, "then");
    let else_count = count_keyword_outside_strings(text, "else");
    if_count > then_count || then_count > else_count
}

fn gather_expr(lines: &[Line], i: usize, first_text: &str) -> Result<(String, usize), ParseError> {
    let mut depth = bracket_balance(first_text);
    if depth < 0 {
        return Err(parse_err("unbalanced brackets: too many closers", Some(lines[i].lineno)));
    }
    if depth == 0 && !ends_with_dangling_keyword(first_text) && !has_unclosed_if(first_text) {
        return Ok((first_text.to_string(), i + 1));
    }

    let start_lineno = lines[i].lineno;
    let mut parts = vec![first_text.to_string()];
    let mut j = i + 1;

    while j < lines.len() && (depth > 0 || ends_with_dangling_keyword(parts.last().unwrap()) || has_unclosed_if(&parts.join(" "))) {
        let nxt = &lines[j];
        let (head, _) = split_head(&nxt.text);
        if is_stop_head(&head) { break; }
        parts.push(nxt.text.clone());
        depth += bracket_balance(&nxt.text);
        if depth < 0 {
            return Err(parse_err("unbalanced brackets: too many closers in continuation", Some(nxt.lineno)));
        }
        j += 1;
    }

    if depth != 0 {
        return Err(parse_err(
            format!("unbalanced brackets in expression starting at line {}: {} unclosed", start_lineno, depth),
            Some(start_lineno),
        ));
    }
    let joined = parts.join(" ");
    if ends_with_dangling_keyword(parts.last().unwrap()) {
        return Err(parse_err(
            "expression ending with `if`/`then`/`else` needs more — the keyword must be followed by an expression.",
            Some(start_lineno),
        ));
    }
    if has_unclosed_if(&joined) {
        return Err(parse_err(
            format!("`if` expression started at line {} is missing a matching `then` or `else`.", start_lineno),
            Some(start_lineno),
        ));
    }
    Ok((joined, j))
}

// ---------------------------------------------------------------------------
// Bind parsing
// ---------------------------------------------------------------------------

fn is_bind(text: &str) -> bool {
    let q = text.find('"').unwrap_or(text.len());
    let before_quote = &text[..q];
    before_quote.contains("<-") || before_quote.contains('←')
}

fn parse_bind_multiline(lines: &[Line], i: usize) -> Result<(Expr, usize), ParseError> {
    let line = &lines[i];
    let text = &line.text;
    let (op, op_len) = if text.contains("<-") { ("<-", 2) } else { ("←", "←".len()) };
    let op_pos = text.find(op).unwrap();
    let name = text[..op_pos].trim().to_string();
    if !name.chars().all(|c| c.is_alphanumeric() || c == '_') || name.is_empty() {
        return Err(parse_err(format!("invalid bind name: {:?}", name), Some(line.lineno)));
    }
    let rhs_start = text[op_pos + op_len..].trim().to_string();
    let (rhs_text, new_i) = gather_expr(lines, i, &rhs_start)?;
    let expr = safe_parse_expr(&rhs_text, line.lineno)?;
    // Body is a placeholder; compose_steps will fill it in.
    let placeholder = Expr::Lit { value: serde_json::Value::Null, type_: "Unit".into(), conf: 1.0, provenance: "literal".into() };
    Ok((Expr::Bind { name, expr: Box::new(expr), body: Box::new(placeholder) }, new_i))
}

// ---------------------------------------------------------------------------
// Step composition
// ---------------------------------------------------------------------------

fn compose_steps(steps: Vec<Expr>) -> Expr {
    if steps.len() == 1 { return steps.into_iter().next().unwrap(); }
    let mut iter = steps.into_iter();
    let head = iter.next().unwrap();
    let tail: Vec<Expr> = iter.collect();
    if let Expr::Bind { name, expr, .. } = head {
        return Expr::Bind { name, expr, body: Box::new(compose_steps(tail)) };
    }
    // Non-bind head: Seq(head, compose_steps(tail)) — mirrors Python's
    // `Seq(steps=(head, _compose_steps(tail)))` which nests rather than flattens.
    Expr::Seq { steps: vec![head, compose_steps(tail)] }
}

// ---------------------------------------------------------------------------
// Signature and effects parsing
// ---------------------------------------------------------------------------

fn parse_signature(rest: &str, line: usize) -> Result<(Vec<Param>, String), ParseError> {
    let arrow = if rest.contains("->") { "->" } else if rest.contains('→') { "→" } else {
        return Err(parse_err("signature missing `->`", Some(line)));
    };
    let arrow_pos = rest.find(arrow).unwrap();
    let lhs = rest[..arrow_pos].trim();
    let rhs = rest[arrow_pos + arrow.len()..].trim().to_string();
    if !lhs.starts_with('(') || !lhs.ends_with(')') {
        return Err(parse_err("signature params must be in parentheses", Some(line)));
    }
    let inside = lhs[1..lhs.len()-1].trim();
    let mut params = Vec::new();
    if !inside.is_empty() {
        for raw in split_top_level_commas(inside) {
            if !raw.contains(':') {
                return Err(parse_err(format!("param without type annotation: {:?}", raw), Some(line)));
            }
            let colon = raw.find(':').unwrap();
            let pname = raw[..colon].trim().to_string();
            let ptype = raw[colon+1..].trim().to_string();
            params.push(Param { name: pname, type_: ptype });
        }
    }
    Ok((params, rhs))
}

fn parse_effects(rest: &str, line: usize) -> Result<Vec<String>, ParseError> {
    let rest = rest.trim();
    if !rest.starts_with('{') || !rest.ends_with('}') {
        return Err(parse_err("effect set must be `{...}`", Some(line)));
    }
    let inside = rest[1..rest.len()-1].trim();
    if inside.is_empty() { return Ok(Vec::new()); }
    let mut items: Vec<String> = inside.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect();
    items.sort();
    items.dedup();
    Ok(items)
}

fn split_top_level_commas(s: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut depth = 0i32;
    let mut cur = String::new();
    for c in s.chars() {
        match c {
            '('|'['|'{' => { depth += 1; cur.push(c); }
            ')'|']'|'}' => { depth -= 1; cur.push(c); }
            ',' if depth == 0 => { out.push(cur.trim().to_string()); cur = String::new(); }
            _ => { cur.push(c); }
        }
    }
    if !cur.trim().is_empty() { out.push(cur.trim().to_string()); }
    out
}

// ---------------------------------------------------------------------------
// String literal parsing
// ---------------------------------------------------------------------------

fn parse_string_literal(s: &str, line: usize) -> Result<String, ParseError> {
    let s = s.trim();
    if !s.starts_with('"') || !s.ends_with('"') || s.len() < 2 {
        return Err(parse_err(format!("expected quoted string, got {:?}", s), Some(line)));
    }
    let inner = &s[1..s.len()-1];
    let mut out = String::new();
    let chars: Vec<char> = inner.chars().collect();
    let n = chars.len();
    let mut i = 0;
    while i < n {
        let c = chars[i];
        if c != '\\' { out.push(c); i += 1; continue; }
        if i + 1 >= n { return Err(parse_err("trailing backslash in string literal", Some(line))); }
        let esc = chars[i + 1];
        i += 2;
        match esc {
            'n' => out.push('\n'),
            't' => out.push('\t'),
            'r' => out.push('\r'),
            '\\' => out.push('\\'),
            '"' => out.push('"'),
            '0' => out.push('\0'),
            'u' => {
                if i + 4 > n { return Err(parse_err("\\u escape needs four hex digits", Some(line))); }
                let hex4: String = chars[i..i+4].iter().collect();
                i += 4;
                let cp = u32::from_str_radix(&hex4, 16).map_err(|_| parse_err(format!("invalid \\u escape: {:?}", hex4), Some(line)))?;
                let ch = char::from_u32(cp).ok_or_else(|| parse_err(format!("invalid unicode codepoint: U+{:04X}", cp), Some(line)))?;
                out.push(ch);
            }
            _ => { out.push('\\'); out.push(esc); }
        }
    }
    Ok(out)
}

// ---------------------------------------------------------------------------
// Preprocessing
// ---------------------------------------------------------------------------

fn preprocess(source: &str) -> Vec<Line> {
    let mut out = Vec::new();
    for (n, raw) in source.lines().enumerate() {
        let stripped = match raw.find('#') {
            Some(pos) => &raw[..pos],
            None => raw,
        };
        let stripped = stripped.trim_end();
        if stripped.trim().is_empty() { continue; }
        let indent = stripped.len() - stripped.trim_start().len();
        out.push(Line {
            indent,
            text: stripped.trim().to_string(),
            lineno: n + 1,
        });
    }
    out
}

fn split_head(text: &str) -> (String, String) {
    // Try multi-char keywords first (longest match)
    let keywords = [
        "intent", "effects", "believe", "module", "import", "bottom",
        "from", "post", "when", "cost", "cand", "else", "sig", "pre", "def",
        // Unicode glyphs
        "≡", "⟡", "σ", "⚡", "⊢", "⊣", "ƒ", "¿", "⊨", "⊥",
    ];
    for kw in &keywords {
        if text == *kw {
            if let Some(canon) = keyword_canon(kw) {
                return (canon.to_string(), String::new());
            }
            return (kw.to_string(), String::new());
        }
        let with_space = format!("{} ", kw);
        let with_tab = format!("{}\t", kw);
        if text.starts_with(&with_space) || text.starts_with(&with_tab) {
            let rest = text[kw.len()..].trim().to_string();
            let canon = keyword_canon(kw).unwrap_or(kw);
            return (canon.to_string(), rest);
        }
    }
    (String::new(), text.to_string())
}

fn safe_parse_expr(text: &str, line: usize) -> Result<Expr, ParseError> {
    parse_expr(text).map_err(|e| ParseError { message: e.0, line: Some(line) })
}
