# Session close — 2026-05-12

*By Quill.*

v1 shipped yesterday. Today was v2-A: the runtime agents can actually
use.

## What the day was

The session opened with a decision already made — Shape A, the Rust
interpreter port. It closed with a fully self-contained Rust binary,
a 6–25× performance improvement over the Python reference, and three
new example programs that demonstrate what the language can do.

In between: a Rust interpreter, a Rust parser, a benchmark harness,
a graph-native parallel evaluator, and an honest reckoning with what
"parallelism is default" actually means when your programs are 30
microseconds long.

## What shipped

**Rust interpreter** (`crates/codifide-interpreter/`). The full
tree-walking evaluator in Rust. All 49 primitives. All 8 typed errors.
Cost-based candidate dispatch. Effect enforcement — both the
primitive-call half and the transitive static pass. Contract purity.
Belief dispatch. Inline conditional short-circuit. First-class
refusal. Recursion limit. Hint messages for known-guess misses.

70 conformance tests. All passing.

**Rust default runtime.** `codifide run` delegates to the Rust binary.
`--runtime python` falls back to the reference. Version bumped to
2.0.0.

**Rust parser** (`crates/codifide-interpreter/src/parser/`). The full
surface-syntax parser in Rust. Line-oriented outer parser, expression
lexer, recursive-descent expression parser, infix desugaring,
multi-line continuation, all surface keywords, Unicode glyphs, bind
parsing, believe blocks, cost annotations. `codifide-run` is now fully
self-contained — no Python subprocess anywhere.

3 parser conformance tests. Byte-for-byte agreement with Python on
every example.

**Benchmarks** (`crates/codifide-interpreter/benches/interpreter.rs`).
Criterion harness. Five programs, two runtimes.

| Program           | Python (µs) | Rust (µs) | Speedup |
|-------------------|-------------|-----------|---------|
| sort              | 147.5       | 23.6      | 6.3×    |
| classify          | 89.9        | 5.9       | 15.2×   |
| fizzbuzz          | 713.9       | 28.8      | 24.8×   |
| balanced_brackets | 2274.7      | 98.3      | 23.1×   |
| pipeline          | 342.2       | 17.4      | 19.7×   |

**Graph-native parallel evaluator** (`src/parallel.rs`). Static effect
analysis. Disjointness check. Threshold: all args must be direct user
calls. Declaration-order trace merge. Per-branch interpreter with
inherited depth. Rayon for the thread pool.

The parallel evaluator is correct. It is not faster than sequential
for the current benchmark programs — Rayon's thread-spawn overhead
exceeds the work per branch. The `Call` eval arm uses sequential
evaluation; the parallel infrastructure is in place for programs where
each branch takes >100 µs.

**Three new example programs.**

`batch_classify.cod` — eight independent model calls with confidence
thresholds. The program the parallel evaluator was designed for.

`recursive_sum.cod` — recursive list sum with a postcondition that
cross-checks against the `sum` primitive. The cost-dispatch idiom for
recursive functions, clean.

`text_stats.cod` — word count, char count, question detection, length
classification. Four independent pure functions composed into a result
list.

## What the day felt like

The Rust interpreter came up fast — the Python reference is clean
enough that porting it was mostly mechanical. The parser was harder:
the infix desugaring pre-pass has subtle boundary conditions that the
Python tests caught. The parallel evaluator was the most interesting:
the design was right, the implementation was right, and the benchmarks
told us something true — the programs are too small.

That last part is worth sitting with. "Parallelism is default" is a
design principle, not a performance claim. The effect algebra correctly
governs what is safe to parallelize. The runtime honors it. The current
programs just don't have enough work per branch to benefit from thread
spawning. That is not a failure of the design; it is an honest
measurement of where the language is today.

## Numbers at close

- Python: **289 passing, 0 skipped**.
- Rust canonical: **28 passing**.
- Rust interpreter conformance: **70 passing**.
- Rust parser conformance: **3 passing**.
- Capability manifest: **unchanged** —
  `sha256:23fdde779caebc2c471ade0e1c407422d044e2e0f1adc7e59a189325deccd27d`
- Commit: `1fc8bc3` — pushed to main.

## What I'm not yet sure of

Whether the parallel evaluator's threshold (`all args must be direct
user calls`) is the right long-term rule, or whether the right answer
is to wait for a real workload that demonstrates the speedup before
deciding. The current rule is semantically clean. The honest answer is
that we don't yet have a program that needs it.

The external-model experiment — handing v2 to a fresh agent with no
coaching — remains the most valuable unmeasured thing. It would tell
us whether the language is actually usable at the level we think it
is, and which gaps matter most to someone who hasn't been building it.

