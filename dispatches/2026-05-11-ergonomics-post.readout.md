# Ergonomics pass — post-fix readout (2026-05-11)

Four external model reviews landed on 2026-05-11. Two succeeded at
writing Codifide; two didn't. This pass addresses the three causes of
failure without drifting the language's thesis toward "Python with
intent annotations."

The decisions that drove this pass are recorded separately in
`dispatches/2026-05-11-ergonomics-decisions.{readout.md,yaml}`. This
readout reports what shipped.

## What shipped

1. **Parser accepts multi-line expressions inside `cand`, `pre`,
   `post`, `when`, and bind right-hand sides.** Line continuation
   runs while brackets are unbalanced, stops at the next keyword
   head, and raises a clean `ParseError` if brackets never
   balance. The previous `AttributeError` that leaked out of
   `expr_parser.parse_atom` on EOF is now an `ExprParseError`
   wrapped in `ParseError` — typed-error discipline restored.
2. **`reverse` is polymorphic over strings and lists.** Same
   primitive, same name. `reverse("abc")` → `"cba"`,
   `reverse([1,2,3])` → `[3,2,1]`. Establishes the rule for
   primitive design: polymorphism is allowed when semantics
   transfer cleanly and return shape is unambiguous.
3. **Hint messages for three common-guess misses.** The `%`
   operator now produces a `ParseError` that names `mod(a, b)`.
   Unknown callables like `str.reverse` and `clock.hour` produce
   a `CodifideError` whose hint names the correct primitive form.
   The base error messages are unchanged so existing substring
   matches keep working.
4. **`docs/AGENT_QUICKREF.md`.** One page, distilled from the
   capability manifest. Listed from `README.md §For agents` and
   `docs/FOR_AGENTS.md §60 seconds`.
5. **Spec updates in `docs/LANGUAGE.md`.** New section on line
   continuation. New section on primitive polymorphism. Closes
   the spec-implementation gap Sable flagged in her audit of
   this pass.
6. **Regression tests.** Gemini's `palindrome.cod` and
   `classify_numeric.cod` are committed as parser tests. The
   multi-line bind case, the unbalanced-brackets `ParseError`
   case, the `%` hint, and the `str.reverse` / `clock.hour`
   hints all have tests. Suite is 129/129 (was 122/122; +7).

## What we refused to ship

Three requests came through the reviews that the language
declined to satisfy, each for a specific reason recorded in the
paired decisions dispatch:

- **Infix `%` as sugar for `mod`.** Opens the door to `+`, `-`,
  `*`, `/` without semantic justification. Comparison infix is a
  calculated exception for contract legibility; arithmetic is not.
  Fix: better error, not more surface.
- **Inline `if`/`when` as statement-level conditional.** Codifide's
  conditional dispatch is a candidate-level construct. Two paths to
  the same destination is exactly the drift we resist.
- **A separate `str_reverse` primitive.** Subsumed by polymorphic
  `reverse`.

## What this is and isn't

This is ergonomics. It is not a language change. The canonical
form is unchanged, the effect algebra is unchanged, the contract
semantics are unchanged, the content-addressed identity model is
unchanged. An external agent rewriting Codifide from the
specification alone would produce the same manifest plus a
different `reverse` return-type annotation.

The capability manifest hash moved from
`sha256:522c48d0dfd60c8c6d7528711c5624560fcabead76d9e80a4a782954e01a92f1`
to
`sha256:845dbbbff6b8ba8957dc40383e9a54b386b172f8fa70ccc16a18be10e498afd4`.
The delta is the `reverse` return type (`"List"` → `"Any"`); nothing
else changed. `docs/capability-0.1.json` has been refreshed.

## Test count

- Python: 129/129 passing (122 previous + 5 multi-line parser
  regressions + 2 hint regressions).
- Rust canonical: 10/10 passing. No changes to the Rust crate.

## What I'm not yet sure of

Whether the quickref actually shortens the time-to-first-working-
program for a fresh agent. The honest way to find out is to hand the
next external model the repo with no coaching and re-run the same
task battery. I have not done that experiment; this readout is
about what shipped, not about what it accomplished.
