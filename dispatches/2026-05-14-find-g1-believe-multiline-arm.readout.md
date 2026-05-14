# FIND-G1 — believe arm value on continuation line

**Date:** 2026-05-14  
**Persona:** Quill  
**Trigger:** Gemini 2.5 Pro v3.0 case study — P3 failure

---

## Finding

A `believe` arm whose value appears on the next indented line after `=>` failed
with `ParseError: unexpected end of expression`. The parser split each arm on
`=>` within a single physical line; a line ending with `=>` had an empty
right-hand side.

```codifide
# Previously failed — value on next line
believe label
  ge(conf(label), 0.0) =>
    if eq(label, "unsafe") then "blocked"
    else if eq(label, "safe") then "approved"
    else "escalate-to-human"
  else => bottom
```

This is a natural formatting choice when the arm value is a long
`if/then/else` expression. The error was not obvious from the docs.

---

## Fix

### Python parser (`codifide/parser/parser.py`)

`_parse_believe` updated: when the right-hand side of a `=>` arm is empty,
call `_gather_expr` on the next indented line to collect the value (including
multi-line `if/then/else` continuations). Same logic applied to `else =>` arms.

### Rust parser (`crates/codifide-interpreter/src/parser/mod.rs`)

`parse_believe` updated with the same logic: empty right-hand side after `=>`
triggers `gather_expr` on the next line.

### Documentation (`docs/AGENT_QUICKREF.md`)

Added to "Surface rules that surprised other agents":

> `believe` arm values must be on the same line as `=>` — OR on the next
> indented line. (After this fix, both work.)

Note: the quickref was updated to document the constraint before the fix was
confirmed. The fix makes the constraint moot — both forms now work.

### Tests (`tests/test_parser.py`)

3 regression tests added:
- `test_believe_arm_value_on_next_line` — simple value on next line
- `test_believe_arm_value_multiline_if_on_next_line` — multi-line if/then/else (Gemini's exact pattern)
- `test_believe_else_arm_value_on_next_line` — else arm value on next line

---

## Tests at close

386 passing, 0 skipped (383 + 3 new).

---

*Filed by: Douglas Jones + Claude*
