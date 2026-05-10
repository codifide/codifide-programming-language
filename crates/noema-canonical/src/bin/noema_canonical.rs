//! `noema-canonical` — small CLI that mirrors the subset of
//! `python3 -m noema canonical` relevant to canonical form agreement.
//!
//! Subcommands:
//!
//! - `bytes <file.json>`      — emit canonical JSON byte form.
//! - `hash <file.json>`       — print `sha256:<hex>` over canonical JSON bytes.
//! - `bytes-cbor <file.json>` — emit canonical CBOR byte form (RFC 8949 §4.2).
//! - `hash-cbor <file.json>`  — print `sha256:<hex>` over canonical CBOR bytes.
//!
//! The JSON subcommands are the v0.1 primary form; the CBOR subcommands
//! are the v0.2 binary form. Both agree byte-for-byte with the Python
//! reference implementation on every input the conformance test covers.
//!
//! This binary deliberately does not parse `.nm` surface syntax. The
//! Python reference is authoritative for parsing in v0.

use std::env;
use std::fs;
use std::io::{self, Write};
use std::process::ExitCode;

use noema_canonical::{
    canonical_bytes, canonical_cbor, content_hash, content_hash_cbor,
    from_canonical_json, to_canonical_json,
};

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        usage();
        return ExitCode::from(2);
    }
    match args[1].as_str() {
        "bytes" => run(&args[2], Format::JsonBytes),
        "hash" => run(&args[2], Format::JsonHash),
        "bytes-cbor" => run(&args[2], Format::CborBytes),
        "hash-cbor" => run(&args[2], Format::CborHash),
        other => {
            eprintln!("noema-canonical: unknown subcommand: {other}");
            usage();
            ExitCode::from(2)
        }
    }
}

fn usage() {
    eprintln!("usage: noema-canonical bytes      <file.json>");
    eprintln!("       noema-canonical hash       <file.json>");
    eprintln!("       noema-canonical bytes-cbor <file.json>");
    eprintln!("       noema-canonical hash-cbor  <file.json>");
}

enum Format {
    JsonBytes,
    JsonHash,
    CborBytes,
    CborHash,
}

fn run(path: &str, fmt: Format) -> ExitCode {
    match load_and_emit(path, fmt) {
        Ok(Output::Bytes(b)) => {
            if io::stdout().write_all(&b).is_err() {
                return ExitCode::from(1);
            }
            ExitCode::SUCCESS
        }
        Ok(Output::Text(s)) => {
            println!("{s}");
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("noema-canonical: {e}");
            ExitCode::from(1)
        }
    }
}

enum Output {
    Bytes(Vec<u8>),
    Text(String),
}

fn load_and_emit(path: &str, fmt: Format) -> Result<Output, Box<dyn std::error::Error>> {
    let src = fs::read_to_string(path)?;
    let parsed: serde_json::Value = serde_json::from_str(&src)?;
    // Round-trip through the AST so the byte form we emit reflects what
    // a Rust consumer would produce from its own in-memory form.
    let module = from_canonical_json(&parsed)?;
    let produced = to_canonical_json(&module);
    Ok(match fmt {
        Format::JsonBytes => Output::Bytes(canonical_bytes(&produced)?),
        Format::JsonHash => Output::Text(content_hash(&produced)?),
        Format::CborBytes => Output::Bytes(canonical_cbor(&produced)?),
        Format::CborHash => Output::Text(content_hash_cbor(&produced)?),
    })
}
