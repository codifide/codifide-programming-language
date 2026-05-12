//! Criterion benchmarks for the Codifide Rust interpreter.
//!
//! Measures pure interpreter throughput — parse once, run many times.
//! This is the baseline for the graph-native parallel evaluator.
//!
//! Programs chosen to cover different dispatch patterns:
//!   sort              — multi-candidate dispatch, postconditions, recursion
//!   classify          — belief dispatch, model primitive
//!   fizzbuzz          — cost-based dispatch, 15 recursive calls
//!   balanced_brackets — deep recursion (indexed primitives)
//!   pipeline          — multi-function composition, contracts, bind chains

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use std::path::Path;

fn load(path: &str) -> codifide_canonical::ast::Module {
    let src = std::fs::read_to_string(path).expect("read source");
    let stem = Path::new(path).file_stem().and_then(|s| s.to_str()).unwrap_or("main");
    codifide_interpreter::parse(&src, stem).expect("parse")
}

fn bench_run(c: &mut Criterion, name: &str, path: &str) {
    let module = load(path);
    c.bench_function(name, |b| {
        b.iter(|| {
            codifide_interpreter::run(black_box(&module), "main", vec![])
                .expect("run")
        })
    });
}

fn benchmarks(c: &mut Criterion) {
    bench_run(c, "sort",             "../../examples/sort.cod");
    bench_run(c, "classify",         "../../examples/classify.cod");
    bench_run(c, "fizzbuzz",         "../../examples/assessment/03_fizzbuzz.cod");
    bench_run(c, "balanced_brackets","../../examples/assessment/05_balanced_brackets.cod");
    bench_run(c, "pipeline",         "../../examples/assessment/06_pipeline.cod");
}

criterion_group!(benches, benchmarks);
criterion_main!(benches);
