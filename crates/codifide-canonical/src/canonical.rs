//! Canonical byte form and content addressing.
//!
//! The canonical byte form is deterministic: the same semantic document
//! produces the same bytes, regardless of author input ordering. This is
//! what gets hashed for content addressing.
//!
//! Rules (mirror `docs/CANONICAL.md §Canonical serialization`):
//!
//! - UTF-8, no BOM, no insignificant whitespace.
//! - Object keys sorted lexicographically at every depth.
//! - Arrays preserve order.
//! - Numbers serialized as `serde_json` does (shortest round-trippable
//!   decimal for `f64`). This matches Python `json.dumps` closely; the
//!   conformance test catches any edge cases.
//! - **Strings are ASCII-escaped.** Any codepoint above U+007F is emitted
//!   as `\uXXXX` (or a surrogate pair for codepoints above U+FFFF). This
//!   matches Python's `json.dumps(ensure_ascii=True)` byte-for-byte and is
//!   the choice the spec mandates so the byte form is transport-neutral.
//!   Security audit P0-2 (2026-05-10) discovered the previous
//!   `serde_json::to_vec` path did not escape non-ASCII and produced
//!   different bytes than Python; the custom encoder below corrects that.

use serde_json::{Map, Value};
use sha2::{Digest, Sha256};

use crate::error::Error;

/// Produce the canonical byte form of a Codifide JSON document.
///
/// Accepts a parsed `serde_json::Value`; callers who have raw bytes should
/// parse first. This lets the same function serve both "I already have an
/// AST-sourced Value" and "I just parsed some JSON" flows.
pub fn canonical_bytes(v: &Value) -> Result<Vec<u8>, Error> {
    let normalized = normalize(v);
    let mut out: Vec<u8> = Vec::new();
    write_canonical(&normalized, &mut out);
    Ok(out)
}

/// Content hash: SHA-256 of the canonical byte form, hex-encoded with the
/// `sha256:` prefix mandated by the spec.
pub fn content_hash(v: &Value) -> Result<String, Error> {
    let bytes = canonical_bytes(v)?;
    let mut hasher = Sha256::new();
    hasher.update(&bytes);
    let digest = hasher.finalize();
    let mut hex = String::with_capacity(7 + digest.len() * 2);
    hex.push_str("sha256:");
    for b in digest {
        // Manual hex — avoids pulling in a `hex` crate for six bytes of code.
        hex.push(HEX[(b >> 4) as usize] as char);
        hex.push(HEX[(b & 0x0f) as usize] as char);
    }
    Ok(hex)
}

const HEX: &[u8] = b"0123456789abcdef";

/// Recursively sort object keys; leave arrays, strings, numbers, bools, and
/// null unchanged.
fn normalize(v: &Value) -> Value {
    match v {
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            let mut out = Map::with_capacity(map.len());
            for k in keys {
                out.insert(k.clone(), normalize(&map[k]));
            }
            Value::Object(out)
        }
        Value::Array(arr) => Value::Array(arr.iter().map(normalize).collect()),
        other => other.clone(),
    }
}

/// Write a normalized JSON value to a byte buffer using the canonical rules.
///
/// This function is the heart of cross-implementation agreement. The Python
/// reference uses `json.dumps(..., sort_keys=True, separators=(",", ":"),
/// ensure_ascii=True)`. We match it byte-for-byte:
///
/// - No whitespace between tokens.
/// - Object keys sorted (already done by `normalize`).
/// - Numbers emitted through `serde_json`'s default formatter — which for
///   `f64` produces the shortest round-trippable decimal, matching Python's
///   `repr(float)` in the cases we need.
/// - Strings with every codepoint > 0x7F emitted as `\uXXXX`, exactly as
///   Python does when `ensure_ascii=True`.
fn write_canonical(v: &Value, out: &mut Vec<u8>) {
    match v {
        Value::Null => out.extend_from_slice(b"null"),
        Value::Bool(true) => out.extend_from_slice(b"true"),
        Value::Bool(false) => out.extend_from_slice(b"false"),
        Value::Number(n) => {
            // Integers as-is; floats via serde_json's shortest representation.
            // This matches Python json.dumps for all values in the current
            // test suite; numeric-edge cases are called out as an unknown in
            // the security audit and will get a dedicated fixture.
            out.extend_from_slice(n.to_string().as_bytes());
        }
        Value::String(s) => write_string_ascii_escaped(s, out),
        Value::Array(arr) => {
            out.push(b'[');
            for (i, item) in arr.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                write_canonical(item, out);
            }
            out.push(b']');
        }
        Value::Object(map) => {
            // `normalize` already sorted; we trust that here.
            out.push(b'{');
            for (i, (k, val)) in map.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                write_string_ascii_escaped(k, out);
                out.push(b':');
                write_canonical(val, out);
            }
            out.push(b'}');
        }
    }
}

/// Write a JSON string with ASCII-only output.
///
/// Matches Python's `json.dumps(..., ensure_ascii=True)` exactly:
///
/// - `"` → `\"`
/// - `\\` → `\\\\`
/// - control bytes (0x00..0x1F) → `\uXXXX` lowercase hex, or named escapes
///   for `\b \f \n \r \t`
/// - every BMP codepoint above 0x7E → `\uXXXX` lowercase hex
/// - every non-BMP codepoint → UTF-16 surrogate pair `\uXXXX\uXXXX`
///
/// The lowercase-hex detail matters: Python uses lowercase and byte
/// comparison breaks on case.
fn write_string_ascii_escaped(s: &str, out: &mut Vec<u8>) {
    out.push(b'"');
    for ch in s.chars() {
        match ch {
            '"' => out.extend_from_slice(b"\\\""),
            '\\' => out.extend_from_slice(b"\\\\"),
            '\u{0008}' => out.extend_from_slice(b"\\b"),
            '\u{000C}' => out.extend_from_slice(b"\\f"),
            '\n' => out.extend_from_slice(b"\\n"),
            '\r' => out.extend_from_slice(b"\\r"),
            '\t' => out.extend_from_slice(b"\\t"),
            c if (c as u32) < 0x20 => write_u_escape(c as u32, out),
            c if (c as u32) < 0x7F => out.push(c as u8),
            // 0x7F is a control character; Python emits it literally as
            // 0x7F since it's within ASCII. Match that behavior.
            c if (c as u32) == 0x7F => out.push(0x7F),
            c => {
                let cp = c as u32;
                if cp <= 0xFFFF {
                    write_u_escape(cp, out);
                } else {
                    // Encode as UTF-16 surrogate pair.
                    let adjusted = cp - 0x10000;
                    let high = 0xD800 + (adjusted >> 10);
                    let low = 0xDC00 + (adjusted & 0x3FF);
                    write_u_escape(high, out);
                    write_u_escape(low, out);
                }
            }
        }
    }
    out.push(b'"');
}

fn write_u_escape(cp: u32, out: &mut Vec<u8>) {
    out.extend_from_slice(b"\\u");
    out.push(HEX[((cp >> 12) & 0xF) as usize]);
    out.push(HEX[((cp >> 8) & 0xF) as usize]);
    out.push(HEX[((cp >> 4) & 0xF) as usize]);
    out.push(HEX[(cp & 0xF) as usize]);
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn object_keys_are_sorted_recursively() {
        let input = json!({"b": 1, "a": {"d": 2, "c": 3}});
        let bytes = canonical_bytes(&input).unwrap();
        let text = std::str::from_utf8(&bytes).unwrap();
        assert_eq!(text, r#"{"a":{"c":3,"d":2},"b":1}"#);
    }

    #[test]
    fn arrays_preserve_order() {
        let input = json!([3, 1, 2]);
        let bytes = canonical_bytes(&input).unwrap();
        assert_eq!(bytes, br#"[3,1,2]"#);
    }

    #[test]
    fn content_hash_is_stable_across_author_order() {
        let a = json!({"x": 1, "y": 2});
        let b = json!({"y": 2, "x": 1});
        assert_eq!(content_hash(&a).unwrap(), content_hash(&b).unwrap());
    }

    #[test]
    fn non_ascii_escapes_to_backslash_u() {
        // Security audit P0-2 regression: without ASCII-escaping the Rust
        // and Python canonical bytes diverge on any non-ASCII string.
        let input = json!({"x": "café"});
        let bytes = canonical_bytes(&input).unwrap();
        assert_eq!(bytes, br#"{"x":"caf\u00e9"}"#);
    }

    #[test]
    fn astral_plane_uses_surrogate_pair() {
        // Emoji U+1F600 -> surrogate pair \ud83d\ude00, matching Python.
        let input = json!({"s": "\u{1F600}"});
        let bytes = canonical_bytes(&input).unwrap();
        assert_eq!(bytes, br#"{"s":"\ud83d\ude00"}"#);
    }

    #[test]
    fn control_characters_use_named_escapes() {
        let input = json!({"s": "a\nb\tc"});
        let bytes = canonical_bytes(&input).unwrap();
        assert_eq!(bytes, br#"{"s":"a\nb\tc"}"#);
    }
}
