//! Graph-native parallel evaluator for Codifide.
//!
//! Parallelizes independent sub-expressions at the node level using Rayon.
//! The sequential tree-walker in `interpreter.rs` is the reference; this
//! module adds parallelism where the effect algebra permits it.
//!
//! ## Parallelism sites
//!
//! - `Call` arguments: `list(f(1), f(2), f(3))` — args are independent.
//! - `Concat` parts: `a ++ b ++ c` — parts are independent.
//!
//! `Believe` arm parallelism is deferred (PE-5 from Sable audit).
//!
//! ## Effect constraint (PE-1)
//!
//! Two parallel tasks that share an effect label must serialize. The
//! `expr_effects` function computes a conservative static over-approximation
//! of the effects reachable from an expression. If any two args share an
//! effect, the whole set evaluates sequentially.
//!
//! Trace merge uses indexed collection to preserve declaration order (PE-1).
//!
//! ## Depth counter (PE-3)
//!
//! Each parallel branch gets its own `Interpreter` initialized with the
//! parent's current depth. This preserves the recursion limit semantics
//! without a shared mutable counter.
//!
//! ## Threshold (PE-4)
//!
//! Only parallelize when at least one arg contains a `Call` to a
//! user-defined function (local or imported). Pure expressions (Lit, Ref,
//! Attr on a local, Concat of literals) are not worth spawning threads for.
//!
//! ## Import support (V3-1 / AUD-OVERNIGHT-02)
//!
//! Branch interpreters now receive the parent's `resolved_imports` so that
//! imported symbols are available inside parallel branches. The threshold
//! functions accept `resolved_imports` and treat imported symbols the same
//! as local symbols for eligibility purposes.

use std::collections::HashMap;
use std::collections::HashSet;
use rayon::prelude::*;

use codifide_canonical::ast::{Definition, Expr, Module};

use crate::errors::Error;
use crate::primitives::EffectTrace;
use crate::value::Value;

// ---------------------------------------------------------------------------
// Static effect analysis
// ---------------------------------------------------------------------------

/// Compute the conservative set of effect labels reachable from `expr`.
///
/// Uses declared signature effects for user-defined function calls (PE-2),
/// including imported symbols (V3-1). This is a static over-approximation:
/// it includes effects from all branches of an `If`, even though only one
/// branch evaluates at runtime. Conservative is correct — it may serialize
/// expressions that could theoretically run in parallel, but never runs two
/// expressions in parallel when they shouldn't be.
pub fn expr_effects(
    expr: &Expr,
    module: &Module,
    resolved_imports: &HashMap<String, Definition>,
) -> HashSet<String> {
    let mut out = HashSet::new();
    collect_effects(expr, module, resolved_imports, &mut out);
    out
}

fn collect_effects(
    expr: &Expr,
    module: &Module,
    resolved_imports: &HashMap<String, Definition>,
    out: &mut HashSet<String>,
) {
    match expr {
        Expr::Call { fn_, args } => {
            // Local user-defined function: use its declared signature effects.
            if let Some((_, defn)) = module.symbols.iter().find(|(n, _)| n == fn_) {
                for eff in &defn.signature.effects {
                    out.insert(eff.clone());
                }
            }
            // Imported symbol: use its declared signature effects (V3-1).
            else if let Some(defn) = resolved_imports.get(fn_.as_str()) {
                for eff in &defn.signature.effects {
                    out.insert(eff.clone());
                }
            }
            // Primitive: effect is checked at runtime; we don't have a
            // static registry here. For safety, we don't add primitive
            // effects statically — the parallel path only fires when
            // user-defined calls are present (threshold check), and
            // primitive-only expressions are pure by the threshold rule.
            for a in args { collect_effects(a, module, resolved_imports, out); }
        }
        Expr::Bind { expr: e, body, .. } => {
            collect_effects(e, module, resolved_imports, out);
            collect_effects(body, module, resolved_imports, out);
        }
        Expr::Seq { steps } => {
            for s in steps { collect_effects(s, module, resolved_imports, out); }
        }
        Expr::Concat { parts } => {
            for p in parts { collect_effects(p, module, resolved_imports, out); }
        }
        Expr::Believe { subject, arms, otherwise } => {
            collect_effects(subject, module, resolved_imports, out);
            for (c, v) in arms {
                collect_effects(c, module, resolved_imports, out);
                collect_effects(v, module, resolved_imports, out);
            }
            collect_effects(otherwise, module, resolved_imports, out);
        }
        Expr::Attr { target, .. } => { collect_effects(target, module, resolved_imports, out); }
        Expr::If { cond, then_, else_ } => {
            collect_effects(cond, module, resolved_imports, out);
            collect_effects(then_, module, resolved_imports, out);
            collect_effects(else_, module, resolved_imports, out);
        }
        // Lit, Ref, Bottom: no effects.
        _ => {}
    }
}

// ---------------------------------------------------------------------------
// Parallelism eligibility
// ---------------------------------------------------------------------------

/// Are all pairs of expressions in `exprs` effect-disjoint?
pub fn all_disjoint(
    exprs: &[&Expr],
    module: &Module,
    resolved_imports: &HashMap<String, Definition>,
) -> bool {
    if exprs.len() < 2 { return false; }
    let effect_sets: Vec<HashSet<String>> = exprs.iter()
        .map(|e| expr_effects(e, module, resolved_imports))
        .collect();
    for i in 0..effect_sets.len() {
        for j in (i + 1)..effect_sets.len() {
            if !effect_sets[i].is_disjoint(&effect_sets[j]) {
                return false;
            }
        }
    }
    true
}

/// Does `expr` contain a `Call` to a user-defined function (local or imported)?
/// This is the threshold check (PE-4): pure expressions are not worth
/// spawning threads for.
pub fn contains_user_call(
    expr: &Expr,
    module: &Module,
    resolved_imports: &HashMap<String, Definition>,
) -> bool {
    match expr {
        Expr::Call { fn_, args } => {
            if module.symbols.iter().any(|(n, _)| n == fn_) {
                return true;
            }
            // Imported symbols count as user calls (V3-1).
            if resolved_imports.contains_key(fn_.as_str()) {
                return true;
            }
            args.iter().any(|a| contains_user_call(a, module, resolved_imports))
        }
        Expr::Bind { expr: e, body, .. } => {
            contains_user_call(e, module, resolved_imports)
                || contains_user_call(body, module, resolved_imports)
        }
        Expr::Seq { steps } => {
            steps.iter().any(|s| contains_user_call(s, module, resolved_imports))
        }
        Expr::Concat { parts } => {
            parts.iter().any(|p| contains_user_call(p, module, resolved_imports))
        }
        Expr::Believe { subject, arms, otherwise } => {
            contains_user_call(subject, module, resolved_imports)
                || arms.iter().any(|(c, v)| {
                    contains_user_call(c, module, resolved_imports)
                        || contains_user_call(v, module, resolved_imports)
                })
                || contains_user_call(otherwise, module, resolved_imports)
        }
        Expr::Attr { target, .. } => contains_user_call(target, module, resolved_imports),
        Expr::If { cond, then_, else_ } => {
            contains_user_call(cond, module, resolved_imports)
                || contains_user_call(then_, module, resolved_imports)
                || contains_user_call(else_, module, resolved_imports)
        }
        _ => false,
    }
}

/// Should we parallelize this set of expressions?
///
/// Yes iff:
/// 1. There are at least 2 expressions.
/// 2. **All** expressions are direct `Call` nodes to user-defined functions
///    (local or imported). This is the key threshold (PE-4):
///    `list(f(1), f(2), f(3))` qualifies; `walk(s, add(i, 1), step(s, i, d))`
///    does not (mixed args). Mixed-arg calls are typically recursive patterns
///    where thread-spawn overhead would dominate.
/// 3. All pairs have disjoint effect sets.
pub fn should_parallelize(
    exprs: &[&Expr],
    module: &Module,
    resolved_imports: &HashMap<String, Definition>,
) -> bool {
    if exprs.len() < 2 { return false; }
    // All args must be direct user calls (local or imported) — no mixed args.
    if !exprs.iter().all(|e| is_direct_user_call(e, module, resolved_imports)) {
        return false;
    }
    all_disjoint(exprs, module, resolved_imports)
}

/// Is `expr` a direct `Call` node (not nested) to a user-defined function
/// (local or imported)?
fn is_direct_user_call(
    expr: &Expr,
    module: &Module,
    resolved_imports: &HashMap<String, Definition>,
) -> bool {
    match expr {
        Expr::Call { fn_, .. } => {
            module.symbols.iter().any(|(n, _)| n == fn_)
                || resolved_imports.contains_key(fn_.as_str())
        }
        _ => false,
    }
}

// ---------------------------------------------------------------------------
// Parallel evaluation result
// ---------------------------------------------------------------------------

/// Result of evaluating one parallel branch.
pub struct BranchResult {
    pub value: Result<Value, Error>,
    pub trace: EffectTrace,
}

/// Evaluate a set of expressions in parallel, each with its own interpreter.
///
/// Returns results in **declaration order** (PE-1: indexed collection).
/// Each branch gets its own `EffectTrace`; the caller merges them in order.
///
/// `make_interp` is a factory that creates a fresh interpreter for each
/// branch, initialized with the parent's current depth (PE-3).
pub fn eval_parallel<F, G>(
    exprs: &[&Expr],
    make_interp: F,
    eval_fn: G,
) -> Vec<BranchResult>
where
    F: Fn() -> (crate::interpreter::Interpreter<'static>, EffectTrace) + Sync,
    G: Fn(&Expr, &mut crate::interpreter::Interpreter<'static>, &mut EffectTrace) -> Result<Value, Error> + Sync,
{
    // Collect with index to preserve declaration order (PE-1).
    let indexed: Vec<(usize, &&Expr)> = exprs.iter().enumerate().collect();
    let mut results: Vec<(usize, BranchResult)> = indexed
        .par_iter()
        .map(|(idx, expr)| {
            let (mut interp, mut trace) = make_interp();
            let value = eval_fn(expr, &mut interp, &mut trace);
            (*idx, BranchResult { value, trace })
        })
        .collect();
    // Sort by index to guarantee declaration order.
    results.sort_by_key(|(idx, _)| *idx);
    results.into_iter().map(|(_, r)| r).collect()
}

/// Merge a sequence of `EffectTrace`s into a parent trace, in order.
pub fn merge_traces(parent: &mut EffectTrace, branches: Vec<EffectTrace>) {
    for branch in branches {
        parent.stdout.extend(branch.stdout);
        parent.clock_reads.extend(branch.clock_reads);
        parent.model_calls.extend(branch.model_calls);
    }
}
