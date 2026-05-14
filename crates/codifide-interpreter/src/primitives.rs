//! Primitive registry for the Codifide Rust interpreter.
//!
//! Mirrors `codifide/runtime/primitives.py`. All 49 primitives from the
//! v1 capability manifest, plus the EffectTrace.
//!
//! Numeric semantics (RI-1): all numbers are f64, matching the canonical
//! form's JSON number representation.

use std::collections::HashMap;
use crate::errors::Error;
use crate::value::{Belief, Concrete, Payload, Value};

// ---------------------------------------------------------------------------
// Effect trace
// ---------------------------------------------------------------------------

/// Mutable record of effects performed during one top-level invocation.
#[derive(Debug, Default, Clone)]
pub struct EffectTrace {
    pub stdout: Vec<String>,
    pub clock_reads: Vec<f64>,
    pub model_calls: Vec<(String, String)>,
}

impl EffectTrace {
    pub fn fresh() -> Self {
        Self::default()
    }
}

// ---------------------------------------------------------------------------
// Primitive spec and registry
// ---------------------------------------------------------------------------

pub struct PrimitiveSpec {
    pub name: &'static str,
    pub effect: Option<&'static str>,
    pub returns: &'static str,
    pub fn_: Box<dyn Fn(&[Value], &mut EffectTrace) -> Result<Value, Error> + Send + Sync>,
}

pub struct PrimitiveRegistry {
    prims: HashMap<String, PrimitiveSpec>,
}

impl PrimitiveRegistry {
    pub fn has(&self, name: &str) -> bool {
        self.prims.contains_key(name)
    }

    pub fn get(&self, name: &str) -> Option<&PrimitiveSpec> {
        self.prims.get(name)
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn num(v: &Value, fn_: &str) -> Result<f64, Error> {
    match v.payload() {
        Some(Payload::Number(n)) => Ok(*n),
        Some(other) => Err(Error::Primitive {
            fn_: fn_.to_string(),
            cause: format!("expected a number, got {:?}", other),
        }),
        None => Err(Error::BottomPropagation { fn_: fn_.to_string() }),
    }
}

fn str_val(v: &Value, fn_: &str) -> Result<String, Error> {
    match v.payload() {
        Some(Payload::String(s)) => Ok(s.clone()),
        Some(other) => Err(Error::Primitive {
            fn_: fn_.to_string(),
            cause: format!("expected a string, got {:?}", other),
        }),
        None => Err(Error::BottomPropagation { fn_: fn_.to_string() }),
    }
}

fn list_val(v: &Value, fn_: &str) -> Result<Vec<Value>, Error> {
    match v.payload() {
        Some(Payload::List(xs)) => Ok(xs.clone()),
        Some(other) => Err(Error::Primitive {
            fn_: fn_.to_string(),
            cause: format!("expected a list, got {:?}", other),
        }),
        None => Err(Error::BottomPropagation { fn_: fn_.to_string() }),
    }
}

fn check_no_bottom(args: &[Value], fn_: &str) -> Result<(), Error> {
    for a in args {
        if a.is_bottom() {
            return Err(Error::BottomPropagation { fn_: fn_.to_string() });
        }
    }
    Ok(())
}

fn num_val(n: f64) -> Value { Value::with_type(Payload::Number(n), "Number") }
fn bool_val(b: bool) -> Value { Value::with_type(Payload::Bool(b), "Bool") }
fn str_out(s: String) -> Value { Value::with_type(Payload::String(s), "String") }
fn int_val(n: i64) -> Value { Value::with_type(Payload::Number(n as f64), "Int") }
fn list_out(xs: Vec<Value>) -> Value { Value::with_type(Payload::List(xs), "List") }

/// Unwrap a Value to a display string (for io.say and str primitive).
fn display(v: &Value) -> String {
    match v.payload() {
        Some(Payload::Null) => "None".to_string(),
        Some(Payload::Bool(b)) => if *b { "True".to_string() } else { "False".to_string() },
        Some(Payload::Number(n)) => {
            if n.fract() == 0.0 && n.abs() < 1e15 { format!("{}", *n as i64) }
            else { format!("{}", n) }
        }
        Some(Payload::String(s)) => s.clone(),
        Some(Payload::List(xs)) => {
            let parts: Vec<String> = xs.iter().map(|x| display(x)).collect();
            format!("[{}]", parts.join(", "))
        }
        Some(Payload::Map(m)) => {
            let parts: Vec<String> = m.iter().map(|(k, v)| format!("{}: {}", k, display(v))).collect();
            format!("{{{}}}", parts.join(", "))
        }
        None => "⊥".to_string(),
    }
}

// ---------------------------------------------------------------------------
// Registry builder
// ---------------------------------------------------------------------------

pub fn build_default_registry() -> PrimitiveRegistry {
    let mut prims: HashMap<String, PrimitiveSpec> = HashMap::new();

    macro_rules! reg {
        ($name:expr, $effect:expr, $returns:expr, $fn:expr) => {
            prims.insert($name.to_string(), PrimitiveSpec {
                name: $name, effect: $effect, returns: $returns,
                fn_: Box::new($fn),
            });
        };
    }

    // -- Arithmetic (pure) --------------------------------------------------
    reg!("add", None, "Number", |a, _| { check_no_bottom(a, "add")?; Ok(num_val(num(&a[0],"add")? + num(&a[1],"add")?)) });
    reg!("sub", None, "Number", |a, _| { check_no_bottom(a, "sub")?; Ok(num_val(num(&a[0],"sub")? - num(&a[1],"sub")?)) });
    reg!("mul", None, "Number", |a, _| { check_no_bottom(a, "mul")?; Ok(num_val(num(&a[0],"mul")? * num(&a[1],"mul")?)) });
    reg!("div", None, "Number", |a, _| {
        check_no_bottom(a, "div")?;
        let b = num(&a[1],"div")?;
        if b == 0.0 { return Err(Error::Primitive { fn_: "div".to_string(), cause: "division by zero".to_string() }); }
        Ok(num_val(num(&a[0],"div")? / b))
    });
    reg!("mod", None, "Int", |a, _| {
        check_no_bottom(a, "mod")?;
        let av = num(&a[0],"mod")? as i64;
        let bv = num(&a[1],"mod")? as i64;
        if bv == 0 { return Err(Error::Primitive { fn_: "mod".to_string(), cause: "modulo by zero".to_string() }); }
        Ok(int_val(av.rem_euclid(bv)))
    });
    reg!("neg", None, "Number", |a, _| { check_no_bottom(a, "neg")?; Ok(num_val(-num(&a[0],"neg")?)) });
    reg!("abs", None, "Number", |a, _| { check_no_bottom(a, "abs")?; Ok(num_val(num(&a[0],"abs")?.abs())) });
    reg!("min", None, "Number", |a, _| { check_no_bottom(a, "min")?; Ok(num_val(num(&a[0],"min")?.min(num(&a[1],"min")?))) });
    reg!("max", None, "Number", |a, _| { check_no_bottom(a, "max")?; Ok(num_val(num(&a[0],"max")?.max(num(&a[1],"max")?))) });
    reg!("pow", None, "Number", |a, _| { check_no_bottom(a, "pow")?; Ok(num_val(num(&a[0],"pow")?.powf(num(&a[1],"pow")?))) });
    reg!("floor", None, "Int", |a, _| { check_no_bottom(a, "floor")?; Ok(int_val(num(&a[0],"floor")?.floor() as i64)) });
    reg!("ceil",  None, "Int", |a, _| { check_no_bottom(a, "ceil")?;  Ok(int_val(num(&a[0],"ceil")?.ceil()  as i64)) });
    reg!("round", None, "Int", |a, _| {
        check_no_bottom(a, "round")?;
        // Banker's rounding (round half to even), matching Python's built-in round().
        let n = num(&a[0], "round")?;
        let floor = n.floor();
        let diff = n - floor;
        let rounded = if (diff - 0.5).abs() < f64::EPSILON {
            // Exactly halfway: round to even
            if (floor as i64) % 2 == 0 { floor } else { floor + 1.0 }
        } else {
            n.round()
        };
        Ok(int_val(rounded as i64))
    });

    // -- Comparison (pure) --------------------------------------------------
    reg!("eq", None, "Bool", |a, _| { check_no_bottom(a, "eq")?; Ok(bool_val(a[0].payload() == a[1].payload())) });
    reg!("ne", None, "Bool", |a, _| { check_no_bottom(a, "ne")?; Ok(bool_val(a[0].payload() != a[1].payload())) });
    reg!("lt", None, "Bool", |a, _| { check_no_bottom(a, "lt")?; Ok(bool_val(num(&a[0],"lt")? <  num(&a[1],"lt")?)) });
    reg!("le", None, "Bool", |a, _| { check_no_bottom(a, "le")?; Ok(bool_val(num(&a[0],"le")? <= num(&a[1],"le")?)) });
    reg!("gt", None, "Bool", |a, _| { check_no_bottom(a, "gt")?; Ok(bool_val(num(&a[0],"gt")? >  num(&a[1],"gt")?)) });
    reg!("ge", None, "Bool", |a, _| { check_no_bottom(a, "ge")?; Ok(bool_val(num(&a[0],"ge")? >= num(&a[1],"ge")?)) });

    // -- Logical (pure, variadic) -------------------------------------------
    reg!("and", None, "Bool", |a, _| { check_no_bottom(a, "and")?; Ok(bool_val(a.iter().all(|x| x.is_truthy()))) });
    reg!("or",  None, "Bool", |a, _| { check_no_bottom(a, "or")?;  Ok(bool_val(a.iter().any(|x| x.is_truthy()))) });
    reg!("not", None, "Bool", |a, _| { check_no_bottom(a, "not")?; Ok(bool_val(!a[0].is_truthy())) });

    // -- Collections (pure) -------------------------------------------------
    reg!("len", None, "Int", |a, _| {
        check_no_bottom(a, "len")?;
        let n = match a[0].payload() {
            Some(Payload::List(xs)) => xs.len(),
            Some(Payload::String(s)) => s.len(),
            Some(Payload::Map(m)) => m.len(),
            _ => return Err(Error::Primitive { fn_: "len".to_string(), cause: "expected list, string, or map".to_string() }),
        };
        Ok(int_val(n as i64))
    });
    reg!("list", None, "List", |a, _| {
        check_no_bottom(a, "list")?;
        Ok(list_out(a.to_vec()))
    });
    reg!("head", None, "Any", |a, _| {
        check_no_bottom(a, "head")?;
        let xs = list_val(&a[0], "head")?;
        xs.into_iter().next().ok_or_else(|| Error::Primitive { fn_: "head".to_string(), cause: "empty list".to_string() })
    });
    reg!("tail", None, "List", |a, _| {
        check_no_bottom(a, "tail")?;
        let xs = list_val(&a[0], "tail")?;
        Ok(list_out(xs.into_iter().skip(1).collect()))
    });
    reg!("append", None, "List", |a, _| {
        check_no_bottom(a, "append")?;
        let mut xs = list_val(&a[0], "append")?;
        xs.push(a[1].clone());
        Ok(list_out(xs))
    });
    reg!("contains_item", None, "Bool", |a, _| {
        check_no_bottom(a, "contains_item")?;
        let xs = list_val(&a[0], "contains_item")?;
        Ok(bool_val(xs.iter().any(|x| x.payload() == a[1].payload())))
    });
    reg!("reverse", None, "Any", |a, _| {
        check_no_bottom(a, "reverse")?;
        match a[0].payload() {
            Some(Payload::String(s)) => Ok(str_out(s.chars().rev().collect())),
            Some(Payload::List(xs)) => Ok(list_out(xs.iter().rev().cloned().collect())),
            _ => Err(Error::Primitive { fn_: "reverse".to_string(), cause: "expected string or list".to_string() }),
        }
    });
    reg!("is_sorted", None, "Bool", |a, _| {
        check_no_bottom(a, "is_sorted")?;
        let xs = list_val(&a[0], "is_sorted")?;
        let sorted = xs.windows(2).all(|w| {
            match (w[0].payload(), w[1].payload()) {
                (Some(Payload::Number(x)), Some(Payload::Number(y))) => x <= y,
                (Some(Payload::String(x)), Some(Payload::String(y))) => x <= y,
                _ => false,
            }
        });
        Ok(bool_val(sorted))
    });
    reg!("is_permutation", None, "Bool", |a, _| {
        check_no_bottom(a, "is_permutation")?;
        let xs = list_val(&a[0], "is_permutation")?;
        let ys = list_val(&a[1], "is_permutation")?;
        if xs.len() != ys.len() { return Ok(bool_val(false)); }
        // Compare sorted payloads via display strings (simple but correct for the test suite).
        let mut xs_s: Vec<String> = xs.iter().map(|v| format!("{:?}", v.payload())).collect();
        let mut ys_s: Vec<String> = ys.iter().map(|v| format!("{:?}", v.payload())).collect();
        xs_s.sort(); ys_s.sort();
        Ok(bool_val(xs_s == ys_s))
    });
    reg!("min_of", None, "Any", |a, _| {
        check_no_bottom(a, "min_of")?;
        let xs = list_val(&a[0], "min_of")?;
        if xs.is_empty() { return Err(Error::Primitive { fn_: "min_of".to_string(), cause: "empty list".to_string() }); }
        let mut best = xs[0].clone();
        for x in &xs[1..] {
            if let (Some(Payload::Number(bv)), Some(Payload::Number(xv))) = (best.payload(), x.payload()) {
                if xv < bv { best = x.clone(); }
            }
        }
        Ok(best)
    });
    reg!("max_of", None, "Any", |a, _| {
        check_no_bottom(a, "max_of")?;
        let xs = list_val(&a[0], "max_of")?;
        if xs.is_empty() { return Err(Error::Primitive { fn_: "max_of".to_string(), cause: "empty list".to_string() }); }
        let mut best = xs[0].clone();
        for x in &xs[1..] {
            if let (Some(Payload::Number(bv)), Some(Payload::Number(xv))) = (best.payload(), x.payload()) {
                if xv > bv { best = x.clone(); }
            }
        }
        Ok(best)
    });
    reg!("sum", None, "Number", |a, _| {
        check_no_bottom(a, "sum")?;
        let xs = list_val(&a[0], "sum")?;
        let total: f64 = xs.iter().map(|x| match x.payload() {
            Some(Payload::Number(n)) => *n,
            _ => 0.0,
        }).sum();
        Ok(num_val(total))
    });

    // -- Strings (pure) -----------------------------------------------------
    reg!("contains", None, "Bool", |a, _| {
        check_no_bottom(a, "contains")?;
        let h = str_val(&a[0], "contains")?;
        let n = str_val(&a[1], "contains")?;
        Ok(bool_val(h.contains(n.as_str())))
    });
    reg!("str", None, "String", |a, _| {
        check_no_bottom(a, "str")?;
        Ok(str_out(display(&a[0])))
    });
    reg!("upper", None, "String", |a, _| { check_no_bottom(a, "upper")?; Ok(str_out(str_val(&a[0],"upper")?.to_uppercase())) });
    reg!("lower", None, "String", |a, _| { check_no_bottom(a, "lower")?; Ok(str_out(str_val(&a[0],"lower")?.to_lowercase())) });
    reg!("trim",  None, "String", |a, _| { check_no_bottom(a, "trim")?;  Ok(str_out(str_val(&a[0],"trim")?.trim().to_string())) });
    reg!("starts_with", None, "Bool", |a, _| {
        check_no_bottom(a, "starts_with")?;
        Ok(bool_val(str_val(&a[0],"starts_with")?.starts_with(str_val(&a[1],"starts_with")?.as_str())))
    });
    reg!("ends_with", None, "Bool", |a, _| {
        check_no_bottom(a, "ends_with")?;
        Ok(bool_val(str_val(&a[0],"ends_with")?.ends_with(str_val(&a[1],"ends_with")?.as_str())))
    });
    reg!("replace", None, "String", |a, _| {
        check_no_bottom(a, "replace")?;
        Ok(str_out(str_val(&a[0],"replace")?.replace(str_val(&a[1],"replace")?.as_str(), str_val(&a[2],"replace")?.as_str())))
    });
    reg!("split", None, "List", |a, _| {
        check_no_bottom(a, "split")?;
        let s = str_val(&a[0], "split")?;
        let sep = str_val(&a[1], "split")?;
        Ok(list_out(s.split(sep.as_str()).map(|p| str_out(p.to_string())).collect()))
    });
    reg!("join", None, "String", |a, _| {
        check_no_bottom(a, "join")?;
        let sep = str_val(&a[0], "join")?;
        let xs = list_val(&a[1], "join")?;
        let parts: Vec<String> = xs.iter().map(|x| display(x)).collect();
        Ok(str_out(parts.join(sep.as_str())))
    });

    // -- Indexed access (pure, polymorphic) ---------------------------------
    reg!("slice", None, "Any", |a, _| {
        check_no_bottom(a, "slice")?;
        let start = num(&a[1], "slice")? as isize;
        let end   = num(&a[2], "slice")? as isize;
        match a[0].payload() {
            Some(Payload::String(s)) => {
                let chars: Vec<char> = s.chars().collect();
                let len = chars.len() as isize;
                let s2 = start.max(0).min(len) as usize;
                let e2 = end.max(0).min(len) as usize;
                Ok(str_out(chars[s2..e2.max(s2)].iter().collect()))
            }
            Some(Payload::List(xs)) => {
                let len = xs.len() as isize;
                let s2 = start.max(0).min(len) as usize;
                let e2 = end.max(0).min(len) as usize;
                Ok(list_out(xs[s2..e2.max(s2)].to_vec()))
            }
            _ => Err(Error::Primitive { fn_: "slice".to_string(), cause: "expected string or list".to_string() }),
        }
    });
    reg!("at", None, "Any", |a, _| {
        check_no_bottom(a, "at")?;
        let idx = num(&a[1], "at")? as isize;
        match a[0].payload() {
            Some(Payload::String(s)) => {
                let chars: Vec<char> = s.chars().collect();
                let len = chars.len() as isize;
                let i = if idx < 0 { len + idx } else { idx };
                if i < 0 || i >= len {
                    return Err(Error::Primitive { fn_: "at".to_string(), cause: format!("index {} out of range for length {}", idx, len) });
                }
                Ok(str_out(chars[i as usize].to_string()))
            }
            Some(Payload::List(xs)) => {
                let len = xs.len() as isize;
                let i = if idx < 0 { len + idx } else { idx };
                if i < 0 || i >= len {
                    return Err(Error::Primitive { fn_: "at".to_string(), cause: format!("index {} out of range for length {}", idx, len) });
                }
                Ok(xs[i as usize].clone())
            }
            _ => Err(Error::Primitive { fn_: "at".to_string(), cause: "expected string or list".to_string() }),
        }
    });
    reg!("char_at", None, "String", |a, _| {
        check_no_bottom(a, "char_at")?;
        let s = str_val(&a[0], "char_at")?;
        let idx = num(&a[1], "char_at")? as isize;
        let chars: Vec<char> = s.chars().collect();
        let len = chars.len() as isize;
        let i = if idx < 0 { len + idx } else { idx };
        if i < 0 || i >= len {
            return Err(Error::Primitive { fn_: "char_at".to_string(), cause: format!("index {} out of range", idx) });
        }
        Ok(str_out(chars[i as usize].to_string()))
    });
    reg!("indexof", None, "Int", |a, _| {
        check_no_bottom(a, "indexof")?;
        match a[0].payload() {
            Some(Payload::String(h)) => {
                let n = str_val(&a[1], "indexof")?;
                Ok(int_val(h.find(n.as_str()).map(|i| i as i64).unwrap_or(-1)))
            }
            Some(Payload::List(xs)) => {
                let pos = xs.iter().position(|x| x.payload() == a[1].payload());
                Ok(int_val(pos.map(|i| i as i64).unwrap_or(-1)))
            }
            _ => Err(Error::Primitive { fn_: "indexof".to_string(), cause: "expected string or list".to_string() }),
        }
    });

    // -- Confidence (pure) --------------------------------------------------
    reg!("conf", None, "Float", |a, _| {
        check_no_bottom(a, "conf")?;
        Ok(num_val(a[0].conf()))
    });
    reg!("belief", None, "Any", |a, _| {
        check_no_bottom(a, "belief")?;
        let c = num(&a[1], "belief")?;
        if c < 0.0 || c > 1.0 {
            return Err(Error::Primitive { fn_: "belief".to_string(), cause: format!("confidence must be in [0.0, 1.0], got {}", c) });
        }
        let inner = match &a[0] {
            Value::Concrete(cv) => cv.clone(),
            Value::Belief(b) => b.about.clone(),
            Value::Bottom { .. } => return Err(Error::BottomPropagation { fn_: "belief".to_string() }),
        };
        Ok(Value::Belief(Box::new(Belief { about: inner, conf: c })))
    });

    // -- Refusal helpers (pure) ---------------------------------------------
    // is_bottom must NOT trigger the BottomPropagation guard — its entire
    // purpose is to test whether a value is Bottom. The guard runs in
    // call_primitive before the fn_ is called; we bypass it by handling
    // Bottom explicitly inside the fn_ and registering with no effect.
    reg!("is_bottom", None, "Bool", |a, _| {
        // Intentionally does NOT call check_no_bottom — that would defeat
        // the purpose. is_bottom is the one primitive that accepts Bottom.
        Ok(bool_val(a[0].is_bottom()))
    });

    // -- I/O (effectful) ----------------------------------------------------
    reg!("io.say", Some("io.stdout"), "String", |a, trace| {
        check_no_bottom(a, "io.say")?;
        let text = display(&a[0]);
        trace.stdout.push(format!("{}\n", text));
        println!("{}", text);
        Ok(str_out(text))
    });

    // -- Clock (effectful) --------------------------------------------------
    reg!("clock.now", Some("clock.read"), "Clock", |_a, trace| {
        use std::time::{SystemTime, UNIX_EPOCH};
        let unix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);
        trace.clock_reads.push(unix);
        // Get local time using the system's UTC offset.
        // We use the C library localtime_r for correctness on all platforms.
        let secs = unix as i64;
        let (hh, mm) = local_hm(secs);
        let hm = format!("{:02}:{:02}", hh, mm);
        let map = vec![
            ("hm".to_string(), str_out(hm)),
            ("unix".to_string(), num_val(unix)),
        ];
        Ok(Value::with_type(Payload::Map(map), "Clock"))
    });

    // -- Model stubs (effectful) --------------------------------------------
    reg!("vision.classify", Some("model.vision"), "Label", |a, trace| {
        check_no_bottom(a, "vision.classify")?;
        let (tag, conf) = match a[0].payload() {
            Some(Payload::Map(m)) => {
                let tag = m.iter().find(|(k, _)| k == "tag")
                    .and_then(|(_, v)| match v.payload() { Some(Payload::String(s)) => Some(s.clone()), _ => None })
                    .unwrap_or_else(|| "unknown".to_string());
                let conf = m.iter().find(|(k, _)| k == "conf")
                    .and_then(|(_, v)| match v.payload() { Some(Payload::Number(n)) => Some(*n), _ => None })
                    .unwrap_or(0.0);
                (tag, conf)
            }
            _ => ("unknown".to_string(), 0.0),
        };
        trace.model_calls.push(("vision.classify".to_string(), tag.clone()));
        let about = Concrete { payload: Payload::String(tag), type_: "Label".to_string(), conf: 1.0, provenance: "model.vision".to_string() };
        Ok(Value::Belief(Box::new(Belief { about, conf })))
    });
    reg!("escalate", Some("model.vision"), "String", |a, trace| {
        check_no_bottom(a, "escalate")?;
        let label = display(&a[1]);
        trace.model_calls.push(("escalate".to_string(), label.clone()));
        Ok(str_out(format!("escalated:{}", label)))
    });

    // -- Host bridges (pure) ------------------------------------------------
    reg!("host_sorted", None, "List", |a, _| {
        check_no_bottom(a, "host_sorted")?;
        let mut xs = list_val(&a[0], "host_sorted")?;
        xs.sort_by(|x, y| {
            match (x.payload(), y.payload()) {
                (Some(Payload::Number(a)), Some(Payload::Number(b))) => a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal),
                (Some(Payload::String(a)), Some(Payload::String(b))) => a.cmp(b),
                _ => std::cmp::Ordering::Equal,
            }
        });
        Ok(list_out(xs))
    });
    reg!("host_image", None, "Image", |a, _| {
        check_no_bottom(a, "host_image")?;
        let tag = str_val(&a[0], "host_image")?;
        let conf = num(&a[1], "host_image")?;
        let map = vec![
            ("tag".to_string(), str_out(tag)),
            ("conf".to_string(), num_val(conf)),
        ];
        Ok(Value::with_type(Payload::Map(map), "Image"))
    });

    PrimitiveRegistry { prims }
}

// ---------------------------------------------------------------------------
// Platform helpers
// ---------------------------------------------------------------------------

/// Get local (hour, minute) from a Unix timestamp using the C library.
/// This matches Python's `time.localtime()` behavior.
fn local_hm(unix_secs: i64) -> (u32, u32) {
    #[cfg(unix)]
    {
        use std::mem::MaybeUninit;
        extern "C" {
            fn localtime_r(timep: *const i64, result: *mut libc_tm) -> *mut libc_tm;
        }
        #[repr(C)]
        struct libc_tm {
            tm_sec: i32, tm_min: i32, tm_hour: i32,
            tm_mday: i32, tm_mon: i32, tm_year: i32,
            tm_wday: i32, tm_yday: i32, tm_isdst: i32,
            // padding for platforms that have extra fields
            _pad: [i64; 4],
        }
        let mut tm: MaybeUninit<libc_tm> = MaybeUninit::uninit();
        unsafe {
            localtime_r(&unix_secs, tm.as_mut_ptr());
            let tm = tm.assume_init();
            (tm.tm_hour as u32, tm.tm_min as u32)
        }
    }
    #[cfg(not(unix))]
    {
        // Fallback: UTC
        let mins_total = ((unix_secs / 60) % (24 * 60)) as u32;
        (mins_total / 60, mins_total % 60)
    }
}
