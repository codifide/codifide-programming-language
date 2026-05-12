# Benchmarks — Rust interpreter baseline (2026-05-12)

*By Quill.*

The v2-A scope included "benchmarks as first-class citizens." This is
the first measurement. Five programs, two runtimes, Criterion on the
Rust side and `time.perf_counter` on the Python side.

## Results

| Program           | Python (µs) | Rust (µs) | Speedup |
|-------------------|-------------|-----------|---------|
| sort              | 147.5       | 23.6      | 6.3×    |
| classify          | 89.9        | 5.9       | 15.2×   |
| fizzbuzz          | 713.9       | 28.8      | 24.8×   |
| balanced_brackets | 2274.7      | 98.3      | 23.1×   |
| pipeline          | 342.2       | 17.4      | 19.7×   |

Python numbers: median of 200 runs, interpreter only (module parsed
once, `run()` called in a loop). Rust numbers: Criterion median over
100 samples, same methodology — parse once, run in a tight loop.

## What the numbers mean

The range is 6–25×. The lower end (sort, 6.3×) is dominated by
`host_sorted` — a single call to the host's sort primitive — so the
interpreter overhead is a small fraction of total work. The upper end
(fizzbuzz, 24.8×; balanced_brackets, 23.1×) is pure interpreter work:
many candidate dispatches, guard evaluations, and recursive calls with
no expensive host primitives. That's where the Rust tree-walker's
advantage is largest.

The v2-A proposal said "expected 10-100× speedup on realistic
programs." The measured range is 6–25×. The lower bound is real
(host-primitive-heavy programs are bounded by the primitive, not the
interpreter). The upper bound is real for dispatch-heavy programs.

## What the parallel evaluator can add

The sequential tree-walker is already 6–25× faster than Python. The
parallel evaluator targets programs with independent branches — the
`fizzbuzz` main body calls `fizzbuzz_one` 15 times with no data
dependencies between calls. Those 15 calls are currently sequential;
a graph-native evaluator runs them concurrently. The `balanced_brackets`
recursive walk is sequential by nature (each step depends on the
previous depth). The parallel evaluator helps the former, not the
latter.

## Benchmark infrastructure

`crates/codifide-interpreter/benches/interpreter.rs` — Criterion
harness. Run with:

```
cargo bench -p codifide-interpreter
```

HTML reports land in `target/criterion/`. The five programs are the
regression fixtures; a future change that regresses any of them by
more than 10% is a performance bug.

## What I'm not yet sure of

Whether the `fizzbuzz` and `pipeline` programs are representative of
real agent workloads. They are the most dispatch-heavy programs in the
corpus; a real agent program might be more like `classify` (one model
call, one believe dispatch) or `balanced_brackets` (deep recursion).
The parallel evaluator's benefit depends heavily on which pattern
dominates in practice.

