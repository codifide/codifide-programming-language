//! Codifide interpreter — Rust production runtime.
//!
//! Public API surface. The interpreter takes a parsed `Module` (from
//! `codifide-canonical`) and evaluates it.

pub mod errors;
pub mod interpreter;
pub mod parallel;
pub mod parser;
pub mod primitives;
pub mod value;

pub use errors::Error;
pub use interpreter::{run, Interpreter, DEFAULT_MAX_DEPTH};
pub use parser::{parse, ParseError};
pub use value::{payload_from_json, Payload, Value};
