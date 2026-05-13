# Contributing to Codifide

Codifide is MIT licensed and accepts contributions. This document covers the practical steps.

For the full governance model — stewardship, spec-change process, personas, forks — see `GOVERNANCE.md`.

## Before you start

- Read `README.md` and `GETTING_STARTED.md` to understand the project.
- If you are an AI agent, start with `docs/FOR_AGENTS.md` and `docs/AGENT_QUICKREF.md`.
- Run the test suite to confirm your environment is clean:
  ```bash
  python3 -m codifide test
  ```
  All 289 tests should pass.

## Types of contributions

### Additive contributions (no dispatch required)
- New example programs in `examples/`
- New tests in `tests/`
- Documentation fixes and clarifications that do not amend the spec
- Bug fixes that do not change observable language behavior

These merge on the usual basis: tests pass, code matches the house style, existing examples still run.

### Language changes (dispatch required)
Any change that affects the capability manifest — new primitives, new AST kinds, new error classes, new effect labels, new surface syntax — requires:

1. A proposal as a paired Quill readout (`.readout.md`) and Glyph dispatch (`.yaml`) in `dispatches/`.
2. An adversarial Sable audit if the change touches security-adjacent surface (the store, the parser, the effect checker).
3. Approval from Douglas Jones on the spec amendment.

See `GOVERNANCE.md §Decision-making` for the full process.

### Spec changes
Changes to `docs/CANONICAL.md`, `docs/CAPABILITY.md`, or any other file that defines conforming behavior follow the same process as language changes above.

## How to submit

1. Fork the repository.
2. Create a branch from `main`.
3. Make your changes. Run `python3 -m codifide test` — all tests must pass.
4. If your change adds new language surface, run `python3 -m codifide dispatch-check` to confirm dispatch pairs are complete.
5. Open a pull request with a clear description of what changed and why.

## Code style

- Python: follow the existing style. No external formatter is enforced, but match the surrounding code.
- Rust: `cargo fmt` before committing.
- Documentation: plain, precise language. No marketing copy in spec files.
- Commit messages: imperative mood, one line summary, detail in the body if needed.

## Tests

Every new primitive, AST kind, or behavior change needs a test. The test suite lives in `tests/`. Look at existing tests for the pattern — most are short `.cod` fixture programs run through the interpreter with an expected output or error.

## Questions

Open an issue in the repository. For trademark or commercial licensing questions, contact Codifide Inc. directly via [codifide.com](https://www.codifide.com).
