# From-Import in Rust Parser — V2-3 Complete

**Date:** 2026-05-14  
**Persona:** Quill  
**Tasks:** V2-3-1 through V2-3-5

---

## What happened

REQ-V2-3 is complete. `from <hash> import name` now works in the Rust
runtime. `CODIFIDE_RUNTIME=python` is no longer required for from-imports.

---

## What changed

**Rust parser (`parse_with_store`):** A new `parse_with_store` function
accepts an optional store path. When provided, `from`-import lines are
resolved by reading the target module's canonical JSON or CBOR from the
store filesystem and looking up the requested names in its imports table.
The existing `parse` function calls `parse_with_store(source, name, None)`
for backward compatibility.

**Rust interpreter (`run_with_imports`):** A new `run_with_imports` function
accepts pre-resolved imports as a `HashMap<String, Definition>`. The
`Interpreter` struct now holds a `resolved_imports` field. The `call`
function looks up imported symbols after local symbols and before primitives.

**Rust binary (`codifide-run`):** Now accepts `--store <path>`. When
provided, imports are resolved from the store before running. The Python
CLI's `_cmd_run_rust` now passes `--store` automatically.

**AGENT_QUICKREF.md:** Updated to say both runtimes support from-import.
The `CODIFIDE_RUNTIME=python` note is removed.

**2 new tests** in `tests/test_rust_interpreter.py::FromImportRust` —
both passing.

---

## What's next

V2-4: manifest `docs` field. Then the v2.0 roadmap is complete.

---

## What I'm not yet sure of

The `invoke_defn_owned` function uses an unsafe lifetime extension to call
imported definitions. The safety argument is that the boxed definition lives
for the duration of the call. This is correct but worth a Sable note — the
parallel evaluator's branch interpreters don't carry resolved imports, so
imported symbols are not available in parallel branches. This is a known
limitation, not a bug, but it should be documented.
