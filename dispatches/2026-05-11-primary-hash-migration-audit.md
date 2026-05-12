# Sable — audit of the primary-hash migration proposal (2026-05-11)

Auditor: Sable
Scope: the proposal in
`dispatches/2026-05-11-primary-hash-migration-proposal.{readout.md,yaml}`.
I am not auditing the implementation (none exists yet). I am auditing
the *proposal*: what risks does it introduce, what does it miss, what
commitments does it rely on.

## Findings against the proposal itself

### PA-1 — P1 — store compatibility read path is promised but not specified

The proposal commits to "a backwards-compatible read path means
pre-migration user stores stay usable, just under their old
identities." It does not specify **how** the store discriminates
JSON-formed from CBOR-formed objects on read when both are named
with `.json` or `.cbor` suffixes in the current on-disk layout.

- If the post-migration `symbol_hash` is CBOR-based, and a
  user-stored JSON object is hashed-to-JSON-identity, a
  post-migration `store get <json-identity>` call **will not
  find the object** unless the store's `get` explicitly walks
  both forms. Today it does; the proposal should say so
  explicitly.
- A user who re-puts a module post-migration gets CBOR hashes.
  Their old JSON-hashed object lingers until GC (which does
  not yet exist — see the separate store-GC proposal). The
  store grows monotonically with duplicate objects. Not
  unsound, just wasteful.

**Disposition:** proposal must either (a) state that the store's
`get` is already polyform and works unchanged, which I believe is
true but did not verify, or (b) commit to a migration test that
round-trips a pre-existing JSON-hashed object through a
post-migration `get`.

### PA-2 — P1 — existing dispatches cite v0 JSON hashes; they become stale

The proposal says "historical dispatches retain their hashes —
journal-accurate." That's correct for honesty, but a reader
wandering into an old dispatch and trying to reproduce a claim
(`codifide store get <cited-hash>`) will fail.

- For dispatches citing manifest hashes (most of them), the
  proposal is wrong that the manifest hash is unchanged. I need
  to probe whether `codifide capability --hash` is CBOR today;
  the proposal asserts it, but I did not see the probe.
- For dispatches citing per-symbol hashes (few of them), those
  hashes become genuinely historical.

**Probe needed:**

```
$ python3 -m codifide capability --hash
# compare to the value cited in 2026-05-11-ergonomics-post.readout.md
```

If they match, the proposal's claim is correct.

### PA-3 — P2 — the "zero external consumers" claim is unverified

The proposal says "there are currently zero such imports in
repository content (`grep -r 'import.*= sha256:' .` returns only
test fixtures that build their own hashes dynamically)." That is
a testable claim; I did not run the grep. The proposal's
confidence in this claim is central to its "single-commit flip
is safe" recommendation. Douglas should either run the grep or
confirm he knows the repo has no such imports.

### PA-4 — P2 — step 9 defers a test un-skip to a future session

The proposal commits to un-skipping the
`HalfPrecisionAllPatternsDiagnostic` test *in a follow-on
session*, not in the migration commit itself. That leaves a
window where the test is still marked skipped with a message
referencing a closed finding. Either un-skip in the migration
commit (preferred) or update the skip message to cite the
migration as the unblock event (acceptable).

### PA-5 — P3 — proposal does not discuss the Rust binary's CLI default

The Python CLI's default flips. The proposal does not explicitly
address whether the Rust binary's `hash` subcommand should also
flip to `hash-cbor` as the default. Cross-implementation
consistency argues yes. Proposal should state the Rust side's
default explicitly.

### PA-6 — P3 — no explicit check for float-bearing modules in examples

Every `.cod` example in `examples/` should be probed to see if
its current JSON hash agrees with its CBOR hash. If any example
has a vulnerable float, the proposal's "examples are unchanged"
claim hides a fact worth stating: the example's identity
changes in the migration, same as any float-bearing module.

## What the proposal gets right

- The motivation is real. AUD-08 is a P1 I re-audited and confirmed.
- The rollback story is clean. `symbol_hash_json` staying present
  is the right shape.
- The "journal-accurate" treatment of historical hashes is
  correct — Codifide's dispatch discipline explicitly says
  historical dispatches retain original phrasing for journal
  honesty.
- Not touching the parser, interpreter, or effect system keeps
  the blast radius small.

## What I did not test

- I did not run `grep -r 'import.*= sha256:'` myself.
- I did not probe whether `codifide capability --hash` is CBOR-
  hashed today (per the proposal's claim) or JSON-hashed.
- I did not compute JSON vs CBOR hashes for each `examples/*.cod`
  to quantify how many identities actually change.
- I did not audit how the on-disk store layout accommodates
  dual-form reads post-migration.

## Post-audit disposition

- **PA-1 (P1) and PA-2 (P1) are blockers**. The proposal cannot
  be approved as written without these probed and the answers
  written into the proposal.
- **PA-3 (P2) is pending Douglas's confirmation**.
- **PA-4 (P2), PA-5 (P3), PA-6 (P3) are edits** to the proposal,
  not blockers.

I recommend the proposal go back for a revision that resolves
PA-1 and PA-2 before Douglas approves it. The work to resolve
them is small: run three probes, write the answers into the
proposal, re-file. Ten minutes.

## What I'm not yet sure of

Whether AUD-08's scope might extend further than f16-class
floats once someone probes the full double dynamic range. I
probed in the re-audit but only on f16-territory and f32
extrema. If the finding is broader than I think, the migration
proposal's urgency goes up, not down.
