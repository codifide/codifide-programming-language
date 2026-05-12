# Design — Codifide symbol store garbage collection (2026-05-11)

**Status:** DESIGN DISPATCH. Not implementation. Requires Douglas's
approval of the design before implementation begins.

**Context.** The content-addressed symbol store
(`codifide/store/symbol_store.py`) grows monotonically. Content
addressing guarantees immutability per identity; a symbol that
was useful last Tuesday is still present and fetchable today.
The store has no mechanism to reclaim space from entries that are
no longer reachable from any "live" root.

For a prototype this is fine — stores are small and
`rm -rf ~/.codifide/store` is an acceptable reset. For a language
that plans to be used seriously, it is not fine. The store needs
a GC.

## The three open questions I flagged earlier

1. What is the **root set** — what does "reachable" mean in this
   language?
2. How does GC treat **dry runs and safety** — can a user
   accidentally delete something they wanted?
3. How does GC **participate in the three-property store
   contract** (hash-verified reads, hash-verified writes,
   idempotent writes)?

This dispatch proposes an answer for each, then states the
implementation shape.

## 1. Root set

A Codifide symbol identity is reachable iff it is referenced by a
chain of imports starting from a **root**. The design question is
what roots are.

**Proposal: roots are user-declared.** A root file at
`<store_root>/ROOTS` lists identities one per line. Every identity
reachable through that file's transitive import closure is
live. Everything else is garbage.

```
# ~/.codifide/store/ROOTS — example
sha256:f8fb5fda...   my favorite greeting
sha256:5899ab1c...   the index I use most days
```

Why user-declared rather than inferred:

- **Inference has no correct answer.** Codifide doesn't know what
  an external consumer cares about. A symbol that looks
  unreferenced today might be the exact bytes a remote agent is
  about to ask for tomorrow. Inference would have to be
  time-based ("older than N days, and nothing locally points at
  it"), and time-based GC in a content-addressed system is
  exactly the wrong primitive — it conflates "old" with
  "unwanted," which are not the same.
- **User-declared is explicit.** The user commits to "these are
  the identities I consider live." GC then has a defensible
  answer to "why did you delete this?" Every deletion traces to
  either (a) the identity wasn't in the closure of any root at
  the time GC ran, or (b) GC was told to delete it directly.

**Subsidiary proposals:**

- Empty `ROOTS` is an error, not "everything is garbage." GC
  refuses to run with no declared roots. Prevents the trivial
  footgun of "I forgot to set up roots and lost my store."
- `ROOTS` is a plain text file because it's user-editable;
  canonical JSON/CBOR would be wrong — the user writes it.
- Comments allowed (lines starting with `#`).
- The `ROOTS` file is **not** content-addressed. It's a mutable
  root specification, and content-addressed mutability makes no
  sense.

## 2. Dry run and safety

**Proposal: GC is dry-run by default.** Every invocation prints
the list of identities it would delete. To actually delete, the
user passes `--execute`.

```
$ codifide store gc
codifide: would delete 47 identities:
  sha256:a1b2c3... (unreachable from any root)
  sha256:d4e5f6... (unreachable from any root)
  ...
Pass --execute to actually delete.

$ codifide store gc --execute
codifide: deleted 47 identities (2.3 MiB reclaimed)
```

Why dry-run default:

- **Deletion is irreversible.** Content-addressed objects cannot
  be reconstructed without their pre-images. If GC deletes
  something the user wanted, the recovery story is "ask whoever
  had the bytes before to re-publish them." For a single-user
  local store there may be no such party.
- **Dry-run gives the user a preview** before any byte leaves
  disk. The audit trail for "I deleted the wrong thing" is now
  "the dry-run said I was going to and I passed `--execute`
  anyway," which is a survivable mistake. Silent deletion without
  preview is not.

**Additional safety:**

- `codifide store gc --execute` writes an audit log to
  `<store_root>/GC.LOG` with timestamp and deleted identities.
  Append-only. Survives across runs.
- If `--execute` is passed but `ROOTS` is empty or missing, GC
  refuses and exits non-zero.
- GC does not touch the `ROOTS` file or `GC.LOG` itself.

## 3. Interaction with the three-property contract

The store's three properties are hash-verified reads,
hash-verified writes, idempotent writes. GC adds **sound
deletion**: a fourth property.

**Definition of sound deletion:**

> For every identity `I` the store deletes, before deletion,
> (a) `I` was present in the store, (b) `I` was not reachable
> from any root's transitive import closure at the time deletion
> was attempted, and (c) the user explicitly authorized
> deletion via `--execute` while `ROOTS` was non-empty.

The first three properties are preserved: GC does not change
what a `get` returns for a surviving identity; it does not write
anything except the `GC.LOG`; and re-running GC on the same state
is a no-op (idempotent).

**Race safety:**

- GC reads `ROOTS`, walks its transitive import closure, and then
  deletes entries not in the closure. If a concurrent `put` adds
  an entry during that window, GC deletes it if it wasn't in the
  closure at closure-computation time. This is a TOCTOU race:
  the put landed, but GC treats it as garbage because no root
  points at it.
- **Mitigation:** GC takes a file lock on `<store_root>/LOCK`
  for the duration of the run. Concurrent writes wait; concurrent
  reads are unaffected (reads are hash-verified on bytes, which
  the GC hasn't deleted yet during its scan phase).
- **Alternative mitigation:** don't lock; accept the race as
  user responsibility ("don't run GC while writing"). Simpler,
  but less safe.
- **Recommendation:** file lock. The complexity cost is small
  (half a dozen lines), the safety benefit is real.

## Implementation shape

Pseudocode for the algorithm:

```python
def gc(store_root, execute=False):
    roots = read_roots(store_root / "ROOTS")
    if not roots:
        raise GCError("ROOTS file is empty or missing; refusing to GC")
    with file_lock(store_root / "LOCK"):
        all_identities = set(iter_identities(store_root))
        reachable = transitive_closure(store, roots)
        unreachable = all_identities - reachable
        if not execute:
            print_dry_run(unreachable)
            return
        for identity in unreachable:
            bytes_freed += delete(identity)
            append_log(store_root / "GC.LOG", identity)
        print_executed(bytes_freed, len(unreachable))
```

`transitive_closure(store, roots)` is a BFS: for each root,
fetch the module's canonical form, read its `imports` map, add
each import identity to the frontier, repeat until the frontier
is empty. Already tested logic — the import resolution path in
`_ResolvedImports.from_module` does exactly this walk today.

CLI shape:

- `codifide store gc` — dry-run.
- `codifide store gc --execute` — actual deletion.
- `codifide store roots add <identity>` — convenience for
  editing `ROOTS`.
- `codifide store roots list` — print current roots.
- `codifide store roots remove <identity>` — remove a root.

No changes to the on-disk layout beyond the two new files
(`ROOTS`, `GC.LOG`, `LOCK`).

## Follow-on implementation tasks

If Douglas approves this design, a future session implements:

1. `ROOTS` file reading (format, validation, error messages).
2. `file_lock` utility around the store root.
3. `transitive_closure` helper reusing import-resolution
   machinery.
4. `SymbolStore.gc(execute=False)` method returning a report.
5. `codifide store gc` subcommand and the `store roots` family.
6. Tests:
   - Dry run prints but doesn't delete.
   - `--execute` without `ROOTS` refuses.
   - Identity in `ROOTS` is preserved; unreferenced identity
     is deleted.
   - Transitive closure through indices resolves correctly.
   - Concurrent `put` during GC does not lose the new object
     (file lock test).
   - `GC.LOG` append is atomic and survives across runs.
7. Documentation: `docs/STORE.md` (new), `docs/CANONICAL.md`
   §Symbol store gains a "Garbage collection" subsection.

Expected size: ~250 lines of Python, ~200 lines of tests, ~100
lines of documentation.

## What I'm asking Douglas to decide

- **Approve the design as written** — a future session implements it.
- **Approve with modifications** — note the modifications and I
  re-issue the design.
- **Reject** — reject the approach; either keep monotonic growth
  as v0 policy or propose a different shape (e.g. time-based
  GC, which I recommended against above).

## What I'm not yet sure of

- Whether `ROOTS` should be a single file or a directory of
  named root files (`ROOTS/personal`, `ROOTS/project-foo`).
  Single file is simpler; directory scales to multi-project
  stores. I recommend single file for v0.x and revisit if
  multi-root complexity emerges.
- Whether GC should run implicitly on any `put` (amortized over
  time) or stay explicit. I recommend explicit — implicit GC
  makes `put` potentially destructive, which violates the
  mental model.
- Whether `GC.LOG` should record pre-deletion bytes (for
  recovery) or just identities (for audit). I recommend just
  identities — recording pre-deletion bytes defeats the point
  of GC by keeping the bytes.
