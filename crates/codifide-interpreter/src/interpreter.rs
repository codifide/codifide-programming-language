//! Codifide tree-walking interpreter — Rust production runtime.
//!
//! Mirrors `codifide/runtime/interpreter.py` exactly. Python is the spec;
//! this file must match it on every observable behavior.
//!
//! The parallel evaluator in `parallel.rs` extends this with concurrent
//! evaluation of independent sub-expressions. See
//! `dispatches/2026-05-12-parallel-evaluator-proposal.readout.md`.

use std::collections::HashMap;

use codifide_canonical::ast::{Candidate, Definition, Expr, Module};

use crate::errors::{general, Error};
use crate::parallel;
use crate::primitives::{build_default_registry, EffectTrace, PrimitiveRegistry};
use crate::value::{payload_from_json, Concrete, Payload, Value};

/// Default maximum Codifide call depth. Mirrors Python's DEFAULT_MAX_DEPTH = 64.
pub const DEFAULT_MAX_DEPTH: usize = 64;

/// Sentinel cost for un-annotated candidates: +∞ represented as u64::MAX.
/// Mirrors Python's `_COST_INFINITY = (1 << 63) - 1`.
const COST_INFINITY: u64 = u64::MAX;

// ---------------------------------------------------------------------------
// Public entry point
// ---------------------------------------------------------------------------

/// Run a Codifide module starting from an entry definition.
///
/// Returns the result value. Raises a typed `Error` on any violation.
/// Mirrors Python's `run()`.
pub fn run(module: &Module, entry: &str, args: Vec<Value>) -> Result<Value, Error> {
    run_with_imports(module, entry, args, HashMap::new())
}

/// Run a Codifide module with pre-resolved imports.
///
/// `resolved_imports` maps local name → Definition for all imported symbols.
/// This mirrors Python's `_ResolvedImports` pattern.
pub fn run_with_imports(
    module: &Module,
    entry: &str,
    args: Vec<Value>,
    resolved_imports: HashMap<String, Definition>,
) -> Result<Value, Error> {
    check_transitive_effects(module)?;
    let mut interp = Interpreter::new_with_imports(module, DEFAULT_MAX_DEPTH, resolved_imports);
    let result = interp.invoke(entry, args)?;
    if result.is_bottom() {
        return Err(Error::Refusal { fn_: entry.to_string() });
    }
    Ok(result)
}

// ---------------------------------------------------------------------------
// Transitive effect check (static pass at module load)
// ---------------------------------------------------------------------------

/// Verify callee-effects ⊆ caller-effects across the whole call graph.
/// Mirrors Python's `_check_transitive_effects`.
fn check_transitive_effects(module: &Module) -> Result<(), Error> {
    for (caller_name, caller_def) in &module.symbols {
        let caller_effects = &caller_def.signature.effects;
        for expr in all_exprs_of(caller_def) {
            for callee_name in call_targets(expr) {
                if let Some((_, callee_def)) = module.symbols.iter().find(|(n, _)| n == callee_name) {
                    let callee_effects = &callee_def.signature.effects;
                    for eff in callee_effects {
                        if !caller_effects.contains(eff) {
                            return Err(Error::Effect {
                                fn_: caller_name.clone(),
                                declared: caller_effects.clone(),
                                observed: eff.clone(),
                            });
                        }
                    }
                }
                // Primitives are checked at runtime; imports not supported in v2-A initial port.
            }
        }
    }
    Ok(())
}

fn all_exprs_of(defn: &Definition) -> Vec<&Expr> {
    let mut out = Vec::new();
    for e in &defn.pre { walk(e, &mut out); }
    for e in &defn.post { walk(e, &mut out); }
    for cand in &defn.candidates {
        if let Some(g) = &cand.guard { walk(g, &mut out); }
        walk(&cand.body, &mut out);
    }
    out
}

fn walk<'a>(expr: &'a Expr, out: &mut Vec<&'a Expr>) {
    out.push(expr);
    match expr {
        Expr::Call { args, .. } => { for a in args { walk(a, out); } }
        Expr::Bind { expr: e, body, .. } => { walk(e, out); walk(body, out); }
        Expr::Seq { steps } => { for s in steps { walk(s, out); } }
        Expr::Concat { parts } => { for p in parts { walk(p, out); } }
        Expr::Believe { subject, arms, otherwise } => {
            walk(subject, out);
            for (c, v) in arms { walk(c, out); walk(v, out); }
            walk(otherwise, out);
        }
        Expr::Attr { target, .. } => { walk(target, out); }
        Expr::If { cond, then_, else_ } => { walk(cond, out); walk(then_, out); walk(else_, out); }
        _ => {}
    }
}

fn call_targets(expr: &Expr) -> Vec<&str> {
    match expr {
        Expr::Call { fn_, .. } => vec![fn_.as_str()],
        _ => vec![],
    }
}

// ---------------------------------------------------------------------------
// Interpreter
// ---------------------------------------------------------------------------

struct Frame<'m> {
    defn: &'m Definition,
    locals: HashMap<String, Value>,
    /// When Some, overrides the signature's effect set (used for contract purity).
    effect_budget: Option<Vec<String>>,
}

impl<'m> Frame<'m> {
    fn allowed_effects(&self) -> &[String] {
        if let Some(budget) = &self.effect_budget {
            budget.as_slice()
        } else {
            &self.defn.signature.effects
        }
    }

    fn with_pure_budget(&self) -> Frame<'m> {
        Frame {
            defn: self.defn,
            locals: self.locals.clone(),
            effect_budget: Some(vec![]),
        }
    }

    fn with_locals(&self, locals: HashMap<String, Value>) -> Frame<'m> {
        Frame {
            defn: self.defn,
            locals,
            effect_budget: self.effect_budget.clone(),
        }
    }
}

pub struct Interpreter<'m> {
    module: &'m Module,
    max_depth: usize,
    depth: usize,
    prims: PrimitiveRegistry,
    trace: EffectTrace,
    /// Pre-resolved imports: local_name → Definition.
    /// Populated from the module's imports table at run time.
    resolved_imports: HashMap<String, Definition>,
}

impl<'m> Interpreter<'m> {
    pub fn new(module: &'m Module, max_depth: usize) -> Self {
        Interpreter {
            module,
            max_depth,
            depth: 0,
            prims: build_default_registry(),
            trace: EffectTrace::fresh(),
            resolved_imports: HashMap::new(),
        }
    }

    pub fn new_with_imports(
        module: &'m Module,
        max_depth: usize,
        resolved_imports: HashMap<String, Definition>,
    ) -> Self {
        Interpreter {
            module,
            max_depth,
            depth: 0,
            prims: build_default_registry(),
            trace: EffectTrace::fresh(),
            resolved_imports,
        }
    }

    fn push_depth(&mut self) -> Result<(), Error> {
        if self.depth >= self.max_depth {
            return Err(Error::RecursionLimit { depth: self.max_depth });
        }
        self.depth += 1;
        Ok(())
    }

    fn pop_depth(&mut self) {
        self.depth -= 1;
    }

    pub fn invoke(&mut self, name: &str, args: Vec<Value>) -> Result<Value, Error> {
        let defn = self.module.symbols.iter()
            .find(|(n, _)| n == name)
            .map(|(_, d)| d)
            .ok_or_else(|| general(format!("no such definition: {:?}", name)))?;
        self.invoke_defn(defn, args)
    }

    fn invoke_defn(&mut self, defn: &'m Definition, args: Vec<Value>) -> Result<Value, Error> {
        self.push_depth()?;
        let result = self.invoke_defn_inner(defn, args);
        self.pop_depth();
        result
    }

    /// Invoke an owned Definition (from resolved imports).
    /// We box it to get a stable address, then use the same unsafe lifetime
    /// extension as the borrowed path.
    ///
    /// Safety: `boxed` must remain live for the entire duration of
    /// `invoke_defn_inner`, including any recursive calls it makes.
    /// We achieve this by calling `drop(boxed)` explicitly AFTER
    /// `invoke_defn_inner` returns — never before. Do not reorder these
    /// statements. The Rust drop order for locals would drop `boxed` before
    /// `result` is returned if we relied on implicit drop, which would be UB.
    fn invoke_defn_owned(&mut self, defn: Definition, args: Vec<Value>) -> Result<Value, Error> {
        let boxed = Box::new(defn);
        let defn_ref: &Definition = &*boxed;
        // Safety: boxed is kept alive (not dropped) until after invoke_defn_inner
        // returns. The explicit drop(boxed) below enforces this. Do not move
        // drop(boxed) before the result assignment.
        let defn_ref: &'m Definition = unsafe { &*(defn_ref as *const Definition) };
        self.push_depth()?;
        let result = self.invoke_defn_inner(defn_ref, args);
        self.pop_depth();
        // IMPORTANT: drop(boxed) must come after invoke_defn_inner returns.
        // Moving this before the call would invalidate defn_ref mid-execution.
        drop(boxed);
        result
    }

    fn invoke_defn_inner(&mut self, defn: &'m Definition, args: Vec<Value>) -> Result<Value, Error> {
        // Bind parameters.
        let mut locals = HashMap::new();
        for (i, p) in defn.signature.params.iter().enumerate() {
            let v = args.get(i).cloned().unwrap_or(Value::Bottom);
            locals.insert(p.name.clone(), v);
        }

        let frame = Frame { defn, locals, effect_budget: None };

        // Preconditions (pure budget).
        for clause in &defn.pre {
            let pure = frame.with_pure_budget();
            let result = self.eval(clause, &pure)?;
            if !result.is_truthy() {
                return Err(Error::Contract {
                    fn_: defn.intent.clone(), // use intent as name for now
                    kind: "pre",
                    clause: describe(clause),
                    intent: defn.intent.clone(),
                });
            }
        }

        // Dispatch.
        let result = self.dispatch(defn, &frame)?;

        // Postconditions (skipped on Bottom).
        if !result.is_bottom() {
            for clause in &defn.post {
                let mut post_locals = frame.locals.clone();
                post_locals.insert("result".to_string(), result.clone());
                let post_frame = Frame { defn, locals: post_locals, effect_budget: Some(vec![]) };
                let ok = self.eval(clause, &post_frame)?;
                if !ok.is_truthy() {
                    return Err(Error::Contract {
                        fn_: defn.intent.clone(),
                        kind: "post",
                        clause: describe(clause),
                        intent: defn.intent.clone(),
                    });
                }
            }
        }

        Ok(result)
    }

    fn dispatch(&mut self, defn: &'m Definition, frame: &Frame<'m>) -> Result<Value, Error> {
        let pure = frame.with_pure_budget();
        let mut satisfied: Vec<(u64, usize, &Candidate)> = Vec::new();
        for (idx, cand) in defn.candidates.iter().enumerate() {
            let guard_ok = match &cand.guard {
                None => true,
                Some(g) => self.eval(g, &pure)?.is_truthy(),
            };
            if guard_ok {
                let cost = cand.cost.unwrap_or(COST_INFINITY);
                satisfied.push((cost, idx, cand));
            }
        }
        if satisfied.is_empty() {
            return Err(Error::Dispatch { fn_: defn.intent.clone() });
        }
        satisfied.sort_by_key(|(cost, idx, _)| (*cost, *idx));
        let (_, _, chosen) = satisfied[0];
        self.eval(&chosen.body, frame)
    }

    fn eval(&mut self, expr: &Expr, frame: &Frame<'m>) -> Result<Value, Error> {
        match expr {
            Expr::Lit { value, type_, conf, .. } => {
                Ok(Value::Concrete(Concrete {
                    payload: payload_from_json(value),
                    type_: type_.clone(),
                    conf: *conf,
                    provenance: "literal".to_string(),
                }))
            }

            Expr::Ref { name } => {
                if let Some(v) = frame.locals.get(name.as_str()) {
                    return Ok(v.clone());
                }
                Err(general(unknown_callable_message(name)))
            }

            Expr::Attr { target, name: attr_name } => {
                // Dotted primitive (e.g. clock.now) — try before evaluating target.
                if let Expr::Ref { name: ref_name } = target.as_ref() {
                    if !frame.locals.contains_key(ref_name.as_str()) {
                        let dotted = format!("{}.{}", ref_name, attr_name);
                        if self.prims.has(&dotted) {
                            return self.call_primitive(&dotted, &[], frame);
                        }
                        return Err(general(unknown_callable_message(&dotted)));
                    }
                }
                let tgt = self.eval(target, frame)?;
                match tgt.payload() {
                    Some(Payload::Map(m)) => {
                        m.iter().find(|(k, _)| k == attr_name)
                            .map(|(_, v)| v.clone())
                            .ok_or_else(|| general(format!("no field {:?} on map", attr_name)))
                    }
                    _ => Err(general(format!("no field {:?} on value", attr_name))),
                }
            }

            Expr::Call { fn_, args } => {
                self.call(fn_, args, frame)
            }

            Expr::Bind { name, expr: e, body } => {
                let val = self.eval(e, frame)?;
                let mut new_locals = frame.locals.clone();
                new_locals.insert(name.clone(), val);
                self.eval(body, &frame.with_locals(new_locals))
            }

            Expr::Seq { steps } => {
                let mut result = Value::Bottom;
                for step in steps {
                    result = self.eval(step, frame)?;
                }
                Ok(result)
            }

            Expr::Concat { parts } => {
                // Parallel path: if parts are effect-disjoint and at least
                // one contains a user call, evaluate in parallel.
                let part_refs: Vec<&Expr> = parts.iter().collect();
                if parallel::should_parallelize(&part_refs, self.module) {
                    let vals = self.eval_parallel_exprs(&part_refs, frame)?;
                    let mut s = String::new();
                    for v in vals {
                        match v.payload() {
                            Some(Payload::String(ps)) => s.push_str(ps),
                            Some(other) => s.push_str(&format!("{:?}", other)),
                            None => s.push_str("⊥"),
                        }
                    }
                    return Ok(Value::with_type(Payload::String(s), "String"));
                }
                // Sequential fallback.
                let mut s = String::new();
                for p in parts {
                    let v = self.eval(p, frame)?;
                    match v.payload() {
                        Some(Payload::String(ps)) => s.push_str(ps),
                        Some(other) => s.push_str(&format!("{:?}", other)),
                        None => s.push_str("⊥"),
                    }
                }
                Ok(Value::with_type(Payload::String(s), "String"))
            }

            Expr::Bottom => Ok(Value::Bottom),

            Expr::If { cond, then_, else_ } => {
                let c = self.eval(cond, frame)?;
                if c.is_truthy() {
                    self.eval(then_, frame)
                } else {
                    self.eval(else_, frame)
                }
            }

            Expr::Believe { subject, arms, otherwise } => {
                let subj = self.eval(subject, frame)?;
                let mut inner_locals = frame.locals.clone();
                inner_locals.insert("it".to_string(), subj.clone());
                let inner = frame.with_locals(inner_locals);
                for (cond, val) in arms {
                    let c = self.eval(cond, &inner)?;
                    if c.is_truthy() {
                        return self.eval(val, &inner);
                    }
                }
                self.eval(otherwise, &inner)
            }
        }
    }

    fn call(&mut self, fn_: &str, arg_exprs: &[Expr], frame: &Frame<'m>) -> Result<Value, Error> {
        // User-defined function (local symbols).
        if let Some((_, defn)) = self.module.symbols.iter().find(|(n, _)| n == fn_) {
            let r: Result<Vec<_>, _> = arg_exprs.iter().map(|a| self.eval(a, frame)).collect();
            let vals = r?;
            // Safety: defn lifetime is tied to module which outlives self.
            let defn: &'m Definition = unsafe { &*(defn as *const Definition) };
            return self.invoke_defn(defn, vals);
        }
        // Imported symbol — clone the definition so we can call it.
        if let Some(defn) = self.resolved_imports.get(fn_).cloned() {
            let r: Result<Vec<_>, _> = arg_exprs.iter().map(|a| self.eval(a, frame)).collect();
            let vals = r?;
            return self.invoke_defn_owned(defn, vals);
        }
        // Primitive.
        if self.prims.has(fn_) {
            return self.call_primitive(fn_, arg_exprs, frame);
        }
        Err(general(unknown_callable_message(fn_)))
    }

    /// Call `fn_` with pre-evaluated argument values (used by the parallel path).
    fn call_with_vals(&mut self, fn_: &str, vals: Vec<Value>, frame: &Frame<'m>) -> Result<Value, Error> {
        // User-defined function.
        if let Some((_, defn)) = self.module.symbols.iter().find(|(n, _)| n == fn_) {
            let defn: &'m Definition = unsafe { &*(defn as *const Definition) };
            return self.invoke_defn(defn, vals);
        }
        // Primitive: call with pre-evaluated values directly.
        if let Some(spec) = self.prims.get(fn_) {
            let effect = spec.effect;
            let fn_ptr: *const dyn Fn(&[Value], &mut EffectTrace) -> Result<Value, Error> =
                spec.fn_.as_ref() as *const _;
            let allowed = frame.allowed_effects();
            if let Some(eff) = effect {
                if !allowed.contains(&eff.to_string()) {
                    return Err(Error::Effect {
                        fn_: frame.defn.intent.clone(),
                        declared: allowed.to_vec(),
                        observed: eff.to_string(),
                    });
                }
            }
            if fn_ != "is_bottom" {
                for a in &vals {
                    if a.is_bottom() {
                        return Err(Error::BottomPropagation { fn_: fn_.to_string() });
                    }
                }
            }
            return unsafe { (*fn_ptr)(&vals, &mut self.trace) };
        }
        Err(general(unknown_callable_message(fn_)))
    }

    /// into `self.trace` in declaration order (PE-1).
    fn eval_parallel_exprs(&mut self, exprs: &[&Expr], frame: &Frame<'m>) -> Result<Vec<Value>, Error> {
        let current_depth = self.depth;
        let max_depth = self.max_depth;
        let locals_snapshot = frame.locals.clone();
        let effect_budget = frame.effect_budget.clone();

        // Transmit pointers as usize (which is Send). We reconstruct them
        // inside each closure. Safety: Module, Definition, and Expr are
        // immutable during parallel evaluation and outlive all branches.
        let module_addr: usize = self.module as *const Module as usize;
        let defn_addr: usize = frame.defn as *const Definition as usize;

        let n = exprs.len();
        let mut slots: Vec<Option<(Result<Value, Error>, EffectTrace)>> =
            (0..n).map(|_| None).collect();

        rayon::scope(|s| {
            let slots_ptr = slots.as_mut_ptr();
            for (idx, expr) in exprs.iter().enumerate() {
                let expr_addr: usize = (*expr) as *const Expr as usize;
                // Safety: each closure writes to a distinct slot index — no aliasing.
                let slot_addr: usize = unsafe { slots_ptr.add(idx) }
                    as *mut Option<(Result<Value, Error>, EffectTrace)> as usize;
                let locals = locals_snapshot.clone();
                let budget = effect_budget.clone();

                s.spawn(move |_| {
                    let module: &Module = unsafe { &*(module_addr as *const Module) };
                    let defn: &Definition = unsafe { &*(defn_addr as *const Definition) };
                    let expr: &Expr = unsafe { &*(expr_addr as *const Expr) };

                    let mut branch_interp = Interpreter {
                        module,
                        max_depth,
                        depth: current_depth,
                        prims: build_default_registry(),
                        trace: EffectTrace::fresh(),
                        // Note: resolved_imports is not passed to branch interpreters.
                        // Imported symbols are not available in parallel branches.
                        // This is a known limitation (AUD-OVERNIGHT-02). If a parallel
                        // branch calls an imported symbol, it will fail with
                        // unknown_callable. Fix: pass resolved_imports here when the
                        // parallel evaluator gains full import support.
                        resolved_imports: HashMap::new(),
                    };
                    let branch_frame = Frame { defn, locals, effect_budget: budget };
                    let result = branch_interp.eval(expr, &branch_frame);
                    let branch_trace = branch_interp.trace;
                    let slot = slot_addr as *mut Option<(Result<Value, Error>, EffectTrace)>;
                    unsafe { *slot = Some((result, branch_trace)); }
                });
            }
        });

        // Merge traces in declaration order (PE-1), then extract values.
        let mut values = Vec::with_capacity(n);
        for slot in slots {
            let (result, branch_trace) = slot.expect("parallel branch did not complete");
            parallel::merge_traces(&mut self.trace, vec![branch_trace]);
            values.push(result?);
        }
        Ok(values)
    }

    fn call_primitive(&mut self, name: &str, arg_exprs: &[Expr], frame: &Frame<'m>) -> Result<Value, Error> {
        // Extract spec metadata before any mutable borrow of self.
        let (effect, fn_ptr) = {
            let spec = self.prims.get(name)
                .ok_or_else(|| general(format!("unknown primitive: {:?}", name)))?;
            let effect = spec.effect;
            // Safety: the registry is immutable for the lifetime of the interpreter;
            // the fn_ pointer remains valid. We extract it here to release the
            // shared borrow on self.prims before we need &mut self for eval.
            let fn_ptr: *const dyn Fn(&[Value], &mut EffectTrace) -> Result<Value, Error> =
                spec.fn_.as_ref() as *const _;
            (effect, fn_ptr)
        };

        // Effect check.
        let allowed = frame.allowed_effects();
        if let Some(eff) = effect {
            if !allowed.contains(&eff.to_string()) {
                return Err(Error::Effect {
                    fn_: frame.defn.intent.clone(),
                    declared: allowed.to_vec(),
                    observed: eff.to_string(),
                });
            }
        }

        // Evaluate arguments (needs &mut self, safe now that prims borrow is released).
        let args: Result<Vec<_>, _> = arg_exprs.iter().map(|a| self.eval(a, frame)).collect();
        let args = args?;

        // Bottom propagation guard. is_bottom is the one primitive that
        // explicitly accepts Bottom as an argument; all others reject it.
        if name != "is_bottom" {
            for a in &args {
                if a.is_bottom() {
                    return Err(Error::BottomPropagation { fn_: name.to_string() });
                }
            }
        }

        // Call via the extracted pointer.
        unsafe { (*fn_ptr)(&args, &mut self.trace) }
    }
}

// ---------------------------------------------------------------------------
// Error message helpers (mirrors Python's hint tables)
// ---------------------------------------------------------------------------

fn unknown_callable_message(fn_: &str) -> String {
    let base = format!("unknown callable: {:?}", fn_);
    let hint = CALLABLE_HINTS.iter().find(|(k, _)| *k == fn_).map(|(_, v)| *v);
    match hint {
        Some(h) => format!("{}\n  hint: {}", base, h),
        None => base,
    }
}

const CALLABLE_HINTS: &[(&str, &str)] = &[
    ("str.reverse",    "use `reverse(s)` — `reverse` is polymorphic over strings and lists"),
    ("str.upper",      "use `upper(s)`"),
    ("str.lower",      "use `lower(s)`"),
    ("str.trim",       "use `trim(s)`"),
    ("str.split",      "use `split(s, sep)`"),
    ("str.replace",    "use `replace(s, old, new)`"),
    ("str.join",       "use `join(sep, xs)`"),
    ("str.contains",   "use `contains(s, needle)`"),
    ("str.starts_with","use `starts_with(s, prefix)`"),
    ("str.ends_with",  "use `ends_with(s, suffix)`"),
    ("clock.hour",     "use `clock.now` — returns a record with fields `hm` and `unix`"),
    ("clock.minute",   "use `clock.now` — returns a record with fields `hm` and `unix`"),
    ("clock.second",   "use `clock.now` — returns a record with fields `hm` and `unix`"),
    ("list.reverse",   "use `reverse(xs)`"),
    ("list.len",       "use `len(xs)`"),
    ("list.append",    "use `append(xs, item)` — returns a new list"),
    ("list.head",      "use `head(xs)`"),
    ("list.tail",      "use `tail(xs)`"),
    ("list.sum",       "use `sum(xs)`"),
];

fn describe(expr: &Expr) -> String {
    match expr {
        Expr::Call { fn_, args } => {
            let arg_strs: Vec<_> = args.iter().map(describe).collect();
            format!("{}({})", fn_, arg_strs.join(", "))
        }
        Expr::Ref { name } => name.clone(),
        Expr::Attr { target, name } => format!("{}.{}", describe(target), name),
        Expr::Lit { value, .. } => value.to_string(),
        Expr::Bottom => "bottom".to_string(),
        Expr::Concat { parts } => parts.iter().map(describe).collect::<Vec<_>>().join(" ++ "),
        Expr::If { cond, then_, else_ } => {
            format!("if {} then {} else {}", describe(cond), describe(then_), describe(else_))
        }
        _ => format!("{:?}", std::mem::discriminant(expr)),
    }
}
