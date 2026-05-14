# V3-3 — Refusal Reasons

**Date:** 2026-05-14  
**Persona:** Quill  
**Trigger:** V3-3 item from the v3.0 roadmap; V3-2 shipped

---

## What shipped

`bottom` gains an optional string payload: `bottom "reason"`. The change is
additive and backward-compatible — bare `bottom` nodes produce identical
canonical bytes to the pre-V3-3 form.

### Python parser (`codifide/parser/expr_parser.py`)

`bottom` followed by a string token is parsed as `BottomExpr(reason=...)`.
Bare `bottom` parses as `BottomExpr(reason=None)` — unchanged.

### Python core types (`codifide/core/types.py`)

- `BottomExpr` gains `reason: Optional[str] = None`.
- New `BottomWithReason` class subclasses `_BottomType` so `isinstance(x, _BottomType)` catches both bare `Bottom` and reasoned refusals. Overrides `__new__` to avoid the singleton pattern.

### Python interpreter (`codifide/runtime/interpreter.py`)

- `BottomExpr` evaluation returns `BottomWithReason(reason)` when a reason is present, `Bottom` otherwise.
- All `is Bottom` / `is not Bottom` identity checks replaced with `isinstance(x, _BottomType)` so reasoned refusals are handled identically to bare ones.
- `RefusalError` raised with `reason=result.reason` when the escaping bottom carries a reason.

### Python errors (`codifide/runtime/errors.py`)

`RefusalError` gains `reason: Optional[str]` field. The error message includes `Reason: <reason>` when present.

### Python primitives (`codifide/runtime/primitives.py`)

`is_bottom` primitive updated to use `isinstance(x, _BottomType)` so it returns `true` for both bare and reasoned refusals.

### Canonical JSON/CBOR (`codifide/projection/canonical.py`)

- `_expr_to_json`: emits `"reason"` key only when present. Bare `bottom` → `{"kind":"bottom"}` (unchanged).
- `_expr_from_json`: reads optional `"reason"` field.

### Capability manifest (`codifide/capability.py`)

`bottom` AST kind updated: description mentions the optional `reason` field; `fields` list gains `{"name": "reason", "type": "string", "optional": True}`.

### Rust AST (`crates/codifide-canonical/src/ast.rs`)

`Bottom` variant gains `reason: Option<String>`.

### Rust JSON (`crates/codifide-canonical/src/json.rs`)

`expr_to_json`: emits `reason` only when `Some`. `expr_from_json`: reads optional `reason`.

### Rust expr parser (`crates/codifide-interpreter/src/parser/expr_parser.rs`)

`bottom` followed by a `Str` token is parsed as `Expr::Bottom { reason: Some(...) }`.

### Rust value (`crates/codifide-interpreter/src/value.rs`)

`Value::Bottom` gains `reason: Option<String>`. All match arms updated to `Bottom { .. }` or `Bottom { reason }`.

### Rust errors (`crates/codifide-interpreter/src/errors.rs`)

`Error::Refusal` gains `reason: Option<String>`. Display includes reason when present.

### Rust interpreter (`crates/codifide-interpreter/src/interpreter.rs`)

`Expr::Bottom { reason }` evaluates to `Value::Bottom { reason: reason.clone() }`. Top-level refusal check uses `if let Value::Bottom { reason }` to pass reason to `Error::Refusal`.

---

## Tests

24 new tests in `tests/test_bottom_reason.py`:

- **Parser (6):** bare bottom, `bottom "reason"`, empty reason, reason in source, bare in source, reason in believe else arm
- **Canonical (8):** bare bottom has no reason key, reason included when present, round-trips for both, from_canonical bare and with reason, module round-trip, bare bottom hash unchanged
- **Interpreter (7):** bare bottom raises RefusalError with reason=None, reasoned bottom raises with reason, error message includes reason, handled in believe, reason propagates through nested call, BottomWithReason is falsy, isinstance check
- **Capability (3):** reason field present, optional flag, description mentions reason

---

## Backward compatibility

Bare `bottom` nodes produce identical canonical bytes. All existing programs
behave identically. The `reason` field is purely additive.

---

## Tests at close

383 passing, 0 skipped (359 + 24 new).

---

*Filed by: Douglas Jones + Claude*
