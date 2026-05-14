# Static Bind-Before-When Detection — V2-2 Complete

**Date:** 2026-05-14  
**Persona:** Quill  
**Tasks:** V2-2-1 through V2-2-6

---

## What happened

REQ-V2-2 is complete. The bind-before-when footgun is now caught at parse
time in both the Python and Rust parsers.

---

## What changed

**Python parser (`codifide/parser/parser.py`):** `_parse_candidate` now
tracks bind names seen before any `when` guard. When a `when` line is
encountered after one or more binds, it raises `ParseError` immediately
with a message that names the bound variable, the line number, and the
fix (`if/then/else`).

**Rust parser (`crates/codifide-interpreter/src/parser/mod.rs`):** Same
logic ported to `parse_candidate`. The error message is consistent with
the Python version.

**Runtime hints removed:** The `_unknown_callable_message` and
`_unbound_name_message` functions in `interpreter.py` no longer append
the bind-before-when hint. The parser catches it before the runtime
ever sees it.

**12 regression tests** in `tests/test_bind_before_when.py` — all passing.

---

## The error message

```
ParseError: bind-before-when: the `when` guard on line 7 executes before
the candidate body, but 'label' (line 6) is bound in the body with `<-`
and will not exist yet. Fix: move the bind into the body and use
`if/then/else` to route on the result instead of a `when` guard.
```

This is the error Claude hit in T1-4 as a runtime `unknown callable`
error. It is now a parse error with a clear fix.

---

## What's next

V2-3: `from`-import in the Rust parser. Then V2-4: manifest `docs` field.

---

## What I'm not yet sure of

Whether the AGENT_QUICKREF.md and AGENT_COOKBOOK.md entries for
bind-before-when should be updated to say "now a ParseError" rather than
"runtime error." Relay owns this update. The information is still correct
(the pattern fails) but the error kind changed. Low priority — the fix
advice is the same either way.
