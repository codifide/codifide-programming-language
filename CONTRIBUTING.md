# Contributing to Codifide

Codifide is MIT licensed and welcomes contributions. This document covers
the practical steps. For the full governance model — stewardship, spec-change
process, personas, forks — see `GOVERNANCE.md`.

## Before you start

- Read `README.md` and `GETTING_STARTED.md` to understand the project.
- If you are an AI agent, start with `docs/FOR_AGENTS.md` and `docs/AGENT_QUICKREF.md`.
- Run the test suite to confirm your environment is clean:
  ```bash
  pip install -e .
  python3 -m pytest tests/ -q
  ```
  All 450 tests should pass, 0 skipped.

## Types of contributions

### Additive contributions (no dispatch required)

- New example programs in `examples/`
- New tests in `tests/`
- Documentation fixes that do not amend the spec
- Bug fixes that do not change observable language behavior

These merge on the usual basis: tests pass, code matches the house style,
existing examples still run.

### Language changes (dispatch required)

Any change that affects the capability manifest — new primitives, new AST
kinds, new error classes, new effect labels, new surface syntax — requires:

1. A G0 problem statement (see `GOVERNANCE.md §Gates`)
2. A G1 requirements document with acceptance criteria
3. A paired Quill readout (`.readout.md`) and Glyph dispatch (`.yaml`) in
   `dispatches/` for each significant decision
4. A Sable adversarial audit if the change touches security-adjacent surface
   (the store, the parser, the effect checker, the RPC server)
5. All tests passing, 0 skipped
6. `python3 -m codifide dispatch-check` exits 0

See `GOVERNANCE.md` for the full seven-gate process.

### Spec changes

Changes to `docs/CANONICAL.md`, `docs/CAPABILITY.md`, or any file that
defines conforming behavior follow the same process as language changes.

## How to submit

1. Fork the repository.
2. Create a branch from `main`.
3. Make your changes.
4. Run `python3 -m pytest tests/ -q` — all tests must pass.
5. If your change adds new language surface, run
   `python3 -m codifide dispatch-check` to confirm dispatch pairs are complete.
6. Open a pull request with a clear description of what changed and why.

## Governance process

Codifide uses a seven-gate stage-gate process for all language changes:

| Gate | Question |
|------|----------|
| G0 | Is this worth exploring? |
| G1 | Are the requirements strong enough? |
| G2/G3 | Is the design ready? |
| G4 | Build and verify. |
| G5 | Release readiness. |
| G6 | Post-release review. |

Every gate requires evidence, not confidence. "We think it's fine" is not a
gate pass. See `GOVERNANCE.md` and `.kiro/steering/01-governance-gates.md`
for the full criteria.

## Dispatch discipline

Every significant decision is recorded as a paired dispatch:

- `dispatches/<date>-<slug>.readout.md` — Quill (human-readable)
- `dispatches/<date>-<slug>.yaml` — Glyph (agent-readable, structured)

Run `python3 -m codifide dispatch-check` before ending any session that
filed dispatches. It exits non-zero if any pairs are incomplete.

## Code style

- **Python:** match the surrounding code. No external formatter enforced.
- **Rust:** `cargo fmt` before committing.
- **Documentation:** plain, precise language. No marketing copy in spec files.
- **Commit messages:** imperative mood, one-line summary, detail in body if needed.
- **Tests:** every new primitive, AST kind, or behavior change needs a test.
  Look at `tests/` for the pattern.

## Three-persona review

Language changes go through three independent reviews:

- **Sable** (A-Team auditor) — adversarial soundness, security, conformance
- **B-Team** (different AI model) — finds what the builders missed
- **Zero-Context reviewer** — reads the artifact as a new contributor would

See `.kiro/steering/04-adversarial-review.md` for how to run each.

## Questions

Open a [Discussion](https://github.com/codifide/codifide-programming-language/discussions)
for questions, ideas, and show-and-tell. For security vulnerabilities, see
`SECURITY.md`. For trademark or commercial licensing, contact Codifide Inc.
via [codifide.com](https://www.codifide.com/#contact).
