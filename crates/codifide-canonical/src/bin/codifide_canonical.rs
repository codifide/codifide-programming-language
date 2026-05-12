//! `codifide-canonical` — small CLI that mirrors the subset of
//! `python3 -m codifide canonical` relevant to canonical form agreement.
//!
//! Subcommands that take canonical **JSON text** input:
//!
//! - `bytes <file.json>`      — emit canonical JSON byte form.
//! - `hash <file.json>`       — print `sha256:<hex>` (primary, CBOR since 2026-05-11).
//! - `bytes-cbor <file.json>` — emit canonical CBOR byte form (RFC 8949 §4.2).
//! - `hash-cbor <file.json>`  — alias of `hash`; explicit naming for callers
//!                              who want the wire form obvious at the call site.
//! - `hash-json <file.json>`  — legacy JSON-byte content identity.
//!
//! Subcommands that take canonical **CBOR byte** input:
//!
//! - `bytes-cbor-in <file.cbor>` — round-trip CBOR bytes through the
//!                                  crate's decoder + encoder.
//! - `hash-cbor-in <file.cbor>`  — print `sha256:<hex>` of the decoded
//!                                  value's canonical CBOR re-encoding.
//!
//! The `-in` variants exist to close AUD-2026-05-11-08's residual
//! surface: when input is provided as CBOR bytes, the crate bypasses
//! `serde_json::from_str` entirely, so the JSON decimal-parser
//! divergence that caused f16-class content-hash splits cannot bite.
//!
//! This binary deliberately does not parse `.cod` surface syntax. The
//! Python reference is authoritative for parsing in v0.

use std::env;
use std::fs::File;
use std::io::{self, Read, Write};
use std::process::ExitCode;

use codifide_canonical::{
    canonical_bytes, canonical_cbor, content_hash, content_hash_cbor,
    decode_canonical_cbor, from_canonical_json, to_canonical_json,
};

/// Maximum input size. A canonical Codifide module is typically under
/// 100 KiB; 64 MiB is generously larger than any legitimate module
/// while bounding adversarial reads. Without this cap, passing
/// ``/dev/zero`` as the input file hangs indefinitely — the
/// 2026-05-10 CBOR audit filed this as P1-7.
const MAX_INPUT_BYTES: u64 = 64 * 1024 * 1024;

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        usage();
        return ExitCode::from(2);
    }
    match args[1].as_str() {
        "bytes" => run(&args[2], Format::JsonBytes),
        // `hash` is the primary content identity; as of 2026-05-11 it hashes
        // over canonical CBOR bytes. `hash-cbor` is an explicit alias.
        // `hash-json` preserves the legacy JSON-byte identity for callers
        // that need to reproduce pre-migration hashes.
        "hash" | "hash-cbor" => run(&args[2], Format::CborHash),
        "hash-json" => run(&args[2], Format::JsonHash),
        "bytes-cbor" => run(&args[2], Format::CborBytes),
        // CBOR-input subcommands: accept canonical CBOR bytes as
        // input, bypass serde_json::from_str entirely. See AUD-08
        // residual-surface note in the module docs.
        "hash-cbor-in" => run_cbor_in(&args[2], CborInFormat::Hash),
        "bytes-cbor-in" => run_cbor_in(&args[2], CborInFormat::Bytes),
        other => {
            eprintln!("codifide-canonical: unknown subcommand: {other}");
            usage();
            ExitCode::from(2)
        }
    }
}

fn usage() {
    eprintln!("usage: codifide-canonical bytes         <file.json>");
    eprintln!("       codifide-canonical hash          <file.json>   # primary (CBOR) identity");
    eprintln!("       codifide-canonical hash-cbor     <file.json>   # alias of hash");
    eprintln!("       codifide-canonical hash-json     <file.json>   # legacy JSON identity");
    eprintln!("       codifide-canonical bytes-cbor    <file.json>");
    eprintln!("       codifide-canonical hash-cbor-in  <file.cbor>   # CBOR-bytes input, closes AUD-08 surface");
    eprintln!("       codifide-canonical bytes-cbor-in <file.cbor>   # CBOR-bytes input, round-trip");
}

enum Format {
    JsonBytes,
    JsonHash,
    CborBytes,
    CborHash,
}

enum CborInFormat {
    /// Decode canonical CBOR input, re-encode it, and hash the
    /// re-encoding. The hash is stable because the re-encoding is
    /// canonical-by-construction; the decoder enforces that on read.
    Hash,
    /// Decode canonical CBOR input and re-emit canonical CBOR bytes.
    /// For valid canonical input, this is a byte-identical round-trip
    /// — a useful conformance probe.
    Bytes,
}

fn run_cbor_in(path: &str, fmt: CborInFormat) -> ExitCode {
    match load_cbor_and_emit(path, fmt) {
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
            eprintln!("codifide-canonical: {e}");
            ExitCode::from(1)
        }
    }
}

fn load_cbor_and_emit(path: &str, fmt: CborInFormat) -> Result<Output, Box<dyn std::error::Error>> {
    let src = read_bounded(path)?;
    // Canonical CBOR decoder — strict; rejects non-shortest heads,
    // unsorted map keys, indefinite-length encodings, NaN/infinity,
    // trailing bytes. On success we hold a serde_json::Value shaped
    // identically to what from_canonical_json would have produced,
    // but without the JSON-text parsing step.
    let value = decode_canonical_cbor(&src)?;
    let module = from_canonical_json(&value)?;
    let produced = to_canonical_json(&module);
    Ok(match fmt {
        CborInFormat::Hash => Output::Text(content_hash_cbor(&produced)?),
        CborInFormat::Bytes => Output::Bytes(canonical_cbor(&produced)?),
    })
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
            eprintln!("codifide-canonical: {e}");
            ExitCode::from(1)
        }
    }
}

enum Output {
    Bytes(Vec<u8>),
    Text(String),
}

fn load_and_emit(path: &str, fmt: Format) -> Result<Output, Box<dyn std::error::Error>> {
    let src = read_bounded(path)?;
    let parsed: serde_json::Value = serde_json::from_slice(&src)?;
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

/// Read ``path`` into memory, capped at ``MAX_INPUT_BYTES``. Exceeding the
/// cap is a hard error — we would rather refuse a legitimate large file
/// than hang on ``/dev/zero`` or be starved by a slow producer.
fn read_bounded(path: &str) -> io::Result<Vec<u8>> {
    let file = File::open(path)?;
    let mut buf = Vec::new();
    // `take` limits bytes read before EOF; past the cap we peek one more
    // byte to distinguish "exactly cap bytes" from "larger than cap".
    let mut limited = file.take(MAX_INPUT_BYTES + 1);
    limited.read_to_end(&mut buf)?;
    if buf.len() as u64 > MAX_INPUT_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            format!(
                "input exceeds {} bytes; refuse to read more",
                MAX_INPUT_BYTES
            ),
        ));
    }
    Ok(buf)
}
