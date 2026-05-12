//! JSON projection of the canonical AST.
//!
//! Two entry points:
//!
//!   - [`to_canonical_json`] turns a [`Module`] into a `serde_json::Value`.
//!   - [`from_canonical_json`] parses a `serde_json::Value` back into a
//!     [`Module`].
//!
//! Shape is fixed by `docs/CANONICAL.md`. Any deviation is a spec bug in
//! this crate, not a variant.

use serde_json::{json, Map, Value as JsonValue};

use crate::ast::{Candidate, Definition, Expr, Module, Param, Signature};
use crate::error::{shape, Error};
use crate::SCHEMA_VERSION;

// ---------------------------------------------------------------------------
// Module <-> JSON
// ---------------------------------------------------------------------------

pub fn to_canonical_json(m: &Module) -> JsonValue {
    let mut symbols = Map::new();
    for (name, def) in &m.symbols {
        symbols.insert(name.clone(), def_to_json(def));
    }
    let mut out = Map::new();
    out.insert("codifide".to_string(), JsonValue::String(SCHEMA_VERSION.to_string()));
    out.insert("module".to_string(), JsonValue::String(m.name.clone()));
    out.insert("symbols".to_string(), JsonValue::Object(symbols));
    // Imports are only emitted when present, matching the Python side.
    // Keys are sorted so the in-memory projection agrees with the
    // canonical byte form (which sorts keys at every depth anyway).
    if !m.imports.is_empty() {
        let mut imports = Map::new();
        let mut sorted = m.imports.clone();
        sorted.sort_by(|a, b| a.0.cmp(&b.0));
        for (name, identity) in sorted {
            imports.insert(name, JsonValue::String(identity));
        }
        out.insert("imports".to_string(), JsonValue::Object(imports));
    }
    JsonValue::Object(out)
}

pub fn from_canonical_json(v: &JsonValue) -> Result<Module, Error> {
    let obj = v.as_object().ok_or_else(|| shape("top-level must be object"))?;
    match obj.get("codifide").and_then(|v| v.as_str()) {
        Some(s) if s == SCHEMA_VERSION => {}
        Some(s) => return Err(Error::UnsupportedVersion(s.to_string())),
        None => return Err(shape("missing `codifide` version tag")),
    }
    let name = obj
        .get("module")
        .and_then(|v| v.as_str())
        .unwrap_or("main")
        .to_string();
    let symbols_obj = obj
        .get("symbols")
        .and_then(|v| v.as_object())
        .ok_or_else(|| shape("`symbols` must be an object"))?;
    let mut symbols = Vec::with_capacity(symbols_obj.len());
    for (k, v) in symbols_obj.iter() {
        symbols.push((k.clone(), def_from_json(v)?));
    }
    // Imports are optional; when present, preserve their order (which
    // by now is sorted, since the canonical form sorts).
    let mut imports: Vec<(String, String)> = Vec::new();
    if let Some(imports_obj) = obj.get("imports").and_then(|v| v.as_object()) {
        for (k, v) in imports_obj.iter() {
            let identity = v
                .as_str()
                .ok_or_else(|| shape("import value must be string"))?
                .to_string();
            imports.push((k.clone(), identity));
        }
    }
    Ok(Module {
        name,
        symbols,
        imports,
    })
}

// ---------------------------------------------------------------------------
// Definition
// ---------------------------------------------------------------------------

fn def_to_json(d: &Definition) -> JsonValue {
    json!({
        "kind": "definition",
        "intent": d.intent,
        "signature": sig_to_json(&d.signature),
        "pre": d.pre.iter().map(expr_to_json).collect::<Vec<_>>(),
        "post": d.post.iter().map(expr_to_json).collect::<Vec<_>>(),
        "candidates": d.candidates.iter().map(cand_to_json).collect::<Vec<_>>(),
    })
}

fn def_from_json(v: &JsonValue) -> Result<Definition, Error> {
    let obj = v.as_object().ok_or_else(|| shape("definition must be object"))?;
    let intent = obj
        .get("intent")
        .and_then(|v| v.as_str())
        .ok_or_else(|| shape("definition.intent missing or not a string"))?
        .to_string();
    let signature = sig_from_json(obj.get("signature").unwrap_or(&JsonValue::Null))?;
    let pre = array_of_exprs(obj.get("pre"))?;
    let post = array_of_exprs(obj.get("post"))?;
    let candidates_json = obj
        .get("candidates")
        .and_then(|v| v.as_array())
        .ok_or_else(|| shape("definition.candidates must be array"))?;
    let candidates = candidates_json
        .iter()
        .map(cand_from_json)
        .collect::<Result<Vec<_>, _>>()?;
    Ok(Definition {
        intent,
        signature,
        pre,
        post,
        candidates,
    })
}

fn sig_to_json(s: &Signature) -> JsonValue {
    // Effects are emitted sorted. We clone and sort defensively in case an
    // upstream caller left them unsorted.
    let mut effects = s.effects.clone();
    effects.sort();
    json!({
        "params": s
            .params
            .iter()
            .map(|p| json!({"name": p.name, "type": p.type_}))
            .collect::<Vec<_>>(),
        "returns": s.returns,
        "effects": effects,
    })
}

fn sig_from_json(v: &JsonValue) -> Result<Signature, Error> {
    if v.is_null() {
        return Ok(Signature {
            params: vec![],
            returns: "Any".to_string(),
            effects: vec![],
        });
    }
    let obj = v.as_object().ok_or_else(|| shape("signature must be object"))?;
    let params = match obj.get("params").and_then(|v| v.as_array()) {
        Some(arr) => arr
            .iter()
            .map(|p| {
                let p = p
                    .as_object()
                    .ok_or_else(|| shape("param must be object"))?;
                Ok::<_, Error>(Param {
                    name: p
                        .get("name")
                        .and_then(|v| v.as_str())
                        .ok_or_else(|| shape("param.name missing"))?
                        .to_string(),
                    type_: p
                        .get("type")
                        .and_then(|v| v.as_str())
                        .unwrap_or("Any")
                        .to_string(),
                })
            })
            .collect::<Result<Vec<_>, _>>()?,
        None => vec![],
    };
    let returns = obj
        .get("returns")
        .and_then(|v| v.as_str())
        .unwrap_or("Any")
        .to_string();
    let mut effects = match obj.get("effects").and_then(|v| v.as_array()) {
        Some(arr) => arr
            .iter()
            .filter_map(|v| v.as_str().map(|s| s.to_string()))
            .collect::<Vec<_>>(),
        None => vec![],
    };
    effects.sort();
    effects.dedup();
    Ok(Signature {
        params,
        returns,
        effects,
    })
}

fn cand_to_json(c: &Candidate) -> JsonValue {
    let guard = match &c.guard {
        Some(g) => expr_to_json(g),
        None => JsonValue::Null,
    };
    // Build the base object; only emit `cost` when present so the
    // canonical bytes of un-annotated candidates stay identical to
    // the pre-amendment form (no existing hash invalidated). Cost,
    // when present, is a non-negative integer.
    let mut obj = serde_json::Map::new();
    obj.insert("body".to_string(), expr_to_json(&c.body));
    if let Some(cost) = c.cost {
        obj.insert("cost".to_string(), JsonValue::from(cost));
    }
    obj.insert("guard".to_string(), guard);
    obj.insert("intent".to_string(), JsonValue::String(c.intent.clone()));
    obj.insert("kind".to_string(), JsonValue::String("candidate".to_string()));
    JsonValue::Object(obj)
}

fn cand_from_json(v: &JsonValue) -> Result<Candidate, Error> {
    let obj = v.as_object().ok_or_else(|| shape("candidate must be object"))?;
    let intent = obj
        .get("intent")
        .and_then(|v| v.as_str())
        .unwrap_or("default")
        .to_string();
    let guard = match obj.get("guard") {
        Some(JsonValue::Null) | None => None,
        Some(g) => Some(expr_from_json(g)?),
    };
    let body = expr_from_json(
        obj.get("body").ok_or_else(|| shape("candidate.body missing"))?,
    )?;
    // `cost` is optional. When present it MUST be a non-negative
    // integer representable as u64. Anything else is a typed shape
    // error — the canonical-form typing contract mandates this.
    let cost = match obj.get("cost") {
        None | Some(JsonValue::Null) => None,
        Some(v) => {
            let n = v
                .as_u64()
                .ok_or_else(|| shape("candidate.cost must be a non-negative integer"))?;
            Some(n)
        }
    };
    Ok(Candidate {
        intent,
        guard,
        body,
        cost,
    })
}

// ---------------------------------------------------------------------------
// Expressions
// ---------------------------------------------------------------------------

fn expr_to_json(e: &Expr) -> JsonValue {
    match e {
        Expr::Lit {
            value,
            type_,
            conf,
            provenance,
        } => json!({
            "kind": "lit",
            "value": value,
            "type": type_,
            "conf": conf,
            "provenance": provenance,
        }),
        Expr::Ref { name } => json!({"kind": "ref", "name": name}),
        Expr::Call { fn_, args } => json!({
            "kind": "call",
            "fn": fn_,
            "args": args.iter().map(expr_to_json).collect::<Vec<_>>(),
        }),
        Expr::Bind { name, expr, body } => json!({
            "kind": "bind",
            "name": name,
            "expr": expr_to_json(expr),
            "in": expr_to_json(body),
        }),
        Expr::Seq { steps } => json!({
            "kind": "seq",
            "steps": steps.iter().map(expr_to_json).collect::<Vec<_>>(),
        }),
        Expr::Believe {
            subject,
            arms,
            otherwise,
        } => json!({
            "kind": "believe",
            "subject": expr_to_json(subject),
            "arms": arms
                .iter()
                .map(|(c, v)| JsonValue::Array(vec![expr_to_json(c), expr_to_json(v)]))
                .collect::<Vec<_>>(),
            "else": expr_to_json(otherwise),
        }),
        Expr::Bottom => json!({"kind": "bottom"}),
        Expr::Concat { parts } => json!({
            "kind": "concat",
            "parts": parts.iter().map(expr_to_json).collect::<Vec<_>>(),
        }),
        Expr::Attr { target, name } => json!({
            "kind": "attr",
            "target": expr_to_json(target),
            "name": name,
        }),
        Expr::If { cond, then_, else_ } => json!({
            "kind": "if",
            "cond": expr_to_json(cond),
            "then": expr_to_json(then_),
            "else": expr_to_json(else_),
        }),
    }
}

fn expr_from_json(v: &JsonValue) -> Result<Expr, Error> {
    let obj = v.as_object().ok_or_else(|| shape("expression must be object"))?;
    let kind = obj
        .get("kind")
        .and_then(|v| v.as_str())
        .ok_or_else(|| shape("expression missing `kind`"))?;
    match kind {
        "lit" => Ok(Expr::Lit {
            value: obj.get("value").cloned().unwrap_or(JsonValue::Null),
            type_: obj
                .get("type")
                .and_then(|v| v.as_str())
                .unwrap_or("Any")
                .to_string(),
            conf: obj
                .get("conf")
                .and_then(|v| v.as_f64())
                .unwrap_or(1.0),
            provenance: obj
                .get("provenance")
                .and_then(|v| v.as_str())
                .unwrap_or("literal")
                .to_string(),
        }),
        "ref" => Ok(Expr::Ref {
            name: obj
                .get("name")
                .and_then(|v| v.as_str())
                .ok_or_else(|| shape("ref.name missing"))?
                .to_string(),
        }),
        "call" => Ok(Expr::Call {
            fn_: obj
                .get("fn")
                .and_then(|v| v.as_str())
                .ok_or_else(|| shape("call.fn missing"))?
                .to_string(),
            args: array_of_exprs(obj.get("args"))?,
        }),
        "bind" => Ok(Expr::Bind {
            name: obj
                .get("name")
                .and_then(|v| v.as_str())
                .ok_or_else(|| shape("bind.name missing"))?
                .to_string(),
            expr: Box::new(expr_from_json(
                obj.get("expr").ok_or_else(|| shape("bind.expr missing"))?,
            )?),
            body: Box::new(expr_from_json(
                obj.get("in").ok_or_else(|| shape("bind.in missing"))?,
            )?),
        }),
        "seq" => Ok(Expr::Seq {
            steps: array_of_exprs(obj.get("steps"))?,
        }),
        "believe" => {
            let subject = Box::new(expr_from_json(
                obj.get("subject")
                    .ok_or_else(|| shape("believe.subject missing"))?,
            )?);
            let arms_json = obj
                .get("arms")
                .and_then(|v| v.as_array())
                .ok_or_else(|| shape("believe.arms missing"))?;
            let mut arms = Vec::with_capacity(arms_json.len());
            for a in arms_json {
                let pair = a
                    .as_array()
                    .ok_or_else(|| shape("believe arm must be [cond, value]"))?;
                if pair.len() != 2 {
                    return Err(shape("believe arm must have exactly two elements"));
                }
                arms.push((expr_from_json(&pair[0])?, expr_from_json(&pair[1])?));
            }
            let otherwise = Box::new(expr_from_json(
                obj.get("else")
                    .ok_or_else(|| shape("believe.else missing (required)"))?,
            )?);
            Ok(Expr::Believe {
                subject,
                arms,
                otherwise,
            })
        }
        "bottom" => Ok(Expr::Bottom),
        "concat" => Ok(Expr::Concat {
            parts: array_of_exprs(obj.get("parts"))?,
        }),
        "attr" => Ok(Expr::Attr {
            target: Box::new(expr_from_json(
                obj.get("target").ok_or_else(|| shape("attr.target missing"))?,
            )?),
            name: obj
                .get("name")
                .and_then(|v| v.as_str())
                .ok_or_else(|| shape("attr.name missing"))?
                .to_string(),
        }),
        "if" => Ok(Expr::If {
            cond: Box::new(expr_from_json(
                obj.get("cond").ok_or_else(|| shape("if.cond missing"))?,
            )?),
            then_: Box::new(expr_from_json(
                obj.get("then").ok_or_else(|| shape("if.then missing"))?,
            )?),
            else_: Box::new(expr_from_json(
                obj.get("else").ok_or_else(|| shape("if.else missing"))?,
            )?),
        }),
        other => Err(shape(format!("unknown expression kind: {other:?}"))),
    }
}

fn array_of_exprs(opt: Option<&JsonValue>) -> Result<Vec<Expr>, Error> {
    match opt {
        None | Some(JsonValue::Null) => Ok(vec![]),
        Some(v) => {
            let arr = v
                .as_array()
                .ok_or_else(|| shape("expected array of expressions"))?;
            arr.iter().map(expr_from_json).collect()
        }
    }
}
