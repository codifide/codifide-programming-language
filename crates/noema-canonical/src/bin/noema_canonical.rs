//! `noema-canonical` — small CLI that mirrors the subset of
//! `python3 -m noema canonical` relevant to canonical form agreement.
//!
//! Subcommands:
//!
//! - `bytes <file.json>`     — emit canonical byte form of a canonical JSON
//!   document (reads JSON, round-trips through the Rust AST, writes
//!   canonical bytes to stdout).
//! - `hash <file.json>`      — print `sha256:<hex>` over canonical byte form.
//!
//! This binary deliberately does not parse `.nm` surface syntax. The Python
//! reference is authoritative for parsing in v0. The Rust side consumes the
//! canonical JSON the Python side produces, re-serializes, and hashes. That
//! is the tightest possible conformance surface without duplicating the
//! parser — and the parser is exactly the part that is still changing.

use std::env;
use std::fs;
use std::io::{self, Write};
use std::process::ExitCode;

use noema_canonical::{canonical_bytes, content_hash, from_canonical_json, to_canonical_json};

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        usage();
        return ExitCode::from(2);
    }
    match args[1].as_str() {
        "bytes" => run_bytes(&args[2]),
        "hash" => run_hash(&args[2]),
        other => {
            eprintln!("noema-canonical: unknown subcommand: {other}");
            usage();
            ExitCode::from(2)
        }
    }
}

fn usage() {
    eprintln!("usage: noema-canonical bytes <file.json>");
    eprintln!("       noema-canonical hash  <file.json>");
}

fn run_bytes(path: &str) -> ExitCode {
    match load_and_roundtrip(path) {
        Ok(bytes) => {
            if io::stdout().write_all(&bytes).is_err() {
                return ExitCode::from(1);
            }
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("noema-canonical: {e}");
            ExitCode::from(1)
        }
    }
}

fn run_hash(path: &str) -> ExitCode {
    match load_and_hash(path) {
        Ok(h) => {
            println!("{h}");
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("noema-canonical: {e}");
            ExitCode::from(1)
        }
    }
}

fn load_and_roundtrip(path: &str) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let src = fs::read_to_string(path)?;
    let parsed: serde_json::Value = serde_json::from_str(&src)?;
    // Round-trip through the AST so the byte form we emit reflects what a
    // Rust consumer would produce from its own in-memory form, not just the
    // normalization of whatever JSON we happened to read.
    let module = from_canonical_json(&parsed)?;
    let produced = to_canonical_json(&module);
    Ok(canonical_bytes(&produced)?)
}

fn load_and_hash(path: &str) -> Result<String, Box<dyn std::error::Error>> {
    let src = fs::read_to_string(path)?;
    let parsed: serde_json::Value = serde_json::from_str(&src)?;
    let module = from_canonical_json(&parsed)?;
    let produced = to_canonical_json(&module);
    Ok(content_hash(&produced)?)
}
