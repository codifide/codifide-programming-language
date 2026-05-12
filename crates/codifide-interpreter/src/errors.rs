//! Typed error hierarchy for the Codifide interpreter.
//!
//! Mirrors `codifide/runtime/errors.py`. All eight typed error classes
//! plus the base `CodifideError`. The Python side raises exceptions;
//! the Rust side returns `Result<_, Error>`.

use std::fmt;

/// Base error type. All Codifide runtime errors are variants of this enum.
#[derive(Debug)]
pub enum Error {
    /// A primitive call failed (wraps the underlying cause as a string).
    Primitive { fn_: String, cause: String },
    /// A precondition or postcondition did not hold.
    Contract {
        fn_: String,
        kind: &'static str, // "pre" or "post"
        clause: String,
        intent: String,
    },
    /// A function performed an effect its signature did not declare.
    Effect {
        fn_: String,
        declared: Vec<String>,
        observed: String,
    },
    /// No candidate guard matched during dispatch.
    Dispatch { fn_: String },
    /// Bottom escaped a context that did not handle it.
    Refusal { fn_: String },
    /// Call depth exceeded the interpreter's limit.
    RecursionLimit { depth: usize },
    /// Bottom reached a primitive that cannot consume it.
    BottomPropagation { fn_: String },
    /// A module has imports but no store was provided.
    MissingStore { module: String },
    /// An import could not be resolved.
    UnresolvedImport { name: String, identity: String },
    /// General interpreter error (unbound name, unknown callable, etc.).
    General(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Primitive { fn_, cause } => {
                write!(f, "primitive '{fn_}' failed: {cause}")
            }
            Error::Contract { fn_, kind, clause, intent } => {
                write!(
                    f,
                    "'{fn_}' failed {kind}condition `{clause}`. \
                     The function exists because: {intent:?}"
                )
            }
            Error::Effect { fn_, declared, observed } => {
                write!(
                    f,
                    "'{fn_}' performed effect '{observed}' which is not in its \
                     declared set {declared:?}"
                )
            }
            Error::Dispatch { fn_ } => {
                write!(
                    f,
                    "No candidate of '{fn_}' matched. Add a default candidate \
                     (one with no `when` guard) to guarantee dispatch."
                )
            }
            Error::Refusal { fn_ } => {
                write!(
                    f,
                    "'{fn_}' returned ⊥ (refusal) and no caller chose to handle it. \
                     Refusal is first-class in Codifide; handle it in a `believe` arm \
                     or at the call site."
                )
            }
            Error::RecursionLimit { depth } => {
                write!(
                    f,
                    "Codifide call depth exceeded {depth}. Raise the limit on the \
                     Interpreter or refactor the program to avoid unbounded recursion."
                )
            }
            Error::BottomPropagation { fn_ } => {
                write!(
                    f,
                    "primitive '{fn_}' received ⊥ (refusal) as an argument. \
                     Handle the refusal in a `believe` arm before calling \
                     primitives that need a concrete value."
                )
            }
            Error::MissingStore { module } => {
                write!(
                    f,
                    "module {module:?} has imports but no store was provided \
                     to resolve them."
                )
            }
            Error::UnresolvedImport { name, identity } => {
                write!(f, "cannot resolve import {name:?} = {identity}")
            }
            Error::General(msg) => write!(f, "{msg}"),
        }
    }
}

impl std::error::Error for Error {}

/// Convenience constructor.
pub fn general(msg: impl Into<String>) -> Error {
    Error::General(msg.into())
}
