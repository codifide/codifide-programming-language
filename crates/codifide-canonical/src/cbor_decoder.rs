//! Strict canonical CBOR decoder.
//!
//! Mirror of ``codifide/projection/cbor_decoder.py``. Accepts only the
//! subset of CBOR that our canonical encoder produces; everything else
//! (indefinite-length strings, non-shortest heads, unsorted map keys,
//! NaN/infinity, unsupported tags) is rejected with a typed error.
//!
//! Why this exists: previously the Rust CLI's only path for accepting
//! input was through ``serde_json::from_str``, which parses decimal
//! floats via its own writer-specific rules. Python's ``json`` and
//! ``serde_json`` disagree on shortest-decimal form for f16-class
//! values (AUD-08 P1). A CBOR decoder bypasses that path entirely: the
//! caller writes canonical CBOR bytes, the decoder reads them back
//! into a ``serde_json::Value`` preserving exact integer and IEEE-754
//! float bits.
//!
//! This decoder deliberately decodes into ``serde_json::Value`` rather
//! than a custom Rust type. The rest of the crate already operates on
//! ``serde_json::Value`` — matching that shape keeps the new subcommand
//! a drop-in replacement for the JSON-input path.

use std::convert::TryFrom;

use serde_json::{Map, Number, Value};

use crate::error::Error;

/// Default upper bound on any single length-prefixed payload in the
/// input. 64 MiB is the same bound the Python decoder enforces and is
/// generously larger than any legitimate Codifide module.
pub const MAX_PAYLOAD_BYTES: usize = 64 * 1024 * 1024;

/// Decode canonical CBOR bytes into a JSON-shaped ``serde_json::Value``.
///
/// Fails fast on any non-canonical input. Returns an error if the
/// decoded value does not consume exactly ``data.len()`` bytes — a
/// trailing byte is itself a canonicalization violation.
pub fn decode_canonical_cbor(data: &[u8]) -> Result<Value, Error> {
    decode_canonical_cbor_with_limit(data, MAX_PAYLOAD_BYTES)
}

/// Variant that takes an explicit per-payload byte limit. Use a
/// smaller limit for untrusted input; the 64 MiB default is appropriate
/// for locally-controlled inputs.
pub fn decode_canonical_cbor_with_limit(data: &[u8], max_payload: usize) -> Result<Value, Error> {
    let (value, consumed) = decode(data, 0, max_payload)?;
    if consumed != data.len() {
        return Err(Error::Shape(format!(
            "trailing bytes after CBOR value: consumed {consumed} of {}",
            data.len()
        )));
    }
    Ok(value)
}

fn shape<T: Into<String>>(msg: T) -> Error {
    Error::Shape(msg.into())
}

// ---------------------------------------------------------------------------
// Main decode loop
// ---------------------------------------------------------------------------

fn decode(data: &[u8], i: usize, max_payload: usize) -> Result<(Value, usize), Error> {
    if i >= data.len() {
        return Err(shape("unexpected end of CBOR input"));
    }
    let head = data[i];
    let major = head >> 5;
    let additional = head & 0x1F;
    match major {
        0 => {
            let (n, j) = read_argument(data, i, additional)?;
            Ok((u64_to_value(n), j))
        }
        1 => {
            let (n, j) = read_argument(data, i, additional)?;
            // Major 1 stores -1-n. Must be representable as i64; the
            // canonical encoder never writes a negative bignum small
            // enough to fit in a plain head — and if `n` exceeds
            // i64::MAX-1 we overflow. Treat that case as non-canonical.
            // Also: -1 - u64::MAX would be -2^64, below i64::MIN.
            if n > i64::MAX as u64 {
                return Err(shape(
                    "negative integer out of i64 range; encoder must have used bignum",
                ));
            }
            let value = -(n as i64) - 1;
            Ok((Value::Number(Number::from(value)), j))
        }
        2 => {
            let (len, j) = read_argument(data, i, additional)?;
            let len_usize = bound_len(len, max_payload, "byte string")?;
            if j.checked_add(len_usize).ok_or_else(|| shape("byte string length overflow"))? > data.len() {
                return Err(shape("byte string runs past end of input"));
            }
            // Byte strings in the canonical form are not used by the
            // module shape, but bignum bodies land here. Preserve them
            // as an array of small integers so the upstream shape
            // layer can reject them if it did not expect bytes. We
            // prefer to report their shape explicitly rather than try
            // to coerce into UTF-8.
            let body = &data[j..j + len_usize];
            let arr: Vec<Value> = body.iter().map(|b| Value::from(*b)).collect();
            Ok((Value::Array(arr), j + len_usize))
        }
        3 => {
            let (len, j) = read_argument(data, i, additional)?;
            let len_usize = bound_len(len, max_payload, "text string")?;
            if j.checked_add(len_usize).ok_or_else(|| shape("text string length overflow"))? > data.len() {
                return Err(shape("text string runs past end of input"));
            }
            let body = &data[j..j + len_usize];
            let s = std::str::from_utf8(body)
                .map_err(|e| shape(format!("invalid UTF-8 in text string: {e}")))?;
            Ok((Value::String(s.to_string()), j + len_usize))
        }
        4 => {
            let (len, mut j) = read_argument(data, i, additional)?;
            let remaining = data.len() - j;
            if len > remaining as u64 {
                return Err(shape(format!(
                    "array claims {len} items but only {remaining} bytes remain"
                )));
            }
            let mut items = Vec::with_capacity(len as usize);
            for _ in 0..len {
                let (item, next) = decode(data, j, max_payload)?;
                items.push(item);
                j = next;
            }
            Ok((Value::Array(items), j))
        }
        5 => {
            let (len, mut j) = read_argument(data, i, additional)?;
            let remaining = data.len() - j;
            if len.checked_mul(2).map_or(true, |two_n| two_n > remaining as u64) {
                return Err(shape(format!(
                    "map claims {len} pairs but only {remaining} bytes remain"
                )));
            }
            let mut out: Map<String, Value> = Map::with_capacity(len as usize);
            let mut last_key_bytes: Option<&[u8]> = None;
            for _ in 0..len {
                let key_start = j;
                let (key_value, after_key) = decode(data, j, max_payload)?;
                let key_end = after_key;
                let key_bytes = &data[key_start..key_end];
                // Canonical map-key ordering: each key's encoded bytes
                // must be strictly greater than the previous key's.
                if let Some(prev) = last_key_bytes {
                    if key_bytes <= prev {
                        return Err(shape("map keys not in canonical order"));
                    }
                }
                last_key_bytes = Some(key_bytes);
                // Keys must be strings in our canonical form (map type
                // shape pulls through to JSON keys, which must be
                // strings).
                let key_str = match key_value {
                    Value::String(s) => s,
                    _ => return Err(shape("canonical map keys must be text strings")),
                };
                if out.contains_key(&key_str) {
                    return Err(shape("duplicate map key in canonical CBOR"));
                }
                let (val, after_val) = decode(data, after_key, max_payload)?;
                out.insert(key_str, val);
                j = after_val;
            }
            Ok((Value::Object(out), j))
        }
        6 => {
            // Tagged. Canonical form only allows bignum tags (2, 3) for
            // integers outside the u64 range. We don't currently use
            // bignums in any Codifide module, but reject with a clear
            // message if one shows up.
            let (tag, j) = read_argument(data, i, additional)?;
            let (_inner, after_inner) = decode(data, j, max_payload)?;
            match tag {
                2 | 3 => {
                    // A bignum body larger than u64::MAX can't be
                    // represented by ``serde_json::Number``; reject
                    // rather than silently truncate.
                    Err(shape(
                        "canonical CBOR bignum encountered; not representable in this decoder's JSON view",
                    ))
                    .map(|_: ()| (Value::Null, after_inner))  // unreachable: returning for type-check parity
                }
                other => Err(shape(format!(
                    "unsupported CBOR tag in canonical form: {other}"
                ))),
            }
        }
        7 => {
            match additional {
                20 => Ok((Value::Bool(false), i + 1)),
                21 => Ok((Value::Bool(true), i + 1)),
                22 => Ok((Value::Null, i + 1)),
                25 => {
                    // Half-precision float (binary16).
                    if i + 3 > data.len() {
                        return Err(shape("truncated half float"));
                    }
                    let bits = u16::from_be_bytes([data[i + 1], data[i + 2]]);
                    let f = f16_bits_to_f64(bits)
                        .ok_or_else(|| shape("NaN/infinity not allowed in canonical CBOR"))?;
                    let n = Number::from_f64(f)
                        .ok_or_else(|| shape("f16 decoded to non-finite f64"))?;
                    Ok((Value::Number(n), i + 3))
                }
                26 => {
                    if i + 5 > data.len() {
                        return Err(shape("truncated single float"));
                    }
                    let bits = u32::from_be_bytes([
                        data[i + 1],
                        data[i + 2],
                        data[i + 3],
                        data[i + 4],
                    ]);
                    let f = f32::from_bits(bits);
                    if f.is_nan() || f.is_infinite() {
                        return Err(shape("NaN/infinity not allowed in canonical CBOR"));
                    }
                    let n = Number::from_f64(f as f64)
                        .ok_or_else(|| shape("f32 decoded to non-finite f64"))?;
                    Ok((Value::Number(n), i + 5))
                }
                27 => {
                    if i + 9 > data.len() {
                        return Err(shape("truncated double float"));
                    }
                    let mut buf = [0u8; 8];
                    buf.copy_from_slice(&data[i + 1..i + 9]);
                    let f = f64::from_be_bytes(buf);
                    if f.is_nan() || f.is_infinite() {
                        return Err(shape("NaN/infinity not allowed in canonical CBOR"));
                    }
                    let n = Number::from_f64(f)
                        .ok_or_else(|| shape("double decoded to non-finite f64"))?;
                    Ok((Value::Number(n), i + 9))
                }
                other => Err(shape(format!(
                    "unsupported major-7 additional in canonical CBOR: {other}"
                ))),
            }
        }
        other => Err(shape(format!("unreachable major type: {other}"))),
    }
}

fn u64_to_value(n: u64) -> Value {
    if n <= i64::MAX as u64 {
        Value::Number(Number::from(n as i64))
    } else {
        // serde_json supports u64 via from<u64>; Number handles both.
        Value::Number(Number::from(n))
    }
}

fn bound_len(len: u64, max_payload: usize, what: &str) -> Result<usize, Error> {
    if len > max_payload as u64 {
        return Err(shape(format!(
            "{what} claims {len} bytes, exceeds max_payload {max_payload}"
        )));
    }
    usize::try_from(len).map_err(|_| shape(format!("{what} length out of usize range")))
}

fn read_argument(data: &[u8], i: usize, additional: u8) -> Result<(u64, usize), Error> {
    if additional < 24 {
        return Ok((additional as u64, i + 1));
    }
    match additional {
        24 => {
            if i + 2 > data.len() {
                return Err(shape("truncated 1-byte argument"));
            }
            let n = data[i + 1] as u64;
            if n < 24 {
                return Err(shape("non-canonical: 1-byte argument used for small value"));
            }
            Ok((n, i + 2))
        }
        25 => {
            if i + 3 > data.len() {
                return Err(shape("truncated 2-byte argument"));
            }
            let n = u16::from_be_bytes([data[i + 1], data[i + 2]]) as u64;
            if n < 0x100 {
                return Err(shape("non-canonical: 2-byte argument used for small value"));
            }
            Ok((n, i + 3))
        }
        26 => {
            if i + 5 > data.len() {
                return Err(shape("truncated 4-byte argument"));
            }
            let n = u32::from_be_bytes([
                data[i + 1],
                data[i + 2],
                data[i + 3],
                data[i + 4],
            ]) as u64;
            if n < 0x10000 {
                return Err(shape("non-canonical: 4-byte argument used for small value"));
            }
            Ok((n, i + 5))
        }
        27 => {
            if i + 9 > data.len() {
                return Err(shape("truncated 8-byte argument"));
            }
            let mut buf = [0u8; 8];
            buf.copy_from_slice(&data[i + 1..i + 9]);
            let n = u64::from_be_bytes(buf);
            if n < 0x100000000 {
                return Err(shape("non-canonical: 8-byte argument used for small value"));
            }
            Ok((n, i + 9))
        }
        other => Err(shape(format!(
            "indefinite-length or reserved form not allowed: {other}"
        ))),
    }
}

/// Convert a 2-byte binary16 bit pattern to an f64. Returns ``None`` if
/// the pattern decodes to NaN or infinity (canonical CBOR forbids both).
fn f16_bits_to_f64(bits: u16) -> Option<f64> {
    let sign = (bits >> 15) as u32;
    let exponent = ((bits >> 10) & 0x1F) as u32;
    let mantissa = (bits & 0x3FF) as u32;

    if exponent == 0x1F {
        // NaN or infinity — forbidden in canonical CBOR.
        return None;
    }

    let f32_bits = if exponent == 0 && mantissa == 0 {
        // Signed zero.
        sign << 31
    } else if exponent == 0 {
        // Subnormal. Shift left until the leading 1 is found.
        let mut exp: i32 = -14;
        let mut mant = mantissa;
        while mant & 0x400 == 0 {
            mant <<= 1;
            exp -= 1;
        }
        // Drop the implicit leading 1 and re-bias for f32.
        mant &= 0x3FF;
        let exp_f32 = (exp + 127) as u32;
        (sign << 31) | (exp_f32 << 23) | (mant << 13)
    } else {
        // Normal number.
        let exp_f32 = exponent - 15 + 127;
        (sign << 31) | (exp_f32 << 23) | (mantissa << 13)
    };

    let f = f32::from_bits(f32_bits) as f64;
    if f.is_nan() || f.is_infinite() {
        None
    } else {
        Some(f)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cbor::canonical_cbor;
    use serde_json::json;

    /// Round-tripping a canonical JSON value through the encoder and
    /// back through the decoder must yield an equal value.
    fn roundtrip(v: Value) {
        let bytes = canonical_cbor(&v).expect("encode");
        let decoded = decode_canonical_cbor(&bytes).expect("decode");
        assert_eq!(decoded, v, "round-trip disagreement for {v}");
    }

    #[test]
    fn integer_round_trip() {
        for n in [0i64, 1, -1, 23, 24, -24, 255, 256, -256, 1 << 31, -(1 << 31)] {
            roundtrip(json!(n));
        }
    }

    #[test]
    fn string_round_trip() {
        roundtrip(json!(""));
        roundtrip(json!("IETF"));
        roundtrip(json!("hello, world"));
        roundtrip(json!("\u{00fc}"));  // non-ASCII
    }

    #[test]
    fn composite_round_trip() {
        roundtrip(json!([]));
        roundtrip(json!([1, 2, 3]));
        roundtrip(json!({}));
        roundtrip(json!({"a": 1, "b": 2}));
    }

    #[test]
    fn null_and_bool_round_trip() {
        roundtrip(Value::Null);
        roundtrip(Value::Bool(true));
        roundtrip(Value::Bool(false));
    }

    #[test]
    fn signed_zero_round_trip() {
        // Serde's JSON value does not preserve signed zero by default;
        // we just confirm 0.0 decodes cleanly. Negative zero is
        // encoder-exercised in the Python suite.
        let bytes = canonical_cbor(&Value::from(0.0)).expect("encode");
        let decoded = decode_canonical_cbor(&bytes).expect("decode");
        assert_eq!(decoded, Value::from(0.0));
    }

    #[test]
    fn small_f16_values_round_trip_exactly() {
        // The smallest f16 subnormal — AUD-08's canonical witness.
        // Encoder produces `f9 00 01`; decoder returns an f64 whose
        // bits equal 0x3e70000000000000. The round-trip succeeds
        // because we skip JSON-text parsing entirely.
        let subnormal = f64::from_bits(0x3e70000000000000);
        let v = Value::from(subnormal);
        let bytes = canonical_cbor(&v).expect("encode");
        let decoded = decode_canonical_cbor(&bytes).expect("decode");
        assert_eq!(decoded, v);
    }

    #[test]
    fn rejects_nan_payload() {
        // f16 NaN: exponent all-ones, non-zero mantissa. Manually
        // construct the canonical-looking head so the decoder sees
        // it.
        let nan_bytes = [0xF9u8, 0x7E, 0x00];
        let result = decode_canonical_cbor(&nan_bytes);
        assert!(result.is_err(), "NaN must be rejected");
    }

    #[test]
    fn rejects_infinity_payload() {
        let inf_bytes = [0xF9u8, 0x7C, 0x00];  // f16 +∞
        let result = decode_canonical_cbor(&inf_bytes);
        assert!(result.is_err(), "infinity must be rejected");
    }

    #[test]
    fn rejects_non_shortest_integer_head() {
        // 23 encoded as a 1-byte argument (non-canonical — 23 fits
        // inline).
        let bytes = [0x18u8, 23];
        assert!(decode_canonical_cbor(&bytes).is_err());
    }

    #[test]
    fn rejects_unsorted_map_keys() {
        // Map with two keys, "b" then "a" — strictly decreasing. The
        // canonical form requires strictly increasing encoded-key
        // order.
        let bytes = [
            0xA2,              // map(2)
            0x61, b'b', 0x01,  // "b" -> 1
            0x61, b'a', 0x02,  // "a" -> 2
        ];
        assert!(decode_canonical_cbor(&bytes).is_err());
    }

    #[test]
    fn rejects_duplicate_map_keys() {
        // Map with "a" twice — invalid regardless of order.
        let bytes = [
            0xA2,
            0x61, b'a', 0x01,
            0x61, b'a', 0x02,
        ];
        assert!(decode_canonical_cbor(&bytes).is_err());
    }

    #[test]
    fn rejects_trailing_bytes() {
        // A valid single integer followed by extra data.
        let mut bytes = vec![0x01];  // integer 1
        bytes.push(0xFF);
        assert!(decode_canonical_cbor(&bytes).is_err());
    }

    #[test]
    fn rejects_truncated_input() {
        // Text string head claiming length 10, but only 2 bytes
        // follow.
        let bytes = [0x6A, b'a', b'b'];
        assert!(decode_canonical_cbor(&bytes).is_err());
    }

    #[test]
    fn rejects_indefinite_length_head() {
        // Additional = 31 → indefinite length, forbidden in canonical.
        let bytes = [0x5F, 0xFF];
        assert!(decode_canonical_cbor(&bytes).is_err());
    }
}
