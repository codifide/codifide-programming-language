//! Errors surfaced by the canonical form layer.
//!
//! Keeping errors small and typed so a future language-level error reporter
//! can attach source locations without guessing at kinds.

use std::fmt;

/// Errors from parsing or serializing Codifide canonical form.
#[derive(Debug)]
pub enum Error {
    /// Underlying JSON parse error.
    Json(serde_json::Error),
    /// The document was syntactically JSON but not a valid Codifide canonical
    /// form. The string describes what was wrong.
    Shape(String),
    /// Schema version tag does not match what this crate implements.
    UnsupportedVersion(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Json(e) => write!(f, "json: {e}"),
            Error::Shape(s) => write!(f, "shape: {s}"),
            Error::UnsupportedVersion(v) => {
                write!(f, "unsupported Codifide schema version: {v:?}")
            }
        }
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Error::Json(e) => Some(e),
            _ => None,
        }
    }
}

impl From<serde_json::Error> for Error {
    fn from(e: serde_json::Error) -> Self {
        Error::Json(e)
    }
}

/// Convenience for "this field was missing or the wrong JSON type."
pub(crate) fn shape<T: Into<String>>(msg: T) -> Error {
    Error::Shape(msg.into())
}
