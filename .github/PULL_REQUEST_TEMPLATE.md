## What this PR does

<!-- One paragraph summary of the change. -->

## Type of change

- [ ] Bug fix (no observable behavior change)
- [ ] New example or test (additive, no dispatch required)
- [ ] Documentation fix (no spec change)
- [ ] Language change (new primitive / AST kind / effect / syntax — dispatch required)
- [ ] Spec change (changes to CANONICAL.md, CAPABILITY.md, or conforming behavior)

## Checklist

- [ ] `python3 -m pytest tests/ -q` — all tests pass, 0 skipped
- [ ] `python3 -m codifide dispatch-check` exits 0 (if dispatches were filed)
- [ ] Capability manifest regenerated if public surface changed (`python3 -m codifide capability > docs/capability-0.1.json`)
- [ ] New behavior has tests
- [ ] Commit messages are imperative mood

## For language changes

- [ ] G0 problem statement filed in `.kiro/specs/`
- [ ] G1 requirements with acceptance criteria
- [ ] Paired Quill readout + Glyph dispatch in `dispatches/`
- [ ] Sable audit completed (if security-adjacent)

## Related issues / dispatches

<!-- Link any related issues, discussions, or dispatch files. -->
