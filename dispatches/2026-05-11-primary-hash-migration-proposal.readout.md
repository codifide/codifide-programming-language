# Proposal — primary content hash migration JSON → CBOR (2026-05-11)

**Status:** PROPOSAL. Not implementation. Requires Douglas's approval
before any code changes.

**Proposal revision: R1** (post Sable audit PA-1 through PA-6).

**Context.** The v0 primary content hash is SHA-256 over canonical
JSON bytes. CBOR has been supported since v0.2 alongside JSON, with
disjoint identities by design.

**Finding that makes this urgent.** Sable's re-audit
(`dispatches/2026-05-11-cbor-reaudit.md`) upgraded a latent
cross-implementation divergence to **P1**: Python and Rust can
produce different canonical JSON bytes (and therefore different
content hashes) for the same module, when the module contains a
float whose shortest-decimal representation differs between
Python's `json` and Rust's `serde_json`. This is reachable from
ordinary Codifide code. The current test suite doesn't catch it
because the `.cod` examples happen to avoid vulnerable values.

CBOR hashes over IEEE-754 bits rather than decimal text. The
divergence is structurally impossible in that representation.
Migrating the primary hash to CBOR closes AUD-08 permanently.

## Resolved probes (R1 updates)

Sable flagged three probes in `dispatches/2026-05-11-primary-hash-
migration-audit.md`; all three are resolved here.

- **PA-1, store polyform read.** Confirmed. `SymbolStore.get_bytes`
  and `SymbolStore.get` already try both `.json` and `.cbor`
  suffixes on read; any pre-migration JSON-hashed object remains
  fetchable by its JSON hash post-migration.
- **PA-2, manifest hash form.** Confirmed CBOR. The value
  `sha256:845dbbbf…` we've been citing is already a CBOR hash
  because `codifide capability --hash` always hashed over canonical
  CBOR bytes. The JSON-hash of the same manifest is
  `sha256:6ad49cc2…` — a value we have never cited anywhere in the
  repo.
- **PA-3, in-repo hash dependencies.** Probed with
  `grep -rE 'import.*= sha256:' . --include='*.cod' --include='*.py'`.
  Zero real dependencies. Matches are either illustrative
  documentation (`docs/LANGUAGE.md`), journal prose (dispatches),
  or test fixtures that compute hashes dynamically and remain
  correct under any hash form.
- **PA-6, float-bearing examples.** Every example contains floats
  because `Lit.conf = 1.0` is a field on every literal node.
  However, `1.0`'s shortest decimal (`"1.0"`) agrees across
  Python and Rust, so every current example's hash is stable
  under the two implementations. A probe confirmed: every
  `.cod` example in the repo has identical Python and Rust
  content hashes under the current JSON byte form. The AUD-08
  bug is reachable only by authoring a program with a vulnerable
  float literal, which no example does.

Result: the examples are all safe, but **any new program with
an f16-subnormal or f32-extremum float literal is not**. This
keeps the migration's urgency at P1 while making clear that
nothing currently in the repo is broken.

## Proposal

### What changes

1. **Primary content identity** becomes SHA-256 over canonical
   CBOR bytes, produced by RFC 8949 §4.2 deterministic encoding.
2. **The CLI defaults to CBOR** for `codifide store put`,
   `codifide store hash`, and all other hash-producing subcommands.
3. **JSON canonical form remains supported for inspection**
   (`codifide canonical <file>` continues to default to JSON, and
   `--cbor` continues to opt into CBOR bytes). JSON is a viewing
   format, not an identity format, post-migration.
4. **`codifide store get <hash>` accepts either form** — JSON or
   CBOR — looking up by identity directly. The stored bytes
   retain whatever wire form they were written with. (Most post-
   migration stores will be all-CBOR; pre-migration stores remain
   readable.)
5. **The capability manifest's identity** moves to CBOR-bytes
   hash. The value we've been citing
   (`sha256:845dbbbf…`) is a CBOR hash today because the
   manifest command already hashes over canonical CBOR; only
   symbol identities move.
6. **`docs/CANONICAL.md`** gets a corresponding rewrite of
   §Canonical serialization and §Content addressing.

### What breaks

**Every symbol identity in the world changes.** Currently that's:

- The capability manifest hash we've been citing in recent
  dispatches and CHANGELOG entries. *Actually: unchanged. The
  manifest already hashes over CBOR.* Good.
- Any `.cod` program with a direct `import name = sha256:...` to
  a specific hash. There are currently zero such imports in
  repository content (`grep -r 'import.*= sha256:' .` returns
  only test fixtures that build their own hashes dynamically).
- Any stored symbols a user has in their `~/.codifide/store`.
  These are user-owned state; the migration's backwards-compatible
  read path means they stay usable, just under their old
  identities.
- Any hashes cited in existing dispatches. Historical hashes in
  dispatches are journal-accurate; they are not re-written. Going
  forward, dispatches cite post-migration hashes.

### What does not break

- The parser, the interpreter, the effect system, the contract
  system, the dispatch system, the store's three-property
  contract, the runtime's typed-error set. The migration is a
  change to a byte-form choice, not to the language.
- The Rust canonical crate's surface. The crate already produces
  CBOR bytes and CBOR hashes; the migration flips which one is
  "primary" in the CLI's default behavior.
- The fact that two Codifide implementations have to agree on
  canonical form. They already do on CBOR for every example
  program and for the RFC 8949 Appendix A test vectors.

### Commit plan

The migration is mechanical and can land in one commit:

1. Change `SymbolStore.put_module`'s default to `cbor=True`.
2. Change `codifide store put`'s default to CBOR.
3. Change `codifide store hash`'s output format from the
   JSON-hash column to the CBOR-hash column.
4. Change `symbol_hash(name, defn)` to return the CBOR hash
   (renaming the old function to `symbol_hash_json` for callers
   that need it).
5. Change the Rust binary's default `hash` subcommand to
   CBOR as well, so both implementations default the same.
   (Resolves PA-5.)
6. Update `docs/CANONICAL.md` §Content addressing and
   §Canonical serialization.
7. Update `CHANGELOG.md` with a breaking-change entry.
8. Regenerate `docs/capability-0.1.json` if it drifts (expected
   no change; manifest is already CBOR-hashed).
9. Update `tests/test_conformance.py` — the JSON-bytes
   conformance test becomes "JSON form remains agreed across
   implementations on values in the mutually-safe subset," i.e.
   the examples. CBOR-bytes becomes the stronger claim.
10. **Un-skip `HalfPrecisionAllPatternsDiagnostic`** in the
    migration commit itself. The test should pass post-migration
    because the hash is now over CBOR bits, not decimal text.
    (Resolves PA-4 — no deferred un-skip.)
11. Dispatch an attestation pair (Quill + Glyph) confirming
    the migration landed and listing the new primary hashes
    of everything in `docs/` and `examples/`.

Expected diff size: under 200 lines of code; documentation
additions push it to ~400 lines. No new tests needed; existing
tests are updated in place.

### Rollback story

If the migration has to be reverted, the JSON hash path is still
present (`symbol_hash_json`) and the store's read path still
accepts JSON-formed objects. Reverting is a one-commit change
flipping defaults back.

### Post-migration state

- AUD-08 and AUD-04 are structurally closed.
- The `docs/CAPABILITY.md` claim about content-addressed agent
  consumption becomes bit-exact across implementations.
- The JSON-text decimal parsing divergence is no longer a
  soundness issue, only a readability curiosity.
- Future work: document the canonical CBOR form with RFC 8949
  references at the top of `docs/CANONICAL.md` so a third
  implementation can be written from the spec alone.

## What I'm asking Douglas to decide

- **Approve the plan as written** — go ahead and execute in a
  future session.
- **Approve with modifications** — note the modifications and I
  re-issue the proposal.
- **Defer** — name the specific blocker so the re-issue can
  target it.

## What I'm not yet sure of

- Whether any external consumer relies on the v0 JSON hashes.
  My read of the repo says no. Douglas's judgment is the
  authority.
- Whether the migration should ship at v0.3 or hold for v1.0.
  My read is "v0.3, now that AUD-08 is P1," but this is exactly
  the kind of call that belongs with Douglas.
- Whether a two-stage migration (CBOR hashes available on an
  opt-in flag for a release, then flipped to default) is
  better than a single-commit flip. For a project with no
  external release yet, single-commit is simpler and I'd
  prefer it. If there are external consumers I don't know
  about, two-stage is safer.
