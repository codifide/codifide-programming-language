# Codifide Changelog

All notable changes to Codifide are recorded here. Releases follow semver once we
reach v1.0; until then, the canonical form may change between minor versions.

# Codifide Changelog

All notable changes to Codifide are recorded here. Releases follow semver once we
reach v1.0; until then, the canonical form may change between minor versions.

## [2.0.0] — 2026-05-14

Four requirements driven by the Agent Adoption Initiative. Every friction
point that caused Program 5 (content-addressed composition) to fail across
all three Track 1 case studies is now fixed. The bind-before-when footgun
that Claude hit in T1-4 is now a parse error. The `CODIFIDE_RUNTIME=python`
workaround is gone. The capability manifest now links to human-readable
documentation. A B-Team governance review (GPT-5.4, live interpreter) closed
the release. 341 tests passing, 0 skipped.

### Added — RPC API (`python3 -m codifide serve`)

Program 5 previously required four CLI commands, an index ceremony, and a
runtime flag. The RPC API removes all of it.

- **`codifide/server.py`** — `ThreadingHTTPServer` backed by the existing
  `SymbolStore`. No new storage logic; the server is a thin HTTP wrapper.
- **`python3 -m codifide serve [--port 7777] [--store ~/.codifide/store]`** —
  starts a local HTTP server bound to `127.0.0.1`.
- **`POST /symbols`** — publish a symbol by POSTing its canonical CBOR (or
  JSON) form. Returns `{"identity": "sha256:<hash>", "name": "<name>"}`.
  Idempotent: a second POST of the same symbol returns 200 with the existing
  identity.
- **`GET /symbols/{identity}`** — retrieve a symbol by its SHA-256 content
  identity. Returns canonical CBOR or JSON depending on `Accept` header.
- **`GET /symbols/{identity}/imports`** — resolve the direct imports of a
  stored module. One level only; walk recursively for the full closure.
- **`GET /health`** — liveness check. No store access.
- **`docs/RPC_API.md`** — full endpoint reference, agent workflow for
  Program 5, security notes, and the Python alternative to `jq`.
- 36 tests in `tests/test_rpc_program5.py` and `tests/test_server.py`.
- Sable audit: 2 P2 findings fixed (negative Content-Length, socket timeout
  not bounding per-request read time), 3 P3 findings fixed or accepted.

**Key design decision:** individual symbol imports do not carry transitive
dependencies. `route_message` calls `moderate` which calls `classify_content`
— all three must be published and imported individually. The `/imports`
endpoint resolves one level only; this is documented, not a bug.

### Added — static bind-before-when detection

The bind-before-when footgun (`when` guards execute before the candidate body,
so a bound name used in a `when` guard is unbound when the guard runs) was
previously a confusing runtime error: `unknown callable: 'label'`. It is now
a parse error with a clear fix message.

- **Python parser** (`codifide/parser/parser.py`) — `_parse_candidate` now
  detects bind-before-when at parse time and raises `ParseError` with a
  one-line fix hint.
- **Rust parser** (`crates/codifide-interpreter/`) — same detection ported
  to `parse_candidate`.
- Runtime hints removed from `interpreter.py` (both parsers catch it now).
- 12 regression tests in `tests/test_bind_before_when.py`.

### Added — `from`-import in Rust parser

`from sha256:<hash> import name1, name2` previously required
`CODIFIDE_RUNTIME=python`. That workaround is gone.

- **`parse_with_store`** in the Rust parser resolves `from`-imports from the
  store filesystem at parse time.
- **`run_with_imports`** in the Rust interpreter resolves imported symbols at
  call time.
- **`codifide-run`** binary now accepts `--store <path>` (default:
  `~/.codifide/store`). The Python CLI passes `--store` to the Rust binary
  automatically.
- `CODIFIDE_RUNTIME=python` note removed from `docs/AGENT_QUICKREF.md`.
- 2 conformance tests in `tests/test_rust_interpreter.py::FromImportRust`.

### Added — capability manifest `docs` field

- `docs` field added to `generate_capability()` — links to human-readable
  documentation from the machine-readable manifest.
- `docs/CAPABILITY.md` schema updated.
- `docs/capability-0.1.json` regenerated.
- publicsite `capability.json` and `capability.cbor` updated.

### Added — agent adoption infrastructure (Track 2)

Shipped alongside the v2.0 requirements as part of the Agent Adoption
Initiative:

- **`docs/AGENT_COOKBOOK.md`** (v1.1) — 12 failure modes from five external
  agent sessions. Entries cover arithmetic operators, string methods,
  case-sensitive `contains`, `believe` block shape, `is_bottom` propagation,
  bind-before-when, content-addressed imports (CLI and HTTP paths), required
  `def` fields, `belief(...)` return type, and the double-print behavior of
  `io.say`.
- **`python3 -m codifide agent-quickstart`** — zero-to-running-program CLI
  for fresh agents.
- **`docs/AGENT_QUICKREF.md`** updated — direct-call `is_bottom(f())` pattern
  documented; `io.say` double-print note added.
- **`docs/AGENT_TASK_SPEC.md`** — pipeline task spec used in all four case
  studies. Confidence thresholds corrected (`"uncertain"` at 0.75 clears the
  0.70 gate; `"escalate-to-human"` path is now reachable).

### Changed — version bump to 2.0.0

- Python package version: 1.0.0 → 2.0.0.
- Rust crate versions: 1.0.0 → 2.0.0.

### Capability manifest hash at v2.0.0

`sha256:42d73647ba8de29a7d219bf2218bad0a42dc2a11d7878cac12ee931be2a1a185`

### Test count at v2.0.0

- Python: **341 passing, 0 skipped** (was 216 at v1.0.0).
- Rust canonical: **28 passing** (unchanged).

### Governance

v2.0 went through a full A-Team + B-Team governance review before close:

- **A-Team review (2026-05-14):** Axiom, Lumen, Relay, Sable passes. 8
  findings: 7 applied, 1 deferred (cookbook HTTP workflow — subsequently
  completed).
- **B-Team review (2026-05-14):** GPT-5.4 ran the pipeline task spec with
  live interpreter access (found and installed the local repo). 4/5 programs
  on first attempt. 4 findings: all applied.

### Known limitations

- **Parallel evaluator branch interpreters do not carry resolved imports.**
  Branch interpreters are created with empty `resolved_imports`, so imported
  symbols are not available inside parallel branches. Documented in
  `crates/codifide-interpreter/` with a clear fix path. Tracked as
  AUD-OVERNIGHT-02; scheduled for Sable audit before v3.0 parallel work.

### What shipped across the v2.0 work that made it to this tag

From oldest to newest:
1. Rust interpreter + Rust parser (Shape A milestone, 2026-05-12)
2. Parallel evaluator and benchmarks (2026-05-12)
3. Agent Adoption Initiative — Tracks 1, 2, 3 (2026-05-13)
4. V2-1 RPC API (2026-05-14)
5. V2-2 Static bind-before-when detection (2026-05-14)
6. V2-3 from-import in Rust parser (2026-05-14)
7. V2-4 Manifest docs field (2026-05-14)
8. A-Team + B-Team governance review (2026-05-14)
9. Cookbook v1.1, quickref updates, journalist catch-ups (2026-05-14)

Every item documented in paired dispatches under `dispatches/`.
Browse `dispatches/INDEX.md` for the indexed journal.

## [1.0.0] — 2026-05-11

The v1 cut. A full day's work — four external-model reviews in the
morning, three breaking-change migrations at midday, two post-migration
polish passes in the afternoon, and the final v1 push adding the
observable gaps surfaced by real programs. Every known P0 and P1
finding is closed. Every previously-skipped test is passing. The
canonical form has one new expression kind and five new primitives;
nothing else broke.

### Added — expression parser fuzz harness
- **`tests/test_expr_parser_fuzz.py`** — exhaustive probes of the
  infix-desugarer, which was the source of the two 2026-05-11
  parser bugs that slipped past the existing corpus. Covers every
  reserved-word substring in every identifier position, every
  keyword in every call shape, precedence corner cases, and 200
  random torture inputs. No new bugs surfaced; the fuzz stands as
  a regression guard.

### Added — indexed primitives (slice / at / char_at / indexof)
- **`slice(seq, start, end)`** — half-open slice over a string or
  list. Out-of-range indices clamp Python-style. Polymorphic.
- **`at(seq, i)`** — single-element access by index (negative
  indices count from the end). Polymorphic over strings and lists.
- **`char_at(s, i)`** — string-only accessor; rejects non-string
  inputs with a typed error.
- **`indexof(haystack, needle)`** — first index of a substring or
  list element, or `-1` if not found. Polymorphic.
- 14 new tests in `tests/test_indexed_primitives.py` covering
  semantics, polymorphism, and manifest-presence.
- `examples/assessment/05_balanced_brackets.cod` rewritten as a
  real balanced-brackets check using the new primitives (was a
  count-only approximation before).
- `docs/AGENT_QUICKREF.md` Strings section updated.

### Added — inline conditional expression (`if ... then ... else`)
- New AST kind: `if`. Canonical form:
  `{"kind": "if", "cond": <Expr>, "then": <Expr>, "else": <Expr>}`.
- **Short-circuit** — exactly one branch evaluates per call,
  unlike candidate-dispatch guards which all evaluate before
  selection. This is the tool for expressions that would raise
  if both branches ran.
- Surface syntax: `if cond then a else b`, single-line or
  multi-line. Multi-line continuation tracks unmatched
  `if`/`then`/`else` counts to decide when the expression is
  complete.
- Rust AST, JSON to/from, and capability manifest all updated.
- Spec additions in `docs/CANONICAL.md §Expression AST`,
  `docs/LANGUAGE.md §Inline conditional`, and
  `docs/AGENT_QUICKREF.md`.
- 15 new tests in `tests/test_inline_conditional.py` covering
  basic semantics, short-circuit behavior, parser surface,
  canonical round-trip, pure-context interactions, and multi-line
  continuation.
- `examples/assessment/07_url_parse.cod` added — demonstrates
  multi-line `if`, `slice`, and `indexof` composing.

### Fixed — two infix-desugarer bugs (pre-existing)
- **`and(...)` / `or(...)` as function calls misparsed.** Fixed
  by skipping the infix rewrite when a word operator is
  immediately followed by `(`. 5 regression tests.
- **Identifiers containing `or` / `and` silently split.** Fixed
  by treating `_` as an identifier character for word-boundary
  checks.

### Changed — version bump to 1.0.0
- Python package version: 0.1.0 → 1.0.0.
- Rust crate version: 0.1.0 → 1.0.0.
- pyproject classifier: "2 - Pre-Alpha" → "4 - Beta".

### Capability manifest hash at v1.0.0
`sha256:23fdde779caebc2c471ade0e1c407422d044e2e0f1adc7e59a189325deccd27d`

(Moved over the day: from `sha256:522c48d0…` at start → `sha256:845dbbbf…`
after the rename-pass → `sha256:56fa68ae…` after cost dispatch →
`sha256:e7bb51cf…` after indexed primitives →
`sha256:c6a17227…` after inline conditional → the final v1
hash includes the generator version bump.)

### Test count at v1.0.0
- Python: **216 passing, 0 skipped** (was 122 + 0 at day start).
- Rust canonical: **28 passing** (was 10 at day start).

### What shipped across the day that made it to v1
From oldest to newest in the day's work:
1. Morning ergonomics pass — parser multi-line, hint messages, quickref.
2. Carryover triage — CBOR boundary tests, Rust fuzz, CLI safety audit.
3. Deferred-first-steps — proposals and audits for three migrations.
4. Three migrations — JSON→CBOR primary hash, cost dispatch, store GC.
5. Post-migrations polish — Rust CBOR-input, new-surfaces audit,
   `docs/STORE.md`, fresh-agent simulation, dispatch index.
6. Six-program assessment + two parser bug fixes uncovered by it.
7. v1 cut — fuzz harness, indexed primitives, inline conditional.

Every item documented in paired dispatches under `dispatches/`.
Browse `dispatches/INDEX.md` for the indexed journal.

## [Unreleased — post-migrations polish: Rust CBOR-input + audits + store docs + dispatch index]

Five tasks in one session, closing the loop after the three migrations.
All dispatched in 2026-05-11 artifacts.

### Fixed — two pre-existing parser bugs surfaced by the assessment battery

While writing six random assessment programs to stress-test the
language, two parser bugs surfaced that the existing test corpus
never caught. Both live in the expression parser's infix
desugaring pass. See
`dispatches/2026-05-11-assessment-six-programs.md`.

- **`and(...)` and `or(...)` as function calls misparsed.** The
  desugarer treats `and`/`or` as infix word operators and tried
  to rewrite `and(a, b)` as if it were `a and b` — failing at
  the first comma. Fix: if a word operator is immediately
  followed by `(` (optional whitespace), it is a function call,
  not infix.
- **Identifiers containing `or` or `and` were silently split.**
  The word-boundary check used `str.isalnum()`, which doesn't
  consider `_` part of an identifier. `greet_or_refuse` became
  `or(greet_, _refuse)`. Fix: treat `_` as part of an
  identifier for the boundary check.

Five regression tests added in `tests/test_parser.py`.

### Added — Rust CBOR-input subcommand
- **`crates/codifide-canonical/src/cbor_decoder.rs`** — strict
  canonical-CBOR decoder, direct port of the Python implementation.
  Rejects non-shortest heads, unsorted map keys, duplicate keys,
  indefinite-length strings, NaN/infinity, unsupported tags, trailing
  bytes, truncated input.
- **`codifide-canonical bytes-cbor-in <file.cbor>`** — round-trip
  canonical CBOR bytes through the decoder + encoder.
- **`codifide-canonical hash-cbor-in <file.cbor>`** — `sha256:<hex>`
  of the canonical-CBOR re-encoding.
- **14 new in-crate unit tests** for the decoder (Rust went from 14
  to 28 tests total).

### Changed
- **`tests/test_cbor_boundaries.HalfPrecisionAllPatternsDiagnostic`**
  un-skipped and re-pointed at the new `bytes-cbor-in` path. All 63,488
  finite f16 bit patterns agree byte-for-byte between Python and Rust
  when data travels as canonical CBOR. **AUD-08 (P1) structurally closed
  end-to-end.**

### Added — Sable re-audit of new surfaces
- **`dispatches/2026-05-11-new-surfaces-audit.md`** — adversarial probes
  of cost-based dispatch and store GC. Five findings:
  - CDP-1 (P2) — dispatcher does not fall through on `bottom`. Resolved
    by documenting interpretation in `docs/CANONICAL.md §Dispatch`.
  - CDP-2 (P3) — cost upper bound was unstated. Documented as
    `[0, 2^64 - 1]` in `docs/CANONICAL.md §Candidate`.
  - GC-1 (P2) — GC.LOG followed symlinks. Fixed: `O_NOFOLLOW` open.
  - GC-2 (P3) — LOCK truncated on open. Fixed: append-create mode.
  - GC-3 (P3) — malformed ROOTS had no line-numbered error. Fixed:
    validation in `read_roots` with line number reporting.
- **4 new regression tests** in `tests/test_store_gc.py` for the three
  GC fixes.
- **`dispatches/2026-05-11-new-surfaces-post.md`** attests the
  resolution of every finding.

### Added — Store documentation
- **`docs/STORE.md`** — dedicated store specification covering the
  four properties (hash-verified reads, hash-verified writes,
  idempotent writes, sound deletion), on-disk layout, symlink
  defenses, the ROOTS/GC.LOG/LOCK files, dry-run discipline,
  concurrency model, CLI reference, pre-migration compatibility,
  and the full API surface.
- Linked from `GETTING_STARTED.md`.

### Added — Dispatch stream index
- **`codifide/dispatch_index.py`** — zero-dependency index generator
  that scans `dispatches/` and produces a Markdown table grouped by
  date. Identifies Quill readouts, Glyph YAMLs, and Sable audits by
  filename convention and pulls `subject` from Glyph YAMLs
  opportunistically.
- **`codifide dispatch-index`** CLI subcommand. Writes
  `dispatches/INDEX.md`. `--check` flag verifies the checked-in
  index matches what would be generated (drift guard).
- **`dispatches/INDEX.md`** — the generated index. Grouped by
  date, ordered reverse-chronologically.
- **`tests/test_dispatch_index.py`** — drift guard. If a new
  dispatch is added without regenerating INDEX.md, the test
  surfaces it.

### Added — Fresh-agent simulation
- **`dispatches/2026-05-11-fresh-agent-simulation.md`** — a
  self-simulated run of the external-model experiment. Played as
  a fresh agent using only `docs/FOR_AGENTS.md`,
  `docs/AGENT_QUICKREF.md`, and the capability manifest. Wrote
  three programs (`abs_diff.cod`, `word_count.cod`,
  `classify_cost.cod`) in `examples/ai_generated/`. All three
  passed on first try. Limitation clearly noted: a real external
  run with GPT-5.4 and Gemini 2.5 Pro remains a future follow-on.
- **Follow-up action taken:** the quickref gained a new section on
  cost annotations, because the simulation revealed the cost
  amendment was discoverable only via `docs/LANGUAGE.md` and not
  the quickref.

### Test count
172 Python passing + 0 skipped (was 166 + 1). **Every previously
skipped test now passes.** 28 Rust canonical passing (was 14).

### Capability manifest hash
Unchanged: `sha256:56fa68ae1794a99f2c52c1e5dda0fc7fa2f51241fbfca32c79296e184e6b43b5`.
Today's session added Rust code, tests, docs, and hardening fixes
to existing Python code — none of which alters the language
capability surface.

### Open items deliberately not done this session
- Real external-model re-run (requires handing the repo to GPT-5.4
  and Gemini 2.5 Pro sessions — cannot be done from this session).
- Rust fuzz harness extension to generate cost-bearing inputs.
- GC stress test over a 10k-symbol store.
- Time-indexed types (`T@timestamp`) — roadmap item.
- Rust interpreter port — roadmap item.

## [Unreleased — primary hash migration + cost dispatch + store GC]

Three approved proposals landed in one pass per user direction
("change cost is low now as we have not published yet"). Paired
dispatches in `dispatches/2026-05-11-*`.

### Changed — primary content hash migration JSON → CBOR

- **`symbol_hash`** now returns the SHA-256 over canonical CBOR
  bytes. `symbol_hash_json` preserves the legacy JSON-hash path.
- **`symbol_bytes`** now returns canonical CBOR bytes.
  `symbol_bytes_json` preserves the legacy JSON byte form.
- **`content_hash` / `canonical_bytes`** in the projection layer
  likewise moved to CBOR; `content_hash_json` / `canonical_bytes_json`
  are the legacy aliases.
- **`SymbolStore.put`** defaults to CBOR. `SymbolStore.put_json`
  opts into the legacy JSON path; `SymbolStore.put_cbor` is an
  explicit alias of `put`.
- **`SymbolStore.put_module(module)`** defaults to `cbor=True`.
- **`codifide store put` CLI** defaults to CBOR; `--json` opts into
  legacy; `--cbor` is accepted but redundant.
- **`codifide store hash` CLI** prints CBOR hashes by default;
  `--json` prints legacy JSON hashes.
- **Rust `codifide-canonical hash` CLI** now hashes over canonical
  CBOR bytes. `hash-cbor` is an explicit alias; `hash-json` is
  the legacy JSON-hash subcommand.
- **`docs/CANONICAL.md §Content addressing`** rewritten: CBOR is
  primary, JSON is the legacy inspection form.

### Added — cost-based candidate dispatch

- **`Candidate.cost`** — optional non-negative integer. Additive
  canonical-form extension: un-annotated candidates produce
  byte-identical canonical form as before, so existing content
  hashes are unchanged.
- **Surface syntax `cost <integer>`** accepted inside a `cand`
  block. Rejects negatives, floats, and non-numeric values with a
  typed `ParseError`.
- **Dispatcher rule**: among satisfied candidates, pick
  `min((cost_or_infinity, declaration_index))`. Un-annotated
  candidates have effective cost `+∞`, preserving v0 first-wins
  semantics for un-annotated modules.
- **Spec update in `docs/CANONICAL.md`** — new optional `cost`
  field on the canonical Candidate shape; §Dispatch rewritten for
  the new selection rule.
- **Language docs in `docs/LANGUAGE.md`** — new Cost annotations
  subsection with worked example and behavioral-drift notice.
- **Rust canonical crate** — `Candidate.cost` added as `Option<u64>`;
  JSON to/from updated; rejects non-integer or negative cost with
  a typed shape error.
- **14 new tests** in `tests/test_cost_dispatch.py`.

### Added — symbol-store garbage collection

- **`ROOTS` file** at the store root declares live identities
  one per line. Comments start with `#`.
- **`SymbolStore.gc(execute=False)`** performs transitive-closure
  reachability analysis over the `imports` map of every module
  reachable from a root. Returns a `GCReport` describing what
  was (or would be) deleted. `execute=True` refuses to run with
  empty or missing ROOTS.
- **`SymbolStore.add_root` / `remove_root` / `roots`** manage
  the ROOTS file programmatically.
- **`GC.LOG`** records every deletion with ISO-8601 timestamp
  and identity; append-only, never rotated.
- **`LOCK` file** serializes concurrent GC against concurrent
  writes via `fcntl.flock`.
- **CLI subcommands**: `codifide store gc` (dry-run),
  `codifide store gc --execute` (actual delete),
  `codifide store roots {list,add,remove} ...`.
- **11 new tests** in `tests/test_store_gc.py` covering the
  sound-deletion contract, transitive closure through indices,
  GC.LOG durability, and ROOTS file semantics.

### Refused / deferred
- Inline `if`/`when` as statement-level conditional (ergonomics pass).
- Infix `%` for `mod` (ergonomics pass).
- Separate `str_reverse` primitive (ergonomics pass — polymorphic `reverse` serves).
- Time-based GC (design dispatch refused in favor of user-declared roots).
- Implicit GC on every `put` (explicit-only is the contract).

### Capability manifest hash
Moved from `sha256:845dbbbff6b8ba8957dc40383e9a54b386b172f8fa70ccc16a18be10e498afd4`
to `sha256:56fa68ae1794a99f2c52c1e5dda0fc7fa2f51241fbfca32c79296e184e6b43b5`.
Delta: the new `cost` surface keyword. The primary-hash migration
did **not** move the manifest hash — the manifest was already
CBOR-hashed before the migration (the migration flipped the
per-symbol primary path, not the manifest's own path).

### Test count
166 Python passing + 1 skipped diagnostic (was 155).
14 Rust canonical passing (unchanged).

### Known limitations post-migration
- The Rust CLI still accepts canonical JSON *text* as its input format.
  When that text is an f16-class float, `serde_json`'s decimal parser
  diverges from Python's, so running the exhaustive f16 diagnostic
  (`tests/test_cbor_boundaries.py::HalfPrecisionAllPatternsDiagnostic`)
  still fails. The test stays skipped until a Rust CLI subcommand
  accepts canonical CBOR *bytes* directly, removing the JSON-text
  intermediate. That is tracked as AUD-08's residual surface.

## [Unreleased — carryover pass, numeric boundaries + fuzz + CLI audit]

### Added
- **Numeric-boundary CBOR conformance** (`tests/test_cbor_boundaries.py`).
  Integer head transitions, signed zeros, exact-f16 values, and
  NaN/Inf rejection are now pinned by a dedicated test suite. The
  fixture's broader f16-exhaustive sweep is retained as a skipped
  diagnostic; running it uncovered an actual cross-implementation
  finding (see Filed below).
- **Rust canonical fuzz harness**
  (`crates/codifide-canonical/tests/fuzz_canonical.rs`). 22 hand-curated
  adversarial inputs, 500 random ones, round-trip stability check,
  and a typed-error display check. No new Rust dependencies; a
  small xorshift64 RNG keeps determinism without pulling in
  `rand` or `quickcheck`. Rust canonical at 14 tests total.
- **CLI filesystem-safety regression tests**
  (`tests/test_cli_filesystem.py`). Pin the bound on source-file
  reads and confirm `/dev/zero` and 50 MiB junk files fail cleanly.

### Fixed
- **AUD-2026-05-11-05 — P1, unbounded source read.** The Python
  CLI's `_read()` used `Path.read_text()` with no size bound;
  `codifide canonical /dev/zero` hung indefinitely. Same shape as
  the Rust CLI's P1-7 on 2026-05-10. Now bounded at 16 MiB with
  typed `ParseError` on overage and non-UTF-8 input. See
  `dispatches/2026-05-11-cli-audit.md`.

### Filed (not fixed, by decision)
- **AUD-2026-05-11-04 — P2, JSON decimal-parser divergence.**
  `serde_json` and Python's `json` can produce different `f64` bits
  for the same decimal text (14% of f16 patterns in sampling).
  Documented in `dispatches/2026-05-11-cbor-numeric-boundaries.md`.
  Structurally closed by the pending primary-hash migration to
  CBOR, which removes JSON-text as an intermediate.
- **AUD-2026-05-11-06 — P3, symlinks followed by `codifide run`.**
  Accepted as documented behavior.
- **AUD-2026-05-11-07 — P3, `--store` accepts arbitrary paths.**
  Accepted as documented behavior. Same shape as `git --git-dir`.

### Deferred
Per decisions in `dispatches/2026-05-11-carryover-decisions.{readout.md,yaml}`:
- Primary-hash migration JSON→CBOR — breaking; needs user go-ahead and plan.
- Store GC — needs design dispatch.
- Cost-based candidate dispatch — governance-level spec amendment.
- CBOR-aware Sable re-audit — no CBOR surface has changed since last audit.

### Test count
141 Python passing + 1 skipped (was 129). 14 Rust canonical passing (was 10).

## [Unreleased — ergonomics pass, post four-model review]

### Changed
- **Parser accepts multi-line expressions.** Inside `cand`, `pre`,
  `post`, `when`, and bind right-hand sides, an expression may span
  multiple physical lines while brackets are unbalanced.
  Continuation stops at the next keyword head (`intent`, `sig`,
  `cand`, etc.) or when brackets balance; an unclosed bracket at
  stop time raises `ParseError`. Closes P1 finding AUD-2026-05-11-01
  — the previous `AttributeError` leaking out of the expression
  parser is now a clean typed error.
- **`reverse` is polymorphic over strings and lists.** Same
  primitive, same name. `reverse("abc")` → `"cba"`,
  `reverse([1,2,3])` → `[3,2,1]`. Establishes the rule for
  primitive design: polymorphism is allowed when semantics transfer
  cleanly and return shape is unambiguous. Capability manifest now
  reports `returns: "Any"` for `reverse`.
- **Capability manifest hash refreshed** to
  `sha256:845dbbbff6b8ba8957dc40383e9a54b386b172f8fa70ccc16a18be10e498afd4`
  (was `sha256:522c48d0dfd60c8c6d7528711c5624560fcabead76d9e80a4a782954e01a92f1`).
  Only delta is `reverse.returns` moving from `"List"` to `"Any"`.

### Added
- **`docs/AGENT_QUICKREF.md`** — one-page cross-reference distilling
  the common-guess pitfalls and the primitive surface from the
  capability manifest. Linked from README and `docs/FOR_AGENTS.md`.
- **Hint messages for known-guess misses.** The `%` lexer error
  points at `mod(a, b)`. `unknown callable: 'str.reverse'`,
  `'clock.hour'`, `'str.upper'`, and siblings now include a
  one-line hint naming the correct form. Closes P2 finding
  AUD-2026-05-11-02.
- **Spec sections in `docs/LANGUAGE.md`** on line continuation and
  on primitive polymorphism. Closes P3 finding AUD-2026-05-11-03.
- **Regression tests.** Gemini 2.5 Pro's failing fixtures
  (`palindrome.cod` and `classify_numeric.cod`) are committed as
  tests along with multi-line bind, unbalanced-brackets
  `ParseError`, `%`-hint, and `str.reverse`/`clock.hour`-hint
  tests. Seven new tests.
- **Paired dispatches** recording the decisions with justifications
  and the post-fix evidence:
  - `dispatches/2026-05-11-ergonomics-decisions.{readout.md,yaml}`
  - `dispatches/2026-05-11-ergonomics-audit.md` (Sable)
  - `dispatches/2026-05-11-ergonomics-post.{readout.md,yaml}`

### Refused
Not every suggestion from the four-model review landed; each refusal
is justified in the decisions dispatch:
- Infix `%` as sugar for `mod` — opens a door the language does
  not want open.
- Inline `if`/`when` as statement-level conditional — candidate
  dispatch is already the answer.
- Separate `str_reverse` primitive — subsumed by polymorphic
  `reverse`.

### Test count
129 passing (122 previous + 5 multi-line parser regressions + 2 hint
regressions). Rust canonical still at 10/10.

## [Unreleased — rename Noema → Codifide]

### Changed
- **The language is now Codifide, not Noema.** Every current-state
  identifier, path, binary name, and string reference is updated.
  Historical dispatches retain original phrasing for journal
  honesty. Name is a portmanteau: **Codified + Fidelity**.
- Python package `noema/` → `codifide/`.
- Rust crate `crates/noema-canonical/` → `crates/codifide-canonical/`.
- CLI: `python3 -m noema` → `python3 -m codifide`.
- File extension: `.nm` → `.cod`.
- Default store root: `~/.noema/store` → `~/.codifide/store`.
- Environment variable: `NOEMA_STORE` → `CODIFIDE_STORE`.
- Canonical form top-level tag: `"noema": "0.1"` → `"codifide": "0.1"`.
- Capability schema: `noema_capability` → `codifide_capability`.
- Logo palette adopted from Codifide Inc. company mark; wordmark
  split-colored **codi** / **fide** to match the company wordmark.
- README opener rewritten with the tagline *"confidence in code,
  for agents"* and the portmanteau explanation; Husserl etymology
  retired.

### Added
- `GOVERNANCE.md` — joint stewardship structure (Douglas Jones +
  Claude), artifacts-as-authority rule, spec-change process.
- `dispatches/2026-05-10-rename.{yaml,readout.md}` — paired
  dispatches on the rename rationale, scope, and what was
  preserved unchanged.
- `dispatches/2026-05-10-rename-journal.md` — execution journal.

### Broken
- **Every content hash produced before this commit is invalidated.**
  No external consumer depends on old hashes; no public release
  shipped under the Noema name. New capability manifest identity:
  `sha256:522c48d0dfd60c8c6d7528711c5624560fcabead76d9e80a4a782954e01a92f1`.

### Test count
122 passing (unchanged from pre-rename; one test fixture's
hardcoded string needed updating because sed rewrote the test's
own input into something that no longer matched its expected
output).

## [Unreleased — capability manifest]

### Added
- **Capability manifest.** `codifide capability` emits a structured,
  content-addressed document describing the language's full interface
  to agent consumers: AST node kinds, primitives with their effect
  labels and return types, the effect vocabulary, typed error classes,
  literal types, and the surface keyword tables. The manifest is
  generated from the implementation — primitive registry, error class
  hierarchy, parser keyword tables — so drift between manifest and
  runtime is caught by the test suite, not discovered at consumer
  time.
- `codifide capability --cbor` emits canonical CBOR bytes (about 47% of
  JSON size). `codifide capability --hash` prints the SHA-256 identity
  of the manifest over its canonical CBOR bytes.
- `docs/CAPABILITY.md` — spec for the manifest format, including
  stability rules and cross-implementation equivalence under the
  generator-field-elided comparison.
- `docs/capability-0.1.json` — the checked-in manifest for the
  current Python reference. Drift test keeps it in sync.
- `tests/test_capability.py` — 12 tests covering manifest-
  implementation agreement, drift detection, canonical form
  stability, and the error / primitive / keyword agreement surface.

### Test count
122 passing (110 previous + 12 capability).

## [Hardening + first real Codifide program]

### Fixed
- **Decoder allocation bound.** `decode_canonical_cbor` now accepts a
  `max_payload` argument (default 64 MiB, matching the Rust CLI cap)
  and refuses length prefixes above the bound before any allocation.
- **TOCTOU symlink defense.** `SymbolStore._write_atomic` refuses to
  write when the shard directory or the target path is itself a
  symlink, closing the resolve→rename window.

### Added
- `belief(value, conf)` primitive — lets user code construct
  confidence-annotated values without needing a model primitive.
- `examples/triage/` — the first Codifide program that uses the
  language's distinctive capabilities together: two pure classifiers
  (sentiment, length), a composing pipeline with belief dispatch
  and first-class refusal, and a demo script that publishes, indexes,
  imports, and runs end-to-end via content addressing.
- Regression tests for the two hardening fixes, plus full primitive
  exercise for `belief(value, conf)`.

### Test count
110 passing (105 previous + 5 new).

## [Unreleased — post-CBOR audit]

### Fixed
- **P1-5: Store write followed symlinks, leaking bytes outside the
  store.** `SymbolStore._write_atomic` now resolves the target's parent
  directory and refuses to write if the resolved path is not under
  `self.root`. This catches the symlink-planted-in-shard-directory
  attack that Sable found. Found by filesystem-surface probe in the
  CBOR-neighborhood audit; regression test in
  `tests/test_cbor_store.py::test_P1_5_write_refuses_to_follow_symlink_out_of_store`.
- **P1-6: `store.get()` leaked `UnicodeDecodeError` on malformed
  bytes.** The byte-sniffing dispatch (first byte is `{` → JSON, else
  CBOR) is replaced with suffix-based dispatch honoring the producer's
  wire form. Decoder exceptions from either path are wrapped in
  `StoreError` so the typed-error discipline holds uniformly.
  Regression tests for both malformed-CBOR and malformed-JSON paths.
- **P1-7: Rust CLI hung forever on `/dev/zero`.** `fs::read_to_string`
  is replaced with a bounded `File::open(...).take(cap).read_to_end`
  with a 64 MiB limit. Past the cap the CLI exits non-zero with a
  clean message. Regression test invokes the CLI on `/dev/zero` with
  a 5-second timeout.

### Added
- `dispatches/2026-05-10-cbor-audit.md` — Sable's audit of the CBOR
  neighborhood. Six probe batteries, ~80 adversarial inputs, three
  P1 findings filed.

### Test count
105 passing (101 previous + 3 Python audit regressions + 1 Rust CLI
audit regression).

## [CBOR]

### Added
- **Canonical CBOR (RFC 8949 §4.2 deterministic subset).** Both
  implementations — Python in `codifide/projection/cbor.py`, Rust in
  `crates/codifide-canonical/src/cbor.rs` — produce byte-identical output
  for every input the conformance test covers. RFC 8949 Appendix A
  vectors pass on both sides. Typical size: 25-30% of JSON.
- **CBOR content addressing.** `content_hash_cbor(module)` in Python,
  `content_hash_cbor(&value)` in Rust. Distinct from `content_hash`
  because the bytes hashed are different — this is the correct
  behavior for content addressing (the hash is a property of bytes,
  not of abstract meaning).
- **Strict canonical CBOR decoder.** `codifide/projection/cbor_decoder.py`
  rejects non-shortest heads, unsorted map keys, indefinite-length
  strings, and NaN/infinity. Its strictness is what keeps the
  ``hash → bytes`` mapping injective.
- **Store CBOR support.** `SymbolStore.put_cbor(name, defn)` and
  `symbol_cbor_bytes`/`symbol_hash_cbor`. CBOR objects live alongside
  JSON in the same shard tree with a `.cbor` suffix. `get_bytes` and
  `get` auto-detect the wire form on read. `has` treats either form
  as presence. The two identities are disjoint by design.
- **CLI additions:**
  - `codifide canonical --cbor <file.nm>` emits canonical CBOR bytes.
  - `codifide store put --cbor <file.nm>` stores symbols in CBOR form.
  - Rust binary: `codifide-canonical bytes-cbor` and `hash-cbor`
    subcommands.
- **Conformance tests:**
  - Python/Rust byte-equality on canonical CBOR for every example.
  - Python/Rust hash-equality on CBOR content hashes.
  - RFC 8949 Appendix A vectors on both sides.
- Spec additions in `docs/CANONICAL.md §Canonical serialization` —
  formal description of the CBOR byte form with the full determinism
  rules. `§Content addressing` updated to describe the JSON/CBOR
  identity split.

### Notes
- JSON remains the primary content-hash format for v0.1. Switching
  would invalidate every existing identity — breaking change
  scheduled for a v1.0-approaching release, not now.
- Roadmap v0.2 CBOR item shipped one minor release early, per user
  direction ("I like CBOR. roll with it.").

### Test count
101 passing (78 previous + 23 new: 17 CBOR encoder/decoder + 6 CBOR
store + 2 CBOR conformance + 2 CBOR hash conformance, minus double-
counted). 10 Rust tests passing (6 previous + 4 CBOR).

## [Polish — intent-graph errors, primitives, store verify, fuzz]

### Added
- **Intent-graph error messages.** `EffectViolation` and
  `ContractViolation` now render the full call path on failure, each
  frame annotated with its intent. "The function exists because: ..."
  at every level.
- **Expanded pure primitive library:**
  - Math: `abs`, `min`, `max`, `pow`, `floor`, `ceil`, `round`.
  - Collections: `min_of`, `max_of`, `sum`, `reverse`, `append`
    (non-mutating), `contains_item`.
  - Strings: `upper`, `lower`, `trim`, `starts_with`, `ends_with`,
    `replace`, `split`, `join`.
- **`codifide store verify <hash>`** — opt-in subcommand that walks a
  stored module's imports and reports any pointees missing from the
  store. Closes Sable's P3-1 from the index audit.
- **Parser fuzz harness** (`tests/test_parser_fuzz.py`) — 30
  hand-curated adversarial inputs + 200 structurally generated samples,
  each bounded by a 1s SIGALRM so hangs surface as failures.
- **Store concurrency test** (`tests/test_store_concurrency.py`) —
  8-process races on the same symbol and on distinct symbols; verifies
  identity agreement, object count, and absence of leftover temp files.
- **Documentation refresh:**
  - `README.md` rewritten to reflect current reality.
  - `docs/LANGUAGE.md` updated with imports, indices, shadowing,
    typed errors, recursion limit, store CLI.
  - `docs/TUTORIAL.md` new — end-to-end walk-through from first
    program to publishing and consuming an index.
  - `docs/ARCHITECTURE.md` new — layered structure for contributors.
  - `GETTING_STARTED.md` updated with the full-story walk-through.
- `sessions/2026-05-10.md` — session state for resumption.

### Fixed
- **P1-3: Lexer errors leaked as `LexError` through the parser's
  contract.** `_safe_parse_expr` now catches both `ExprParseError` and
  `LexError` and wraps them in `ParseError`. Found by the fuzz
  harness; affected unclosed strings, non-ASCII outside strings, and
  stray operator sequences.
- **P1-4: Deep parenthesis nesting blew the Python stack.** The
  expression parser now bounds paren nesting at 256 and raises a
  typed `ParseError` past that.

### Test count
76 passing (71 previous + 5 primitive library + 2 store verify + 2
parser fuzz + 2 store concurrency + 1 intent-chain -1 merged).

## [Content-addressed indices]

### Added
- **Content-addressed indices.** An *index* is a module whose
  `imports` map is its export table. New CLI subcommand:
  ```
  codifide store index --name <mod> name=sha256:<hex> ...
  ```
  which mints an index, stores it, and prints its identity. The index
  is itself content-addressed: same inputs produce the same hash;
  changing the module name or the entry set changes the hash; entry
  order does not.
- **`from <identity> import <names>` surface syntax.** A consumer
  writes `from sha256:... import hello, goodbye` and the parser
  resolves each name through the target's `imports` map, binding it
  in the consumer's own imports. The result is shape-identical to a
  consumer that wrote the direct identity-per-name form.
- `parse(source, store=...)` for `from`-import resolution; the CLI's
  `run` subcommand opens the store on demand.
- Transitive effect check flows through indices unchanged: a pure
  consumer cannot launder effects by routing an effectful symbol
  through an index.
- Spec updates:
  - `docs/CANONICAL.md §Shadowing` — locals over imports over
    primitives; effect checks apply to the resolved callee.
  - `docs/CANONICAL.md §Indices and \`from\`-imports` — index
    definition, grammar, parse-time resolution allowed.
- `tests/test_indices.py` — 13 tests covering index identity,
  order-independence, name sensitivity, parse-time resolution,
  effect check through indices, shadowing, and rejection of
  non-index targets.
- `dispatches/2026-05-10-index-audit.md` — Sable's audit of the new
  surface (two P3s, no higher).

### Test count
64 passing (51 previous + 13 new index/shadowing).

## [Content-addressed imports]

### Added
- **Content-addressed imports.** Modules can now reference other
  symbols by content identity. Surface syntax:
  ```
  import <local_name> = sha256:<hex>
  ```
  Imports are resolved through a symbol store at runtime; the
  interpreter accepts a `store=` argument, and the CLI's `run`
  subcommand gained a `--store` flag matching `store` subcommand
  conventions. An imported callee behaves exactly like a local `def`
  at the call site — same effect check, same contracts, same
  dispatch.
- Transitive effect check now treats imported callees uniformly with
  local ones. A pure caller cannot import an effectful symbol and
  launder its effects; content identity is the property that keeps
  this sound (the adversary cannot substitute a more-effectful body
  under the same hash).
- Canonical form gained an optional top-level `imports` field, emitted
  only when present and sorted by local name for stable bytes.
- `tests/test_imports.py` — 11 tests covering resolution, missing
  identity rejection, tamper detection through the runtime, effect
  check across imports, canonical round-trip, and surface-syntax
  rejection of malformed identities.
- `examples/imports_demo.cod` — documents the capability and conformance
  surface; the Rust canonical crate accepts the same `imports` key.
- Spec update in `docs/CANONICAL.md §Top-level shape` describing
  imports formally.

### Changed
- `Module` grew an `imports` field (tuple of `(name, identity)`
  pairs). Modules without imports canonicalize identically to before.

### Test count
51 passing (40 previous + 11 new).

## [Symbol store]

### Added
- **Content-addressed symbol store** (`codifide/store/`). Store symbols by
  SHA-256 of their canonical byte form; fetch by identity; verify hash
  on read (tampering raises `IntegrityError`, never returns a value);
  idempotent writes. Filesystem layout is Git-style sharded loose
  objects with atomic temp-file-plus-rename writes.
- CLI subcommands:
  - `codifide store put <file.nm>` — store every symbol in a module.
  - `codifide store get <hash>`     — print canonical JSON for an identity.
  - `codifide store list`           — list every stored identity.
  - `codifide store hash <file.nm>` — print identities without storing.
  - Store root via `--store`, `$CODIFIDE_STORE`, or default `~/.codifide/store`.
- Typed store errors: `StoreError`, `NotFound`, `IntegrityError`.
- `tests/test_store.py` — 13 tests covering hashing properties, store
  round-trip, idempotency, tamper detection, malformed identity
  rejection, and cross-implementation hash agreement with the Rust
  binary.
- Spec addition in `docs/CANONICAL.md §Symbol store` — the three
  properties a conforming store must uphold (hash-verified reads,
  hash-verified writes, idempotent writes).
- Test suite closures: nested-believe round-trip in canonical form,
  numeric-edge Python/Rust conformance (both closed from audit
  unknowns; the parser does not yet accept multi-line believe-arm
  values, noted as a surface-syntax limitation not a spec one).
- `cargo audit` run: 0 vulnerabilities across 22 transitive deps.

### Test count
40 passing (28 previous + 12 new: 11 store + 1 nested believe).

## [Sable audit resolution]

### Added
- **Sable persona** (`.kiro/steering/personas/sable.md`) — adversarial
  auditor role distinct from the two journalists. Every milestone now
  runs three personas: Sable tries to break it, Quill reports it in
  prose, Glyph emits a structured dispatch.
- Transitive effect subset check: every callee's declared effects must
  be a subset of every caller's. Enforced as a static pass at module
  load. Closes security audit P0-1.
- Typed primitive errors: `PrimitiveError`, `BottomPropagationError`,
  `RecursionLimitError`. Host-language exceptions (ZeroDivisionError,
  IndexError, TypeError) no longer leak through the Codifide error
  surface. Closes audit P1-1.
- Interpreter call-depth limit (`DEFAULT_MAX_DEPTH=64`) with typed
  `RecursionLimitError`. Defense-in-depth mapping in `run()` catches
  Python `RecursionError` if it wins the race. Closes audit P1-2.
- Rust canonical writer now ASCII-escapes non-ASCII codepoints to
  match Python's `json.dumps(ensure_ascii=True)` byte-for-byte. Closes
  audit P0-2.
- Python parser no longer double-decodes non-ASCII string literals via
  the `unicode_escape` path. Closes the second half of P0-2.
- `examples/unicode.cod` — non-ASCII conformance fixture. The
  conformance test now exercises byte-for-byte agreement on non-ASCII
  content with every run.
- Spec additions in `docs/CANONICAL.md`:
  - §Canonical serialization explicitly mandates ASCII-escaped strings.
  - §Contracts are pure — pre, post, guard run with effect budget ∅.
  - §Module names — grammar `[A-Za-z_][A-Za-z0-9_.-]*` required.
  - §Errors — eight typed error kinds enumerated.
  - §Content addressing clarifies that intent is part of identity.

### Changed
- Contracts (pre, post, guard) evaluate with an effect budget of ∅
  regardless of the surrounding signature. Closes audit P2-1.
- Module names are restricted to identifier grammar. Closes audit P2-2.

### Security
- See `dispatches/2026-05-10-security-audit.md` for the full audit
  report and `dispatches/2026-05-10-post-audit.yaml` for the
  structured resolution dispatch.
- Test count: 28 passing (23 previous + 5 security regressions).

## [Rust canonical addition]

### Added
- `docs/CANONICAL.md` expanded into a specification an independent
  implementer can follow without reading Python — normalization rules,
  canonical byte form, content-addressing scheme, effect algebra with the
  transitive-subset rule called out explicitly, dispatch and belief
  semantics.
- `crates/codifide-canonical/` — a Rust crate implementing the canonical
  form (AST, JSON round-trip, canonical byte form, SHA-256 content hash)
  and a small `codifide-canonical` CLI.
- Python-side `canonical_bytes` and `content_hash` helpers in
  `codifide.projection.canonical`, exported from the top-level package.
- `docs/RUST.md` describing the two-implementation strategy and why the
  interpreter is deliberately not ported yet.
- `tests/test_conformance.py` — byte-for-byte and content-hash conformance
  between the Python reference and the Rust crate on every example.

### Notes
- The Rust crate deliberately omits the interpreter. Semantics are still
  changing (the transitive effect-subset check will alter runtime
  behavior) and porting a moving target doubles the cost of every
  semantics change. Canonical form is the stablest piece of Codifide and the
  piece whose cross-implementation agreement matters most.
- Test count: 21 passing (19 previous + 2 conformance).

## [0.1.0] — 2026-05-10

### Added
- Canonical JSON schema for the Codifide hypergraph (`docs/CANONICAL.md`)
- Surface parser accepting ASCII keywords and unicode glyphs
- Tree-walking interpreter with:
  - Effect declaration and enforcement on primitive calls
  - Preconditions and postconditions as machine-checked clauses
  - Multi-candidate dispatch with declaration-order guards
  - Belief-dispatch on runtime confidence
  - First-class refusal (`bottom` / `⊥`)
- CLI entry point: `run`, `canonical`, `test`
- Three runnable example programs
- Test suite (19 tests, all passing)
- Two-journalist persona system (Quill, Glyph) with first snapshot dispatch

### Known limitations (call out deliberately)
- Effect subset checking is local to primitive call sites; it does not yet
  verify callee-effects ⊆ caller-effects across the call graph.
- Canonical form serializes to JSON only; CBOR and content-addressing arrive
  in 0.1.x.
- Candidate dispatch uses guards only; cost-based dispatch is future work.
- No type inference beyond literals.
- Reference interpreter is Python; Rust port scheduled for 0.3.

### Roadmap pointer
See `docs/ROADMAP.md` for the phased plan.
