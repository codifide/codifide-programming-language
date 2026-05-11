//! Codifide canonical form — Rust implementation.
//!
//! This crate is a second, independent implementation of the Codifide canonical
//! form specified in `docs/CANONICAL.md`. It deliberately does not include
//! an interpreter: the interpreter's semantics are still changing. The
//! canonical form is the stablest part of Codifide and the part where
//! agreement across implementations matters most, because it is what gets
//! content-addressed and shipped between agents.
//!
//! The reference Python implementation lives alongside this crate. The two
//! must agree on canonical byte form for every conforming program.

pub mod ast;
pub mod canonical;
pub mod cbor;
pub mod error;
pub mod json;

pub use ast::{Candidate, Definition, Expr, Module, Param, Signature};
pub use canonical::{canonical_bytes, content_hash};
pub use cbor::{canonical_cbor, content_hash_cbor};
pub use error::Error;
pub use json::{from_canonical_json, to_canonical_json};

/// Schema version implemented by this crate. Documents with any other
/// version tag are rejected.
pub const SCHEMA_VERSION: &str = "0.1";
