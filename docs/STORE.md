# Codifide Symbol Store

The symbol store is how Codifide makes content addressing operational.
A symbol is a single definition. Its identity is the SHA-256 of its
canonical byte form. The store maps identity to bytes, and guarantees
a small set of properties that make that mapping safe for agents to
exchange.

This document is the specification implementers should follow and the
practical guide agents should read before putting a symbol anywhere
important.

## The four properties

A conforming store upholds these four properties for every read and
write. The first three are v0 invariants; the fourth was added on
2026-05-11 when garbage collection landed.

1. **Hash-verified reads.** On every read the store re-hashes the
   bytes on disk and compares to the requested identity. Any
   disagreement raises `IntegrityError` and the bytes are not
   returned. Corruption, tampering, and bit-flips all surface the
   same way: you don't get a value back.

2. **Hash-verified writes.** The store refuses to write bytes that
   do not hash to the declared identity. This protects against the
   caller more than against the disk — a caller who computes the
   wrong identity for some bytes gets `IntegrityError` at write
   time instead of writing a misnamed object.

3. **Idempotent writes.** Writing the same identity twice is a
   no-op. Because the bytes are byte-identical (content addressing),
   there is no semantic difference between "create" and "overwrite."
   Calling `put` ten times produces one file on disk and returns
   the same identity ten times.

4. **Sound deletion.** Garbage collection may only remove an
   identity if (a) the identity was present when GC started, (b)
   it was not reachable from any declared root through a
   transitive-closure walk of imports, and (c) the caller
   explicitly authorized deletion via `execute=True` while a
   non-empty ROOTS file existed.

Any implementation that upholds all four properties is a conforming
store regardless of its on-disk layout. The reference Python store
happens to use Git-style sharded loose objects; a different
implementation using SQLite or an object-store backend is
permitted.

## On-disk layout (reference Python store)

```
<store root>/
  sha256/
    ab/
      abcd...ef.cbor     # primary wire form since 2026-05-11
      abcd...ef.json     # legacy wire form
    cd/
      cdef...01.cbor
  ROOTS                  # one identity per line; comments start with #
  GC.LOG                 # append-only log of GC deletions
  LOCK                   # advisory flock held during GC runs
```

The first two hex characters of the digest are a sharding prefix so
one directory does not accumulate tens of thousands of files. This
matches the shape Git uses for loose objects and keeps filesystem
performance reasonable at scale.

A single identity exists under at most one suffix at any given
time. The store has a "polyform read" path — `get_bytes` and
`get` try `.cbor` first, then `.json` — so pre-migration stored
objects remain addressable by their old JSON-hash identity while
new writes produce CBOR-hash identities.

### Atomic writes

All writes go through `tempfile.mkstemp` in the same shard
directory, `write`, `flush`, `fsync`, then `os.replace` into
place. A crashed writer leaves no half-written object visible —
the temp file has a `.codifide-*.tmp` prefix and is cleaned up by
the next successful write.

### Symlink defense

Multiple layers reject symlinks inside the store tree:

- The parent of a target path is resolved and must be under the
  store root.
- A target that is itself a symlink is refused.
- A shard directory that is a symlink is refused.

Each defense caught a specific audit finding in the 2026-05-10
CBOR audit (P1-5) and the 2026-05-11 GC audit (GC-1, GC-2).

## Garbage collection

`~/.codifide/store` grows monotonically under normal use. Content
addressing guarantees a symbol is the same bytes today as last
Tuesday; it does not give the store a deletion policy. GC adds
one.

### Roots declare what's live

Reachability starts from a root set the user declares explicitly.
Roots live in a plain-text file at `<store>/ROOTS`:

```
# My favorite greet
sha256:f8fb5fda1b2462e7fb60641ad2bc4901439719966d4fe8610ea388b8685b321a

# The index my project uses
sha256:5899ab1c4e8c0e8f...
```

Each line is either an identity (primary wire form recommended;
legacy JSON-hash identities work too) or a comment starting with
`#`. Blank lines are ignored. Inline comments after an identity
(`sha256:... # label`) are allowed.

Every identity in ROOTS is validated on read: the shape must match
`sha256:<64 lowercase hex>`. A malformed line raises `GCError` with
the offending line number. This catches typos early rather than
letting them surface later in a less-localized error.

GC does not infer roots. No time-based heuristic, no
reachability-from-working-directory, no "last used." The rule is
explicit: if an identity is not in ROOTS' transitive closure, GC
treats it as garbage. The rule's rigidity is the point — deletion
is irreversible in a content-addressed system, and GC's answer to
"why did you delete this?" must always be either "it wasn't in
your roots' closure" or "you told me to delete it directly."

### Transitive closure through imports

Starting from each root, GC walks the `imports` map of every
module it finds. An import identity is added to the frontier; a
module reachable through any root is live; everything else is
garbage.

Cycles are structurally impossible in a content-addressed store —
an identity is the hash of its bytes, and cyclic bytes cannot be
constructed. The closure walk always terminates.

Broken imports (a root that references an identity not in the
store) are tolerated. They contribute to the reachable set as
"seen and missing" so the store doesn't try to delete them
(they aren't there) but also doesn't treat them as errors
(it's not GC's job to validate the store's wholeness; that's
what `codifide store verify` is for).

### Dry-run discipline

GC is dry-run by default. `SymbolStore.gc()` or
`codifide store gc` prints what *would* be deleted and does not
touch the store:

```
$ codifide store gc
would delete 47 identities, preserved 12, 0 bytes reclaimed (roots: 2)
would delete:
  sha256:a1b2c3...
  sha256:d4e5f6...
  ...
Pass --execute to actually delete.
```

Actually deleting requires `SymbolStore.gc(execute=True)` or
`codifide store gc --execute`. With `--execute`, GC will:

- Verify ROOTS is non-empty. Empty ROOTS with `--execute` raises
  `GCError` rather than deleting everything. This is a deliberate
  footgun guard — agents who forget to set up roots should not be
  able to accidentally wipe a store.
- Acquire the store's LOCK file via `fcntl.flock`.
- Delete each unreachable identity, summing bytes freed.
- Append each deletion to GC.LOG.
- Release the lock.

### Concurrency

A GC run and a concurrent `put` serialize via the file lock. Puts
issued while GC holds the lock block until GC releases; GC waits
for any in-progress puts to finish before starting.

The lock does not protect against the race where a put lands
between the closure computation and the delete sweep — that put's
new identity isn't in the closure (it didn't exist when the walk
ran), so it would be treated as garbage. Mitigation: don't run GC
while writing. If you need both, serialize at the application
layer, or add the newly-put identity as a root before running GC.

### GC.LOG

Every deletion is logged as one line: ISO-8601 timestamp, space,
identity. Append-only. The log is opened with `O_NOFOLLOW` so a
symlink planted at GC.LOG by an attacker cannot redirect the
append-write.

GC.LOG is not rotated. If it grows large that tells you something
about how often you're deleting; the log's size is not the
problem.

### What's explicitly refused

Two alternative designs were considered and declined. Each refusal
is documented in
`dispatches/2026-05-11-store-gc-design.readout.md`:

- **Time-based GC.** A rule like "delete identities not touched
  in 30 days" conflates "old" with "unwanted." A content-
  addressed store's whole point is that age is not a property of
  value. Explicit roots are what separate live from garbage.
- **Implicit GC on `put`.** Amortizing GC across write operations
  would make `put` potentially destructive, which violates the
  store's core mental model (puts are idempotent; they don't
  delete).

## CLI reference

All commands accept `--store <path>` at the `store` level:

```
codifide store put <file.cod> [--json]
codifide store get <hash>
codifide store list
codifide store hash <file.cod> [--json]
codifide store index --name <mod> name=sha256:<hex> ...
codifide store verify <hash>
codifide store gc [--execute]
codifide store roots list
codifide store roots add <identity>
codifide store roots remove <identity>
```

Defaults:

- Root path: `$CODIFIDE_STORE` if set, else `~/.codifide/store`.
- Wire form: CBOR since 2026-05-11. `--json` opts into the legacy
  JSON-hash identity on `put` and `hash`.

## Pre-migration compatibility

Stores created before 2026-05-11 contain `.json` objects whose
identities hash the JSON byte form. After the migration:

- Those objects remain **fetchable** by their old (JSON) identity.
  The `get` / `get_bytes` polyform read path handles this
  transparently.
- A fresh `put` of the same symbol produces a new (CBOR) identity.
  The old object is not overwritten; both coexist under their
  respective identities.
- `iter_identities` surfaces both forms. Neither is "primary" on
  disk; they are just two identities with two byte forms for the
  same abstract symbol.
- `SymbolStore.gc(execute=True)` with a ROOTS file that lists
  only CBOR-hash identities will delete the legacy JSON-hashed
  objects as unreachable. Users who want to keep legacy identities
  must add them to ROOTS explicitly.

## API surface

```python
from codifide.store import SymbolStore, symbol_hash, symbol_hash_json

store = SymbolStore("~/.codifide/store")

# Put a symbol (CBOR, primary)
identity = store.put("greet", definition)

# Put a symbol in legacy JSON form
legacy_id = store.put_json("greet", definition)

# Fetch bytes (polyform; rehashes on read)
data = store.get_bytes(identity)
obj  = store.get(identity)      # parsed to dict

# Presence check
store.has(identity)  # True if either suffix exists

# Iterate
for id_ in store.iter_identities():
    ...

# Garbage collection
store.add_root(identity)
report = store.gc()              # dry run
report = store.gc(execute=True)  # delete, requires non-empty ROOTS

# Roots management
store.roots()                    # list
store.add_root(identity)         # idempotent
store.remove_root(identity)      # returns False if absent
```

## Errors

| Error | When |
|---|---|
| `NotFound` | The requested identity is not in the store. |
| `IntegrityError` | Bytes on disk do not hash to the requested identity, or caller asked to write bytes under a mismatched identity. |
| `StoreError` | Base class; also raised for malformed identities, symlink refusals, and out-of-store paths. |
| `GCError` | GC cannot run: ROOTS is missing or empty with `--execute`, or a ROOTS line is malformed. |

All errors inherit from `StoreError` (except `GCError` which is
part of the GC subsystem and inherits from `Exception`). Hosts
can catch the base class to handle store-level failures
uniformly.

## See also

- `docs/CANONICAL.md §Content addressing` — what identities mean
  and why CBOR became the primary form.
- `dispatches/2026-05-11-store-gc-design.readout.md` — the design
  dispatch that preceded the implementation.
- `dispatches/2026-05-11-store-gc-design.yaml` — structured
  version of the same.
- `dispatches/2026-05-11-new-surfaces-audit.md` — Sable's
  post-implementation audit of the GC and its fixes.
