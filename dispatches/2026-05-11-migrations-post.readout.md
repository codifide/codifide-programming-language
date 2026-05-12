# Migrations landed — post-work readout (2026-05-11)

User direction: "The change cost is low now as we have not published
yet. I want you do all of what's on the todo list now."

Three proposals executed in one session, in dependency order:

1. Primary content-hash migration JSON → CBOR.
2. Cost-based candidate dispatch (spec amendment).
3. Symbol-store garbage collection (design implemented).

All three shipped as code. Tests green on both implementations.

## What changed and how

### 1. Primary hash migration

`symbol_hash`, `symbol_bytes`, `content_hash`, `canonical_bytes`,
`SymbolStore.put`, `SymbolStore.put_module`, the `codifide store`
CLI, and the Rust `codifide-canonical` CLI all moved their primary
path to CBOR. The legacy JSON paths are preserved under `_json`
suffixes (Python) and `hash-json` subcommand (Rust). See
`CHANGELOG.md` for the full delta list.

The store's polyform read path — confirmed clean in Sable's
audit PA-1 — means any pre-migration JSON-hashed object on disk
is still fetchable by its JSON identity. Post-migration writes
produce CBOR-hashed identities, which coexist with pre-migration
JSON objects on disk.

AUD-2026-05-11-04 (P2, CBOR conformance) and AUD-2026-05-11-08
(P1, JSON conformance) are now **structurally closed** on the
Python-side primary path. The Rust CLI still accepts canonical
JSON text as input, so the exhaustive f16 diagnostic remains
skipped with a new reason (Rust's `serde_json` decimal parser
is still in the JSON-text reading path). Closing that fully
requires a Rust subcommand that accepts canonical CBOR bytes
directly; scheduled as a future follow-on.

### 2. Cost-based candidate dispatch

New optional `cost` field on candidates. Parser accepts
`cost <non-negative-integer>` inside a `cand` block. Dispatcher
selects `min((cost_or_∞, declaration_index))` among satisfied
candidates. Un-annotated modules dispatch identically to pre-
amendment behavior.

Canonical form is additive and backwards compatible: a candidate
without a `cost` field produces identical canonical bytes as
before the amendment. No existing content hash is invalidated.

Rust crate's `Candidate` gained `cost: Option<u64>`. JSON
to/from updated. The crate rejects non-integer or negative
cost with a typed shape error.

Sable's audit CBD-1 and CBD-2 concerns are addressed in the
proposal's R1 revision (tight canonical-form typing; explicit
behavioral-drift notice when adding a single annotation).

### 3. Store GC

New `ROOTS` file, new `GC.LOG`, new `LOCK` file. Two-argument GC
API (`SymbolStore.gc(execute=False)`) returns a `GCReport`.
`codifide store gc` and `codifide store roots` CLI subcommands
wired up.

Sound-deletion contract from the design dispatch holds:

- GC refuses `--execute` with empty/missing ROOTS.
- Transitive closure walks the `imports` map through indices,
  pulling live symbols along with rooted modules.
- Deletions are logged with ISO-8601 timestamps; append-only.
- Concurrent writes and concurrent GC serialize via file lock.

All three "subsidiary proposals" from the design dispatch shipped
as stated: empty ROOTS is an error on execute, ROOTS is plain
text with comments, ROOTS is not content-addressed.

## What got refused

Consistent with the decision log from earlier in the session:

- Time-based GC (conflates "old" with "unwanted").
- Implicit GC on every `put` (would violate the mental model).
- Inline `if`/`when` statement (candidate dispatch is the answer).
- Infix `%` for `mod` (fights the named-primitives thesis).
- Separate `str_reverse` primitive (polymorphic `reverse` serves).

Each refusal is documented in its originating decisions dispatch
with a specific reason, not drift.

## Test count

- Python: 166 passing + 1 skipped diagnostic (was 155 + 1).
  - +14 cost-based dispatch tests (`test_cost_dispatch.py`).
  - +11 store-GC tests (`test_store_gc.py`).
  - Pre-existing suite updated to match the new primary-hash
    path (path suffixes, byte-form comparisons).
- Rust canonical: 14 passing (unchanged from this morning).
  Tests updated to construct `Candidate` with the new `cost`
  field.

## Capability manifest hash

- Pre session: `sha256:845dbbbff6b8ba8957dc40383e9a54b386b172f8fa70ccc16a18be10e498afd4`
- Post session: `sha256:56fa68ae1794a99f2c52c1e5dda0fc7fa2f51241fbfca32c79296e184e6b43b5`

The delta is the new `cost` surface keyword appearing in the
`surface_keywords` section of the manifest. The primary-hash
migration did **not** contribute to the delta: the manifest was
already CBOR-hashed before migration (migration flipped
per-symbol hashes, not the manifest's own hash).

The new identity is what external consumers should pin.

## What remains open from the broader queue

- **CBOR-aware Sable re-audit on the new surface.** Cost
  annotations and GC are both new attack surfaces that Sable has
  not yet probed. Scheduled for next session; not urgent because
  the spec amendment is additive and the GC code refuses unsafe
  operations explicitly.
- **Rust CLI subcommand accepting canonical CBOR bytes directly.**
  Would close the residual AUD-08 surface (exhaustive f16
  diagnostic could un-skip). Small, bounded task.
- **Documentation: `docs/STORE.md`** new file was planned in the
  GC design; deferred. `docs/CANONICAL.md` gained the GC
  subsection already.
- **External-model re-run.** Measure whether the new manifest
  hash, the cost-annotation capability, and the GC surface
  change fresh-agent authoring rates. The honest way to find out
  is to hand the next external model the repo with no coaching.

## What I'm not yet sure of

- Whether any `.cod` example in the repo would produce a different
  content hash under the new primary path if a user rebuilds their
  store. The short answer is "yes, every symbol's identity is
  now a CBOR hash, not a JSON hash." A user with an existing
  `~/.codifide/store` will find their old objects are still
  fetchable by their old hashes but new writes produce new ones.
  Running `codifide store put` on a known-old `.cod` file will
  produce a different identity than the user recorded last week.
  This is the expected cost of the migration and is the reason
  the migration was scheduled as a breaking change; having no
  external consumers yet is the reason we could ship it now.
- Whether the Sable audits I wrote for the two proposals caught
  everything. Two P1-class concerns (PA-1, PA-2) and two (CBD-1,
  CBD-2) were resolved in proposal revisions before landing. A
  third-party audit of the shipped code is a future Sable run.
