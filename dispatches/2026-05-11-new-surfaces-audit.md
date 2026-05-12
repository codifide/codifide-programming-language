# Sable — audit of cost-based dispatch + store GC (2026-05-11)

Auditor: Sable
Scope: the two new surfaces shipped in the three-migration pass —
cost-based candidate dispatch (spec amendment, code + docs) and
symbol-store garbage collection (new code + CLI).

Neither surface was probed adversarially before landing. This
audit closes that gap.

## Cost-based dispatch findings

### CDP-1 — P2 — dispatcher does not fall through on `bottom` from cheapest candidate

**What.** The new dispatcher selects `min((cost_or_∞, index))`
among satisfied candidates and evaluates that single candidate's
body. If the body returns ⊥ (bottom), the dispatcher does NOT try
the next-cheapest candidate; the refusal escapes as
`RefusalError`, same as pre-amendment.

**Probe.**

```codifide
def f
  intent "cheap-refuses"
  sig () -> String
  effects {}
  cand
    cost 1
    bottom
  cand
    cost 1000
    "fallback"
```

Expected by an agent that thinks "cheapest sufficient": returns
`"fallback"`. Actual: raises `RefusalError`.

**Why it matters.** This is a genuine semantic ambiguity. Two
defensible interpretations:

- **A. "cheapest that satisfies its guard wins; its result is the
  answer, refusal and all."** Matches current behavior. Preserves
  the pre-amendment "first-satisfied" mental model extended with
  cost.
- **B. "cheapest that actually produces a value wins; bottom
  means try the next."** Makes cost annotations a true
  multi-tier fallback system. Costly because the dispatcher may
  evaluate multiple bodies (and bodies can have effects), so it
  changes the dispatch mental model.

The spec amendment (`dispatches/2026-05-11-cost-based-dispatch-
proposal.readout.md`) implicitly chose interpretation A by not
discussing ⊥, but did not call the choice out. An agent reaching
for cost annotations for multi-tier refusal will hit this and
either change behavior silently or file a bug.

**Severity.** P2. Not a crash. Not soundness. Spec silence on a
material dispatch question. Fix by either (a) documenting
interpretation A explicitly with a rationale in `docs/CANONICAL.md
§Dispatch`, or (b) amending the dispatcher to fall through on ⊥
(which is a bigger spec change and would need its own proposal).

**Recommendation.** Option (a) for this session — pure docs.
Option (b) as a follow-on proposal if user feedback asks for it.

### CDP-2 — P3 — canonical form accepts cost as a u64 but the in-memory Python type is `int` with no documented upper bound

**What.** The Python `Candidate.cost` is an `Optional[int]`. The
Rust side uses `Option<u64>`. The spec says "non-negative
integer." For values above `u64::MAX`, behavior is undefined.

**Probe.**

Python accepts `cost = (1 << 200)` without complaint. Rust
rejects it at `from_canonical_json`. The two agree on `u64` range
but disagree above it.

**Severity.** P3. Agents don't realistically use cost values above
`u64::MAX`. But spec-conforming second implementations should know
the bound. Fix by documenting `cost ≤ u64::MAX` in
`docs/CANONICAL.md §Candidate`.

## Store GC findings

### GC-1 — P2 — GC.LOG write follows symlinks

**What.** `_append_log` opens `<store>/GC.LOG` with
`open(log_path, "a", ...)`, which follows a pre-existing symlink.
An attacker who plants a symlink at `<store>/GC.LOG` pointing at
a file they control will receive GC's append-writes.

**Probe.**

```python
os.symlink("/tmp/attacker-file", f"{store_root}/GC.LOG")
store.gc(execute=True)
# attacker-file now contains "2026-05-11T... sha256:..."
```

**Why it matters.** GC.LOG contents are not secrets — they are
timestamps plus public content-hashes of things the attacker already
knows exist in their filesystem. Low info-leak severity. But the
same attack shape applied to symbol writes was audited P1 on
2026-05-10; applying the same defense here is cheap and consistent.

**Severity.** P2. Fix by opening with `O_NOFOLLOW` (refuses
symlinks at open time) and checking that the log's parent is
within the store root.

### GC-2 — P3 — LOCK file silently truncates pre-existing content

**What.** `_StoreLock.__enter__` opens `<store>/LOCK` with
`"w"` mode, which truncates. A user who accidentally writes
something into the LOCK file loses that content on the next GC.

**Probe.**

```python
Path(f"{store_root}/LOCK").write_text("important")
store.gc()
# LOCK is now empty.
```

**Why it matters.** Users who come across `LOCK` in the store
may think it's a regular file. Truncating isn't destruction of
the store — the store's symbols are content-addressed and
elsewhere — but it violates "least surprise."

**Severity.** P3. Fix by opening with `"a"` mode (append-create)
instead of `"w"`. The file is only used for `flock` anyway; its
content doesn't matter.

### GC-3 — P3 — malformed ROOTS entries crash GC instead of surfacing per-line diagnostics

**What.** A malformed identity in ROOTS causes
`SymbolStore.add_root` to raise `StoreError` at *add* time, but
the same malformed content on disk (if a user edited ROOTS
directly) causes `gc()` to raise at run time via the closure
walker.

**Probe.**

```python
Path(f"{store_root}/ROOTS").write_text("sha256:garbage\n")
store.gc()
# StoreError: malformed sha256 identity
```

**Why it matters.** The user gets a typed error (good) but the
error doesn't name the line number or the specific bad entry
(bad). A ROOTS file with 50 entries and one typo gives no
breadcrumb.

**Severity.** P3. Fix by having `read_roots` validate each
identity and report line-numbered errors; or by making `gc()`
more tolerant and skipping malformed roots with a warning.

**Recommendation.** Validate in `read_roots` with line numbers.
Tolerating malformed roots silently would be worse.

## What I did not test

- The Rust fuzz harness with cost-bearing inputs. The harness
  exists but I did not add cost fields to its random generator.
- Stress testing GC over a store with 10k+ symbols. Design is
  O(n) but constant factors are unmeasured.
- Concurrent `put` + `gc(execute=True)` race under high load.
  The file lock serializes them; I didn't try to break it.
- Whether the ROOTS file's line-continuation or unicode handling
  matters (it does not, for now — plain ASCII hex).
- Whether deleting a symbol-under-symlink does the right thing
  (symbols shouldn't be symlinks anyway, but).

## Post-audit expectations

- **CDP-1 (P2)** and **CDP-2 (P3)** are docs fixes. Apply to
  `docs/CANONICAL.md §Dispatch` and `§Candidate`.
- **GC-1 (P2)**: fix in-session. Small, bounded code change.
- **GC-2 (P3)**: fix in-session. Literally changing `"w"` to
  `"a"`.
- **GC-3 (P3)**: fix in-session. Validate + report line numbers.

No P0 or P1 findings. The new surfaces hold up well. This is the
kind of audit result that suggests the three-persona system is
working: the proposal-phase Sable audits caught the structural
issues; this post-implementation audit is finding polish items
only.
