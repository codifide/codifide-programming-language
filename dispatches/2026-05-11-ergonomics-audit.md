# Sable — ergonomics-pass audit (2026-05-11)

Auditor: Sable
Scope: the four-model feedback batch dated 2026-05-11 and the decisions
filed against it in `dispatches/2026-05-11-ergonomics-decisions.{yaml,readout.md}`.

## Findings

### AUD-2026-05-11-01 — P1 — parser leaks host exception

**What.** The line-oriented outer parser hands `expr_parser.parse_expr`
a single physical line at a time. An expression whose bracket depth
does not balance on that line (e.g. a `list(...)` literal that wraps
to a second line) runs the inner parser off the end of its token
stream. `parse_atom` peeks without guarding for `None`, producing an
`AttributeError` that escapes the `parse() -> Module | ParseError`
contract.

**Probe.**
```
$ python3 -m codifide run examples/ai_generated/classify_numeric.cod
AttributeError: 'NoneType' object has no attribute 'kind'
```

**Why it matters.** Typed-error discipline is a design invariant.
Originally defended against by audit P1-1 (host exceptions in the
runtime) and P1-3 (`LexError` leaking through `_safe_parse_expr`).
This is the same class of bug in a new surface. A host embedding
Codifide will see `AttributeError` where it was promised `ParseError`.

**Severity.** P1. No data loss, no sandbox escape, no soundness
violation. But reachable from benign surface input and violates a
contract the project committed to. Fix before next release.

**Spec bug alongside it.** `docs/LANGUAGE.md` is silent on whether
a single expression may span multiple physical lines. Silence has
been interpreted as "one line." That is an arbitrary restriction
the spec does not actually commit to. Fix: say explicitly that
expressions may continue while brackets are unbalanced.

**Fix (authoring persona, not me).** Line-assembly pass inside
`_parse_candidate` and the pre/post/guard consumers. EOF-safe
`peek` in the expression parser.

### AUD-2026-05-11-02 — P2 — unknown-callable errors are uninformative

**What.** `interpreter._call` raises `CodifideError(f"unknown callable: {fn!r}")`
for any name that isn't a user def, an import, or a primitive.
The message does not suggest what the author might have meant.

**Probe.**
```
$ python3 -m codifide run examples/ai_generated/reverse.cod
CodifideError: unknown callable: 'str.reverse'
```

**Why it matters.** Agents that reach for `str.reverse`, `clock.hour`,
`str.upper`, etc. are common enough that two independent external
agents did it in one afternoon. The language knows the correct form.
An error that doesn't say so is a missed teaching moment.

**Severity.** P2. Doesn't break anything. Surfaces a usability gap
that has now been evidenced by four external reviews.

**Fix.** Keep the unknown-callable error. Add a one-line hint when
the misspelling matches a known-guess table.

### AUD-2026-05-11-03 — P3 — spec silent on primitive polymorphism

**What.** `reverse` is documented as a list primitive. Nothing in
the spec says whether a primitive may accept multiple input types.
Today, none do cleanly. The proposal to make `reverse` polymorphic
over string and list sets a precedent that should be written down.

**Severity.** P3. Soundness polish. Fix by adding a paragraph to
`docs/CAPABILITY.md` or `docs/LANGUAGE.md` describing the rule.

## What I did not test

- Whether the `AttributeError` in AUD-01 has other reachable paths
  beyond multi-line calls. Unbalanced brackets in `pre`/`post`/`when`
  almost certainly hit the same code path; I did not run it.
- Whether the Rust canonical crate produces a comparable error on
  the same canonical JSON the Python parser would produce (it
  doesn't parse surface, so probably not, but I did not check).
- Whether polymorphic `reverse` changes the capability manifest's
  content hash. The `returns` string in the manifest for `reverse`
  is `"List"`; a polymorphic primitive may want to move that to
  `"Any"` or introduce a `returns` variant. Either way, a manifest
  refresh is required and the drift test will force the question.
- Any stress test of the quickref's accuracy against the manifest
  after the polymorphism change lands.

## Post-audit expectations

- AUD-01 must be fixed in this session (P1).
- AUD-02 should be fixed in this session (decision 7 in the paired
  dispatch commits to it anyway).
- AUD-03 should be addressed in the same session where the
  polymorphism change lands.

A post-audit dispatch should confirm each of these with a reproducing
probe that now passes.
