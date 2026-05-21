# Multiple `when` Clauses — Parser Fix

**Date:** 2026-05-18  
**Persona:** Quill  
**Gate:** G4 (Build and Verify) — parser change, HIGH risk classification

---

## What happened

While implementing the parking sign classifier, discovered that multiple `when`
clauses on a single candidate silently dropped all but the last one. This is a
fidelity violation — the language was losing information an agent explicitly
declared.

Douglas approved the fix: multiple `when` clauses are now implicitly ANDed,
matching the behavior of `pre` and `post` (all enforced). Both the Python and
Rust parsers were updated.

---

## What shipped

**Multiple `when` clause support** in both parsers:

- **Python** (`codifide/parser/parser.py`): Changed `guard` variable from
  `Optional[Expr]` to `guards: List[Expr]`. Appends each `when` expression.
  At candidate construction: 0 guards → `None`, 1 guard → direct expression,
  2+ guards → `Call(fn="and", args=tuple(guards))`.

- **Rust** (`crates/codifide-interpreter/src/parser/mod.rs`): Same change.
  `guard: Option<Expr>` → `guards: Vec<Expr>`. Combined at the end with
  `Expr::Call { fn_: "and", args: guards }`.

- **Canonical form unchanged.** Multi-when emits `and(g1, g2, ...)` as the
  single guard expression. No new AST node. No canonical form change. No
  existing content hash invalidated.

---

## Why this matters for agents

1. **Agents think in constraints.** They naturally write one condition per line.
   Forcing `and(cond1, cond2)` is a human-syntax concession.

2. **Silent data loss is the anti-pattern Codifide exists to prevent.** A parser
   that silently drops earlier `when` clauses is a fidelity violation.

3. **Consistency with `pre`/`post`.** Multiple `pre` clauses are all enforced.
   Multiple `post` clauses are all enforced. `when` now behaves the same way.

4. **bind-before-when detection still works.** If a bind appears before any
   `when` clause, the parser raises `ParseError` — regardless of how many
   `when` clauses follow.

---

## Test results

9 new tests in `tests/test_multi_when.py`:
- `SingleWhenUnchanged` (2 tests): existing behavior preserved
- `MultiWhenImplicitAnd` (5 tests): multi-when semantics verified
- `MultiWhenBindBeforeWhenDetection` (2 tests): safety check preserved

Rust conformance: 3 tests passing (Python and Rust produce identical canonical JSON).

Full suite: **483 tests passing** (Python), 24 Rust canonical tests passing.

---

## What I'm not yet sure of

Whether the `and()` primitive short-circuits. If the first condition is false,
does `and()` still evaluate the second? Looking at the primitives, `and` is
implemented as `lambda a, b: bool(_unwrap(a)) and bool(_unwrap(b))` — Python's
`and` short-circuits, so yes, it does. But the guard evaluation in `_dispatch`
evaluates the entire guard expression as one unit. For the multi-when case,
this means all conditions are evaluated via the `and()` call, which does
short-circuit internally. This is correct behavior.
