---
name: Bug report
about: Something in the interpreter, parser, store, or CLI is not working correctly
title: '[bug] '
labels: bug
assignees: ''
---

## What happened

<!-- A clear description of the bug. -->

## Expected behavior

<!-- What you expected to happen. -->

## Reproduction

<!-- Minimal .cod program or CLI command that reproduces the issue. -->

```codifide
# paste your .cod program here
```

```bash
# or the CLI command
python3 -m codifide run ...
```

## Error output

```
# paste the full error message here
```

## Environment

- Codifide version: <!-- run: python3 -m codifide capability | python3 -c "import sys,json; print(json.load(sys.stdin)['generator'])" -->
- Python version: <!-- run: python3 --version -->
- OS:

## Additional context

<!-- Anything else that might be relevant. -->
