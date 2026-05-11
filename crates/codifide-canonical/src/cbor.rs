//! Canonical CBOR (RFC 8949 §4.2) byte form.
//!
//! Byte-for-byte compatible with the Python reference implementation in
//! `codifide/projection/cbor.py`. The conformance test pins the two
//! together on every `.cod` example and on a set of RFC 8949 Appendix A
//! test vectors.
//!
//! The encoder accepts the same JSON-compatible subset as the Python
//! side: null, booleans, integers, finite floats, text strings, byte
//! strings, arrays, and maps with string keys. Anything else returns an
//! error. Infinity and NaN are not representable in canonical form.

use std::io::Write;

use serde_json::{Number, Value};
use sha2::{Digest, Sha256};

use crate::error::Error;

/// Produce the canonical CBOR byte form of a JSON-compatible value.
pub fn canonical_cbor(value: &Value) -> Result<Vec<u8>, Error> {
    let mut out = Vec::with_capacity(64);
    encode_value(value, &mut out)?;
    Ok(out)
}

/// SHA-256 of the canonical CBOR byte form, hex-prefixed with `sha256:`.
pub fn content_hash_cbor(value: &Value) -> Result<String, Error> {
    let bytes = canonical_cbor(value)?;
    let mut hasher = Sha256::new();
    hasher.update(&bytes);
    let digest = hasher.finalize();
    let mut hex = String::with_capacity(7 + digest.len() * 2);
    hex.push_str("sha256:");
    for b in digest {
        hex.push(HEX[(b >> 4) as usize] as char);
        hex.push(HEX[(b & 0x0f) as usize] as char);
    }
    Ok(hex)
}

const HEX: &[u8] = b"0123456789abcdef";

// ---------------------------------------------------------------------------
// Core dispatch
// ---------------------------------------------------------------------------

fn encode_value(v: &Value, out: &mut Vec<u8>) -> Result<(), Error> {
    match v {
        Value::Null => {
            out.push(0xF6);
            Ok(())
        }
        Value::Bool(true) => {
            out.push(0xF5);
            Ok(())
        }
        Value::Bool(false) => {
            out.push(0xF4);
            Ok(())
        }
        Value::Number(n) => encode_number(n, out),
        Value::String(s) => encode_text(s, out),
        Value::Array(a) => encode_array(a, out),
        Value::Object(o) => encode_map(o, out),
    }
}

// ---------------------------------------------------------------------------
// Head encoding
// ---------------------------------------------------------------------------

/// Write the shortest CBOR head for `(major, argument)` to `out`.
fn encode_head(major: u8, n: u64, out: &mut Vec<u8>) {
    debug_assert!(major <= 7);
    let prefix = major << 5;
    if n < 24 {
        out.push(prefix | (n as u8));
    } else if n < 0x100 {
        out.push(prefix | 24);
        out.push(n as u8);
    } else if n < 0x10000 {
        out.push(prefix | 25);
        out.extend_from_slice(&(n as u16).to_be_bytes());
    } else if n < 0x1_0000_0000 {
        out.push(prefix | 26);
        out.extend_from_slice(&(n as u32).to_be_bytes());
    } else {
        out.push(prefix | 27);
        out.extend_from_slice(&n.to_be_bytes());
    }
}

// ---------------------------------------------------------------------------
// Numbers
// ---------------------------------------------------------------------------

fn encode_number(n: &Number, out: &mut Vec<u8>) -> Result<(), Error> {
    // Prefer integer representations when they fit; fall back to float
    // only when the value is genuinely a float. `serde_json::Number`
    // distinguishes these for us.
    if let Some(u) = n.as_u64() {
        encode_unsigned(u, out);
        return Ok(());
    }
    if let Some(i) = n.as_i64() {
        // Covers the negative uint64 range via i64.
        encode_signed(i as i128, out);
        return Ok(());
    }
    // Fall-through: only a float could produce Number that is neither
    // u64 nor i64. `as_f64` always succeeds in that case.
    if let Some(f) = n.as_f64() {
        encode_float(f, out)?;
        return Ok(());
    }
    Err(Error::Shape(format!("unrepresentable number: {n}")))
}

fn encode_unsigned(n: u64, out: &mut Vec<u8>) {
    encode_head(0, n, out);
}

fn encode_signed(n: i128, out: &mut Vec<u8>) {
    if n >= 0 {
        // Fits in u64 because we only reach here via i64.
        encode_head(0, n as u64, out);
    } else {
        // CBOR major type 1 stores `-1 - n` as an unsigned argument.
        let m = (-1 - n) as u64;
        encode_head(1, m, out);
    }
}

fn encode_float(f: f64, out: &mut Vec<u8>) -> Result<(), Error> {
    if f.is_nan() {
        return Err(Error::Shape("canonical CBOR: NaN not representable".into()));
    }
    if f.is_infinite() {
        return Err(Error::Shape(
            "canonical CBOR: infinity not representable".into(),
        ));
    }
    // Try half-precision (binary16) first: the canonical form requires
    // the shortest IEEE encoding that preserves the value exactly,
    // including for signed zero.
    if let Some(h) = try_half(f) {
        out.push(0xF9);
        out.extend_from_slice(&h);
        return Ok(());
    }
    if let Some(s) = try_single(f) {
        out.push(0xFA);
        out.extend_from_slice(&s);
        return Ok(());
    }
    out.push(0xFB);
    out.extend_from_slice(&f.to_be_bytes());
    Ok(())
}

/// Return the 2-byte binary16 representation iff it is exact (preserves
/// value and sign of zero), else None.
fn try_half(f: f64) -> Option<[u8; 2]> {
    // Convert via f32 round-trip first: many values that fit in f16
    // also fit in f32, and the f32 path is the definitive check for
    // "narrower float suffices". We then narrow from f32 to f16 by
    // bit-twiddling because Rust has no stable f16 in 1.95.
    let packed = f64_to_f16_bits(f)?;
    Some(packed.to_be_bytes())
}

/// Try to encode `f` as IEEE-754 binary16 bits, returning None if the
/// encoding would lose precision or change the sign of zero.
fn f64_to_f16_bits(f: f64) -> Option<u16> {
    // Handle zero (preserves sign via the magnitude path below).
    if f == 0.0 {
        let sign = (f.to_bits() >> 63) as u16;
        return Some(sign << 15);
    }

    let bits = f.to_bits();
    let sign = ((bits >> 63) & 0x1) as u16;
    let exp_f64 = ((bits >> 52) & 0x7FF) as i32; // 0..2047
    let mant_f64 = bits & 0x000F_FFFF_FFFF_FFFF;

    // NaN/inf were already rejected by the caller.
    let unbiased_exp = exp_f64 - 1023;

    // Normalized representable range: unbiased exponent in [-14, 15]
    // after normalization. Use conservative bounds before fine checks.
    if unbiased_exp > 15 {
        // Overflow for f16 normals (>= 2^16 magnitude).
        return None;
    }

    if unbiased_exp >= -14 {
        // Normal number in f16. The 10-bit mantissa must be obtained by
        // shifting the 52-bit f64 mantissa right by 42 bits and losing
        // no set bits in the low 42 bits (otherwise we'd lose
        // precision).
        if mant_f64 & ((1u64 << 42) - 1) != 0 {
            return None;
        }
        let mant_f16 = (mant_f64 >> 42) as u16;
        let exp_f16 = ((unbiased_exp + 15) as u16) & 0x1F;
        return Some((sign << 15) | (exp_f16 << 10) | mant_f16);
    }

    // Subnormal range for f16: unbiased_exp in [-24, -15]. The f16
    // subnormal representation stores mantissa with an implicit
    // exponent of -14, so we have to re-express f's magnitude in that
    // frame and confirm exactness.
    if unbiased_exp < -24 {
        // Too small even for a subnormal.
        return None;
    }

    // Effective mantissa including the implicit leading 1.
    let mant_with_leading: u64 = mant_f64 | (1u64 << 52);
    // Shift to place at 10-bit mantissa with implicit -14 exponent.
    // The shift amount is: (52 - 10) + (-14 - unbiased_exp) = 42 + (-14 - unbiased_exp).
    let shift = 42 + (-14 - unbiased_exp) as u32;
    // A shift of 64 or more discards all bits; values that require
    // such a shift cannot be represented.
    if shift >= 64 {
        return None;
    }
    // The low `shift` bits must be zero for exactness.
    if mant_with_leading & ((1u64 << shift) - 1) != 0 {
        return None;
    }
    let mant_f16 = (mant_with_leading >> shift) as u16;
    // For subnormals the f16 exponent field is zero.
    Some((sign << 15) | mant_f16)
}

/// Return the 4-byte binary32 representation iff it is exact.
fn try_single(f: f64) -> Option<[u8; 4]> {
    let as_f32 = f as f32;
    if (as_f32 as f64) != f {
        return None;
    }
    // Preserve sign of zero.
    if f == 0.0 && f.is_sign_negative() != as_f32.is_sign_negative() {
        return None;
    }
    Some(as_f32.to_be_bytes())
}

// ---------------------------------------------------------------------------
// Strings, arrays, maps
// ---------------------------------------------------------------------------

fn encode_text(s: &str, out: &mut Vec<u8>) -> Result<(), Error> {
    let bytes = s.as_bytes();
    encode_head(3, bytes.len() as u64, out);
    out.write_all(bytes).unwrap();
    Ok(())
}

fn encode_array(items: &[Value], out: &mut Vec<u8>) -> Result<(), Error> {
    encode_head(4, items.len() as u64, out);
    for item in items {
        encode_value(item, out)?;
    }
    Ok(())
}

fn encode_map(obj: &serde_json::Map<String, Value>, out: &mut Vec<u8>) -> Result<(), Error> {
    // Encode each (key, value) pair, sort by encoded key bytes, emit.
    // Sorting by encoded bytes is what RFC 8949 §4.2.1 requires; it
    // happens to coincide with sorting by unescaped UTF-8 string bytes
    // for string keys, but we do it the general way anyway.
    let mut pairs: Vec<(Vec<u8>, Vec<u8>)> = Vec::with_capacity(obj.len());
    for (k, v) in obj {
        let mut key_buf = Vec::new();
        encode_text(k, &mut key_buf)?;
        let mut val_buf = Vec::new();
        encode_value(v, &mut val_buf)?;
        pairs.push((key_buf, val_buf));
    }
    pairs.sort_by(|a, b| a.0.cmp(&b.0));
    encode_head(5, pairs.len() as u64, out);
    for (k, v) in pairs {
        out.extend_from_slice(&k);
        out.extend_from_slice(&v);
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests (RFC 8949 Appendix A vectors)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Number};

    /// Helper: encode a JSON value and return its hex for readable compares.
    fn hex(v: &Value) -> String {
        let b = canonical_cbor(v).unwrap();
        b.iter().map(|x| format!("{x:02x}")).collect()
    }

    #[test]
    fn rfc_8949_integer_vectors() {
        assert_eq!(hex(&json!(0)), "00");
        assert_eq!(hex(&json!(1)), "01");
        assert_eq!(hex(&json!(10)), "0a");
        assert_eq!(hex(&json!(23)), "17");
        assert_eq!(hex(&json!(24)), "1818");
        assert_eq!(hex(&json!(100)), "1864");
        assert_eq!(hex(&json!(1000)), "1903e8");
        assert_eq!(hex(&json!(1_000_000)), "1a000f4240");
        assert_eq!(hex(&json!(1_000_000_000_000u64)), "1b000000e8d4a51000");
        assert_eq!(hex(&json!(-1)), "20");
        assert_eq!(hex(&json!(-10)), "29");
        assert_eq!(hex(&json!(-100)), "3863");
        assert_eq!(hex(&json!(-1000)), "3903e7");
    }

    #[test]
    fn rfc_8949_float_vectors() {
        // 0.0 and -0.0: half-precision preserves signed zero.
        assert_eq!(hex(&Value::Number(Number::from_f64(0.0).unwrap())), "f90000");
        assert_eq!(
            hex(&Value::Number(Number::from_f64(-0.0).unwrap())),
            "f98000"
        );
        assert_eq!(hex(&Value::Number(Number::from_f64(1.0).unwrap())), "f93c00");
        assert_eq!(hex(&Value::Number(Number::from_f64(1.5).unwrap())), "f93e00");
        // 1.1 is not exact in any binary float; encoded as f64.
        assert_eq!(
            hex(&Value::Number(Number::from_f64(1.1).unwrap())),
            "fb3ff199999999999a"
        );
        // 65504.0 fits exactly in half precision (largest subnormal-less normal).
        assert_eq!(
            hex(&Value::Number(Number::from_f64(65504.0).unwrap())),
            "f97bff"
        );
        // 100000.0 does not fit in half but fits in single.
        assert_eq!(
            hex(&Value::Number(Number::from_f64(100000.0).unwrap())),
            "fa47c35000"
        );
        // Smallest f16 subnormal.
        assert_eq!(
            hex(&Value::Number(Number::from_f64(5.960464477539063e-8).unwrap())),
            "f90001"
        );
    }

    #[test]
    fn rfc_8949_simple_and_composite_vectors() {
        assert_eq!(hex(&json!(false)), "f4");
        assert_eq!(hex(&json!(true)), "f5");
        assert_eq!(hex(&json!(null)), "f6");
        assert_eq!(hex(&json!([])), "80");
        assert_eq!(hex(&json!([1, 2, 3])), "83010203");
        assert_eq!(hex(&json!({})), "a0");
        assert_eq!(hex(&json!("")), "60");
        assert_eq!(hex(&json!("a")), "6161");
        assert_eq!(hex(&json!("IETF")), "6449455446");
        assert_eq!(hex(&json!("\u{00fc}")), "62c3bc");
        assert_eq!(hex(&json!("\u{6c34}")), "63e6b0b4");
    }

    #[test]
    fn map_keys_sort_by_encoded_bytes() {
        // Keys of different lengths: CBOR sorts by encoded bytes, so
        // "b" (head 0x61 "text string len 1") sorts before "aa" (head
        // 0x62 "text string len 2") because 0x61 < 0x62 regardless of
        // the body. The canonical encoder must emit them in that order.
        let v = json!({"aa": 2, "b": 1});
        let got = hex(&v);
        // 0xa2 (map(2)), then key "b" = 61 62, value 01,
        // then key "aa" = 62 61 61, value 02.
        assert_eq!(got, "a26162016261610 2".replace(" ", ""));
    }
}
