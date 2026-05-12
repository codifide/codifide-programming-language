//! Adversarial-input fuzz for the Rust canonical crate.
//!
//! The Python reference has a parser fuzz harness at
//! ``tests/test_parser_fuzz.py``. The Rust canonical crate has had
//! none. This harness is the counterpart: feed adversarial canonical
//! JSON into ``from_canonical_json`` and assert the crate either
//! produces an ``Ok(Module)`` that successfully round-trips, or
//! returns a typed ``Error`` — but never panics.
//!
//! The battery is a mix of hand-curated inputs (shapes known to
//! exercise specific code paths) and a small pseudo-random stream
//! generated from a deterministic seed so failures are reproducible
//! without a new dependency like ``rand`` or ``quickcheck``.
//!
//! This is a regression surface, not a replacement for ``cargo-fuzz``.
//! When semantics stabilize and the project earns a fuzz-CI budget,
//! a ``cargo-fuzz`` target with libFuzzer-driven coverage should
//! subsume this file. For now, the goal is catching panics that
//! would violate the typed-error discipline.

use codifide_canonical::{
    canonical_bytes, canonical_cbor, content_hash, content_hash_cbor,
    from_canonical_json, to_canonical_json, Error,
};
use serde_json::{json, Value};

// ---------------------------------------------------------------------------
// Hand-curated adversarial inputs
// ---------------------------------------------------------------------------

/// Build a set of hand-curated adversarial JSON documents. Each one
/// targets a specific code path that could panic if careless.
fn adversarial_inputs() -> Vec<(String, Value)> {
    vec![
        ("empty object".into(), json!({})),
        ("null top-level".into(), Value::Null),
        ("array top-level".into(), json!([])),
        ("string top-level".into(), json!("not a module")),
        (
            "wrong version".into(),
            json!({"codifide": "999.0", "module": "x", "symbols": {}}),
        ),
        (
            "missing version".into(),
            json!({"module": "x", "symbols": {}}),
        ),
        (
            "symbols not object".into(),
            json!({"codifide": "0.1", "module": "x", "symbols": []}),
        ),
        (
            "symbols has non-object value".into(),
            json!({"codifide": "0.1", "module": "x", "symbols": {"n": 42}}),
        ),
        (
            "definition missing intent".into(),
            json!({
                "codifide": "0.1", "module": "x",
                "symbols": {"n": {
                    "kind": "definition",
                    "signature": {"params": [], "returns": "Any", "effects": []},
                    "pre": [], "post": [], "candidates": []
                }}
            }),
        ),
        (
            "definition intent not string".into(),
            json!({
                "codifide": "0.1", "module": "x",
                "symbols": {"n": {
                    "kind": "definition",
                    "intent": 42,
                    "signature": {"params": [], "returns": "Any", "effects": []},
                    "pre": [], "post": [], "candidates": []
                }}
            }),
        ),
        (
            "signature not object".into(),
            json!({
                "codifide": "0.1", "module": "x",
                "symbols": {"n": {
                    "kind": "definition",
                    "intent": "t",
                    "signature": "bad",
                    "pre": [], "post": [], "candidates": []
                }}
            }),
        ),
        (
            "signature params not array".into(),
            json!({
                "codifide": "0.1", "module": "x",
                "symbols": {"n": {
                    "kind": "definition",
                    "intent": "t",
                    "signature": {"params": "bad", "returns": "Any", "effects": []},
                    "pre": [], "post": [], "candidates": []
                }}
            }),
        ),
        (
            "param missing name".into(),
            json!({
                "codifide": "0.1", "module": "x",
                "symbols": {"n": {
                    "kind": "definition",
                    "intent": "t",
                    "signature": {"params": [{"type": "Int"}], "returns": "Any", "effects": []},
                    "pre": [], "post": [], "candidates": []
                }}
            }),
        ),
        (
            "candidates not array".into(),
            json!({
                "codifide": "0.1", "module": "x",
                "symbols": {"n": {
                    "kind": "definition",
                    "intent": "t",
                    "signature": {"params": [], "returns": "Any", "effects": []},
                    "pre": [], "post": [], "candidates": "bad"
                }}
            }),
        ),
        (
            "candidate body missing".into(),
            json!({
                "codifide": "0.1", "module": "x",
                "symbols": {"n": {
                    "kind": "definition", "intent": "t",
                    "signature": {"params": [], "returns": "Any", "effects": []},
                    "pre": [], "post": [],
                    "candidates": [{"kind": "candidate", "intent": "d", "guard": null}]
                }}
            }),
        ),
        (
            "expression missing kind".into(),
            json!({
                "codifide": "0.1", "module": "x",
                "symbols": {"n": {
                    "kind": "definition", "intent": "t",
                    "signature": {"params": [], "returns": "Any", "effects": []},
                    "pre": [], "post": [],
                    "candidates": [{"kind": "candidate", "intent": "d", "guard": null,
                                    "body": {"value": 1}}]
                }}
            }),
        ),
        (
            "expression unknown kind".into(),
            json!({
                "codifide": "0.1", "module": "x",
                "symbols": {"n": {
                    "kind": "definition", "intent": "t",
                    "signature": {"params": [], "returns": "Any", "effects": []},
                    "pre": [], "post": [],
                    "candidates": [{"kind": "candidate", "intent": "d", "guard": null,
                                    "body": {"kind": "hypergraph_subscription"}}]
                }}
            }),
        ),
        (
            "believe without else".into(),
            json!({
                "codifide": "0.1", "module": "x",
                "symbols": {"n": {
                    "kind": "definition", "intent": "t",
                    "signature": {"params": [], "returns": "Any", "effects": []},
                    "pre": [], "post": [],
                    "candidates": [{"kind": "candidate", "intent": "d", "guard": null,
                                    "body": {
                                        "kind": "believe",
                                        "subject": {"kind": "ref", "name": "x"},
                                        "arms": []
                                    }}]
                }}
            }),
        ),
        (
            "believe arm malformed".into(),
            json!({
                "codifide": "0.1", "module": "x",
                "symbols": {"n": {
                    "kind": "definition", "intent": "t",
                    "signature": {"params": [], "returns": "Any", "effects": []},
                    "pre": [], "post": [],
                    "candidates": [{"kind": "candidate", "intent": "d", "guard": null,
                                    "body": {
                                        "kind": "believe",
                                        "subject": {"kind": "ref", "name": "x"},
                                        "arms": [[{"kind": "ref", "name": "a"}]],
                                        "else": {"kind": "bottom"}
                                    }}]
                }}
            }),
        ),
        // Deeply nested expression — pre-built to ~200 levels deep. A
        // naive recursive descent without a bound would blow the
        // stack here.
        ("deeply nested call".into(), deeply_nested_call(200)),
        // Huge arrays inside a believe block. The encoder is happy;
        // this checks no intermediate O(n^2) step hides.
        ("many believe arms".into(), many_believe_arms(1000)),
        // Import map with many entries of legal shape.
        ("many imports".into(), many_imports(500)),
        // Import value that is not a string.
        (
            "import value not string".into(),
            json!({
                "codifide": "0.1", "module": "x", "symbols": {},
                "imports": {"foo": 12345}
            }),
        ),
    ]
}

fn deeply_nested_call(depth: usize) -> Value {
    let mut body = json!({"kind": "lit", "value": 0, "type": "Int",
                          "conf": 1.0, "provenance": "literal"});
    for _ in 0..depth {
        body = json!({
            "kind": "call",
            "fn": "id",
            "args": [body],
        });
    }
    wrap_body(body)
}

fn many_believe_arms(n: usize) -> Value {
    let arm = json!([
        {"kind": "lit", "value": true, "type": "Bool", "conf": 1.0, "provenance": "literal"},
        {"kind": "lit", "value": 1, "type": "Int", "conf": 1.0, "provenance": "literal"}
    ]);
    let arms: Vec<Value> = (0..n).map(|_| arm.clone()).collect();
    wrap_body(json!({
        "kind": "believe",
        "subject": {"kind": "ref", "name": "x"},
        "arms": arms,
        "else": {"kind": "bottom"},
    }))
}

fn many_imports(n: usize) -> Value {
    let mut imports = serde_json::Map::new();
    for i in 0..n {
        imports.insert(
            format!("sym_{i:04}"),
            json!(format!("sha256:{}", "a".repeat(64))),
        );
    }
    json!({
        "codifide": "0.1",
        "module": "x",
        "symbols": {},
        "imports": imports,
    })
}

fn wrap_body(body: Value) -> Value {
    json!({
        "codifide": "0.1",
        "module": "x",
        "symbols": {"n": {
            "kind": "definition",
            "intent": "t",
            "signature": {"params": [], "returns": "Any", "effects": []},
            "pre": [], "post": [],
            "candidates": [{
                "kind": "candidate",
                "intent": "d",
                "guard": null,
                "body": body,
            }],
        }},
    })
}

// ---------------------------------------------------------------------------
// Deterministic pseudo-random input generator
// ---------------------------------------------------------------------------

/// xorshift64* — zero dependencies, deterministic, good enough for
/// generating fuzz inputs. NOT cryptographic; the point is
/// reproducibility and coverage, not unpredictability.
struct Xorshift {
    state: u64,
}

impl Xorshift {
    fn new(seed: u64) -> Self {
        Self {
            state: if seed == 0 { 1 } else { seed },
        }
    }
    fn next(&mut self) -> u64 {
        let mut x = self.state;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.state = x;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }
}

fn random_json(rng: &mut Xorshift, depth: u32) -> Value {
    let shape = rng.next() % 8;
    match (shape, depth) {
        (0, _) => Value::Null,
        (1, _) => Value::Bool(rng.next() % 2 == 0),
        (2, _) => json!(rng.next() as i64),
        (3, _) => json!(f64::from_bits(rng.next())),
        (4, _) => Value::String(random_short_string(rng)),
        (_, 0) => json!(0),
        (5, d) => {
            let n = (rng.next() % 4) as usize;
            let items: Vec<Value> = (0..n)
                .map(|_| random_json(rng, d - 1))
                .collect();
            Value::Array(items)
        }
        (6, d) => {
            let n = (rng.next() % 4) as usize;
            let mut obj = serde_json::Map::new();
            for _ in 0..n {
                obj.insert(random_short_string(rng), random_json(rng, d - 1));
            }
            Value::Object(obj)
        }
        _ => Value::Null,
    }
}

fn random_short_string(rng: &mut Xorshift) -> String {
    let len = (rng.next() % 8) as usize;
    (0..len)
        .map(|_| {
            let c = (b'a' as u64 + (rng.next() % 26)) as u8;
            c as char
        })
        .collect()
}

// ---------------------------------------------------------------------------
// Assertions
// ---------------------------------------------------------------------------

/// Run ``from_canonical_json`` on an input, and if it succeeds, also
/// exercise the downstream byte-form and CBOR byte-form paths. None
/// of these paths may panic for any input; they may only return typed
/// errors.
fn assert_no_panic_on(input: &Value) {
    match from_canonical_json(input) {
        Ok(module) => {
            // Round-trip through canonical JSON and back; must not panic.
            let json = to_canonical_json(&module);
            let _ = canonical_bytes(&json);
            let _ = content_hash(&json);
            let _ = canonical_cbor(&json);
            let _ = content_hash_cbor(&json);
        }
        Err(_) => {
            // Typed error path. Acceptable. We never expect panics
            // regardless of input shape.
        }
    }
}

#[test]
fn hand_curated_adversarial_inputs_do_not_panic() {
    for (label, input) in adversarial_inputs() {
        // Catch an unwinding panic per-input so one bad case doesn't
        // short-circuit the loop.
        let result = std::panic::catch_unwind(|| assert_no_panic_on(&input));
        assert!(
            result.is_ok(),
            "panic on adversarial input: {label:?}: {}",
            serde_json::to_string(&input).unwrap_or_else(|_| "<unserializable>".into())
        );
    }
}

#[test]
fn randomly_generated_json_does_not_panic() {
    let mut rng = Xorshift::new(0xC0DE_F1DE_BA5E_C0DE);
    for i in 0..500 {
        let input = random_json(&mut rng, 5);
        let result = std::panic::catch_unwind(|| assert_no_panic_on(&input));
        assert!(
            result.is_ok(),
            "panic on random input #{i}: {}",
            serde_json::to_string(&input).unwrap_or_else(|_| "<unserializable>".into())
        );
    }
}

/// Document round-trips for a valid input should produce identical
/// bytes on both JSON and CBOR projection. This is the positive half
/// of the fuzz — assert determinism on well-formed inputs along with
/// no-panic on malformed ones.
#[test]
fn valid_inputs_canonicalize_stably() {
    let valid = wrap_body(json!({
        "kind": "call",
        "fn": "add",
        "args": [
            {"kind": "lit", "value": 1, "type": "Int", "conf": 1.0, "provenance": "literal"},
            {"kind": "lit", "value": 2, "type": "Int", "conf": 1.0, "provenance": "literal"},
        ],
    }));
    let module = from_canonical_json(&valid).expect("valid input parses");
    let round1_json = to_canonical_json(&module);
    let round1_bytes = canonical_bytes(&round1_json).unwrap();
    let round1_cbor = canonical_cbor(&round1_json).unwrap();

    let module2 = from_canonical_json(&round1_json).expect("re-parse");
    let round2_json = to_canonical_json(&module2);
    let round2_bytes = canonical_bytes(&round2_json).unwrap();
    let round2_cbor = canonical_cbor(&round2_json).unwrap();

    assert_eq!(round1_bytes, round2_bytes);
    assert_eq!(round1_cbor, round2_cbor);
}

/// Errors must be typed — any ``Error`` variant produces a ``Display``
/// rendering, not a panic.
#[test]
fn all_errors_display_cleanly() {
    let bad = json!(null);
    if let Err(e) = from_canonical_json(&bad) {
        let _ = format!("{e}");
        // Also exercise Debug and the source() chain.
        let _ = format!("{e:?}");
        let _ = std::error::Error::source(&e);
    } else {
        panic!("null should have been rejected");
    }

    // Provoke the UnsupportedVersion path.
    let bad = json!({"codifide": "999", "module": "x", "symbols": {}});
    match from_canonical_json(&bad) {
        Err(Error::UnsupportedVersion(_)) => {}
        other => panic!("expected UnsupportedVersion, got {other:?}"),
    }
}
