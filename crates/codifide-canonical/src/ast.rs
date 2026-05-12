//! Canonical AST.
//!
//! Mirrors the Python dataclasses in `codifide/core/types.py`. Types are kept
//! deliberately plain-data: no interior mutability, no trait magic. The
//! point is that a second implementation sees the same shape the first
//! one does.
//!
//! `Expr` is the tagged-union expression node. Every variant corresponds to
//! a `kind` discriminator in the JSON projection.

use serde_json::Value as JsonValue;

/// A module: a named collection of definitions, plus optional imports
/// bound by content identity.
///
/// Imports are resolved through a symbol store at runtime. Their
/// canonical form is a sorted map from local name to `sha256:<hex>`
/// identity; the sort is what makes import-declaration order
/// irrelevant to content hashing.
#[derive(Debug, Clone, PartialEq)]
pub struct Module {
    pub name: String,
    pub symbols: Vec<(String, Definition)>,
    pub imports: Vec<(String, String)>,
}

/// A function definition. Contract-primary, implementations plural.
///
/// The *name* is carried at the `symbols` map level, not inside the
/// definition body — matching the spec's top-level shape. Keeping it out
/// of the struct prevents the same name from appearing in two places and
/// disagreeing with itself.
#[derive(Debug, Clone, PartialEq)]
pub struct Definition {
    pub intent: String,
    pub signature: Signature,
    pub pre: Vec<Expr>,
    pub post: Vec<Expr>,
    pub candidates: Vec<Candidate>,
}

/// A single parameter.
#[derive(Debug, Clone, PartialEq)]
pub struct Param {
    pub name: String,
    pub type_: String,
}

/// Type and effect signature.
///
/// Effects are represented as a sorted `Vec<String>` rather than a `HashSet`
/// so that iteration order is stable and matches the canonical serialization
/// rule (effect arrays are sorted lexicographically).
#[derive(Debug, Clone, PartialEq)]
pub struct Signature {
    pub params: Vec<Param>,
    pub returns: String,
    pub effects: Vec<String>,
}

/// One implementation of a definition's contract.
///
/// `cost` is the optional dispatcher cost annotation added in the
/// 2026-05-11 spec amendment. Absent → effective cost +∞; present
/// → non-negative integer. Among satisfied candidates, the dispatcher
/// picks the smallest cost with declaration order as tiebreaker.
#[derive(Debug, Clone, PartialEq)]
pub struct Candidate {
    pub intent: String,
    pub guard: Option<Expr>,
    pub body: Expr,
    pub cost: Option<u64>,
}

/// Expression AST.
///
/// Variants are named after the `kind` discriminator in canonical JSON.
/// `Lit::value` stays as raw JSON so literal payloads can be anything the
/// host permits (string, number, bool, null, or structured data).
#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Lit {
        value: JsonValue,
        type_: String,
        conf: f64,
        provenance: String,
    },
    Ref {
        name: String,
    },
    Call {
        fn_: String,
        args: Vec<Expr>,
    },
    Bind {
        name: String,
        expr: Box<Expr>,
        body: Box<Expr>,
    },
    Seq {
        steps: Vec<Expr>,
    },
    Believe {
        subject: Box<Expr>,
        arms: Vec<(Expr, Expr)>,
        otherwise: Box<Expr>,
    },
    Bottom,
    Concat {
        parts: Vec<Expr>,
    },
    Attr {
        target: Box<Expr>,
        name: String,
    },
    /// Inline conditional expression — short-circuit.
    ///
    /// Added 2026-05-11. Exactly one of ``then_`` / ``else_``
    /// evaluates at runtime, chosen by the truthiness of
    /// ``cond``. Unlike candidate-dispatch guards (which all
    /// evaluate before selection), an ``If`` expression can
    /// gate an expression that would otherwise raise, e.g.
    /// indexing a string past its length.
    If {
        cond: Box<Expr>,
        then_: Box<Expr>,
        else_: Box<Expr>,
    },
}
