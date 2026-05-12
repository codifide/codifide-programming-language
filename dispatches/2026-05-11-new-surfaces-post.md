# New-surfaces audit — post-fix attestation (2026-05-11)

Follow-on to `dispatches/2026-05-11-new-surfaces-audit.md`.

Sable audited the two surfaces shipped in the three-migration pass
(cost-based dispatch and store GC). Five findings filed. Zero P0 or
P1. Four of five fixed in-session; one is a docs-only clarity fix
also applied.

## Resolution per finding

### CDP-1 (P2) — dispatcher behavior on ⊥ from cheapest candidate
*Status: docs fix applied.*

`docs/CANONICAL.md §Dispatch` now states explicitly that the
dispatcher does not fall through on ⊥ — the cheapest satisfied
candidate's ⊥ escapes as a refusal just like pre-amendment.
Interpretation (A) selected and documented; interpretation (B)
left as a future proposal if feedback asks for it.

Probe that surfaced the ambiguity still triggers; it's just no
longer ambiguous.

### CDP-2 (P3) — cost upper-bound undefined
*Status: docs fix applied.*

`docs/CANONICAL.md §Candidate` now states the range is
`[0, 2^64 - 1]`. Python accepts up to `u64::MAX` by construction;
Rust uses `u64`; bigints are not a concern any realistic agent
will have.

### GC-1 (P2) — GC.LOG write followed symlinks
*Status: code fix applied; regression test added.*

`_append_log` now opens with `O_NOFOLLOW` and surfaces a clean
`OSError` if the log path is a symlink. Test in
`tests.test_store_gc.PostAuditHardening.test_GC_1_log_write_refuses_symlink`
verifies the refusal and checks that the attacker's file stays
empty.

Defense shape matches the 2026-05-10 symbol-write hardening
(P1-5, P1-6) — consistent story across the store's write surface.

### GC-2 (P3) — LOCK file truncated pre-existing content
*Status: code fix applied; regression test added.*

`_StoreLock.__enter__` now opens LOCK with `"a"` (append-create)
instead of `"w"` (truncate). flock is advisory and doesn't care
about file contents. Test in
`PostAuditHardening.test_GC_2_lock_does_not_truncate_preexisting_content`
pins it.

Also added: refuse to acquire the lock if LOCK is a symlink.
Same defense shape; cheap.

### GC-3 (P3) — malformed ROOTS entries lacked line numbers
*Status: code fix applied; regression tests added.*

`read_roots` now validates each entry's `sha256:<64 lowercase hex>`
shape and raises `GCError` with the offending line number and
content on the first malformed entry.

Two tests: one for the error path (line number surfaces correctly)
and one for the happy path (comments and blanks still accepted).

## Test count after this pass
- Python: 170 passing + 0 skipped (was 166 + 0).
- Rust canonical: 28 passing (unchanged).

## What remains open
The audit did not find any P0 or P1 issues in either new surface.
That is the result we were hoping for: Sable's proposal-phase
audits (PA-*, CBD-*) caught the structural issues before
implementation; this post-implementation audit caught polish
items only.

Two low-priority items noted for future sessions:
- Rust fuzz harness doesn't generate cost-bearing inputs; a small
  extension would strengthen the random corpus.
- GC stress test over a 10k-symbol store to measure closure
  performance. Design is O(n); constants unmeasured.
