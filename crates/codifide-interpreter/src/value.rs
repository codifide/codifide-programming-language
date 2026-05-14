//! Runtime value types for the Codifide interpreter.
//!
//! Mirrors `codifide/core/types.py` Value, Belief, and Bottom.
//!
//! Design note (RI-2 from Sable audit): Python uses a singleton `_BottomType`
//! and identity checks (`x is Bottom`). Rust uses an enum variant instead —
//! `Value::Bottom` — which is the natural representation and avoids the
//! singleton pattern entirely.
//!
//! Numeric semantics (RI-1 from Sable audit): all numeric payloads are `f64`,
//! matching the canonical form's JSON number representation. Arbitrary-
//! precision integers are out of scope for v2-A.

use serde_json::Value as JsonValue;

/// A runtime value. Carries type label, confidence, and provenance.
///
/// `Bottom` is the first-class refusal value. It is not an exception;
/// callers must handle it explicitly in a `believe` arm.
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    /// First-class refusal (⊥). Not an error; must be handled by callers.
    ///
    /// The optional ``reason`` field (V3-3) carries a human-readable
    /// explanation of why the refusal occurred. It is purely informational
    /// and does not affect dispatch or truthiness.
    Bottom { reason: Option<String> },
    /// A concrete value with metadata.
    Concrete(Concrete),
    /// A value wrapped with an explicit belief score.
    Belief(Box<Belief>),
}

impl Value {
    pub fn is_bottom(&self) -> bool {
        matches!(self, Value::Bottom { .. })
    }

    /// Unwrap to the inner payload for primitive operations.
    /// Returns `None` for Bottom (callers must check first).
    pub fn payload(&self) -> Option<&Payload> {
        match self {
            Value::Concrete(c) => Some(&c.payload),
            Value::Belief(b) => Some(&b.about.payload),
            Value::Bottom { .. } => None,
        }
    }

    /// Truthiness: Bottom is false; everything else delegates to the payload.
    pub fn is_truthy(&self) -> bool {
        match self {
            Value::Bottom { .. } => false,
            Value::Concrete(c) => c.payload.is_truthy(),
            Value::Belief(b) => b.about.payload.is_truthy(),
        }
    }

    /// Confidence: Belief carries its own; Concrete defaults to 1.0; Bottom is 0.0.
    pub fn conf(&self) -> f64 {
        match self {
            Value::Bottom { .. } => 0.0,
            Value::Concrete(c) => c.conf,
            Value::Belief(b) => b.conf,
        }
    }

    /// Convenience constructor for a concrete value with default metadata.
    pub fn concrete(payload: Payload) -> Self {
        Value::Concrete(Concrete {
            payload,
            type_: "Any".to_string(),
            conf: 1.0,
            provenance: "runtime".to_string(),
        })
    }

    pub fn with_type(payload: Payload, type_: &str) -> Self {
        Value::Concrete(Concrete {
            payload,
            type_: type_.to_string(),
            conf: 1.0,
            provenance: "runtime".to_string(),
        })
    }

    pub fn with_provenance(payload: Payload, type_: &str, provenance: &str) -> Self {
        Value::Concrete(Concrete {
            payload,
            type_: type_.to_string(),
            conf: 1.0,
            provenance: provenance.to_string(),
        })
    }
}

/// A concrete runtime value.
#[derive(Debug, Clone, PartialEq)]
pub struct Concrete {
    pub payload: Payload,
    pub type_: String,
    pub conf: f64,
    pub provenance: String,
}

/// A value with an explicit belief score.
#[derive(Debug, Clone, PartialEq)]
pub struct Belief {
    pub about: Concrete,
    pub conf: f64,
}

/// The actual data carried by a runtime value.
///
/// Codifide's type system is intentionally shallow at v1/v2-A: the
/// canonical form stores literals as JSON values, so we mirror that
/// here. Structured values (records from `clock.now`, image stubs)
/// are represented as `Map`.
#[derive(Debug, Clone, PartialEq)]
pub enum Payload {
    Null,
    Bool(bool),
    Number(f64),
    String(String),
    List(Vec<Value>),
    Map(Vec<(String, Value)>),
}

impl Payload {
    pub fn is_truthy(&self) -> bool {
        match self {
            Payload::Null => false,
            Payload::Bool(b) => *b,
            Payload::Number(n) => *n != 0.0,
            Payload::String(s) => !s.is_empty(),
            Payload::List(xs) => !xs.is_empty(),
            Payload::Map(m) => !m.is_empty(),
        }
    }

    /// Extract as f64 for numeric operations.
    pub fn as_number(&self) -> Option<f64> {
        match self {
            Payload::Number(n) => Some(*n),
            _ => None,
        }
    }

    /// Extract as &str for string operations.
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Payload::String(s) => Some(s.as_str()),
            _ => None,
        }
    }

    /// Extract as list for collection operations.
    pub fn as_list(&self) -> Option<&[Value]> {
        match self {
            Payload::List(xs) => Some(xs.as_slice()),
            _ => None,
        }
    }

    /// Serialize to a JSON-compatible `serde_json::Value` for the
    /// conformance bridge output format.
    pub fn to_json(&self) -> JsonValue {
        match self {
            Payload::Null => JsonValue::Null,
            Payload::Bool(b) => JsonValue::Bool(*b),
            Payload::Number(n) => {
                // Emit integers as integers when the value is whole,
                // matching Python's json output for int values.
                if n.fract() == 0.0 && n.abs() < 1e15 {
                    JsonValue::Number(serde_json::Number::from(*n as i64))
                } else {
                    serde_json::Number::from_f64(*n)
                        .map(JsonValue::Number)
                        .unwrap_or(JsonValue::Null)
                }
            }
            Payload::String(s) => JsonValue::String(s.clone()),
            Payload::List(xs) => {
                JsonValue::Array(xs.iter().map(|v| v.to_json()).collect())
            }
            Payload::Map(m) => {
                let mut obj = serde_json::Map::new();
                for (k, v) in m {
                    obj.insert(k.clone(), v.to_json());
                }
                JsonValue::Object(obj)
            }
        }
    }
}

impl Value {
    /// Serialize to JSON for the conformance bridge.
    pub fn to_json(&self) -> JsonValue {
        match self {
            Value::Bottom { .. } => JsonValue::String("⊥".to_string()),
            Value::Concrete(c) => c.payload.to_json(),
            Value::Belief(b) => b.about.payload.to_json(),
        }
    }
}

/// Convert a `serde_json::Value` literal (from the AST) into a runtime `Payload`.
pub fn payload_from_json(v: &JsonValue) -> Payload {
    match v {
        JsonValue::Null => Payload::Null,
        JsonValue::Bool(b) => Payload::Bool(*b),
        JsonValue::Number(n) => Payload::Number(n.as_f64().unwrap_or(0.0)),
        JsonValue::String(s) => Payload::String(s.clone()),
        JsonValue::Array(xs) => {
            Payload::List(xs.iter().map(|x| Value::concrete(payload_from_json(x))).collect())
        }
        JsonValue::Object(m) => {
            Payload::Map(m.iter().map(|(k, v)| (k.clone(), Value::concrete(payload_from_json(v)))).collect())
        }
    }
}
