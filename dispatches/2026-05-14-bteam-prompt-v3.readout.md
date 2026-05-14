# B-Team Prompt Update — v3.0

**Date:** 2026-05-14  
**Persona:** Quill  
**Trigger:** v3.0 closed; prompt needs updating before next case study

---

## What changed

`docs/GPT4O_PROMPT.md` updated from v2.0 to v3.0.

### Title
`T1-2 (updated for v2.0)` → `T1-2 (updated for v3.0)`

### Version string
`__version__` bumped from `1.0.0` to `3.0.0` (was never bumped for v2.0 — corrected now).
`docs/capability-0.1.json` regenerated. `dispatches/INDEX.md` regenerated.

### Manifest hash
`sha256:42d73647...` → `sha256:d900fe7e...`

### Generator
`codifide-python-2.0.0` → `codifide-python-3.0.0`

### RESOURCE 2 — surface rules

Added `bottom "reason"` entry:
> `bottom "reason"` (v3.0). `bottom` accepts an optional string payload. The reason is propagated through `RefusalError` for diagnostics. Bare `bottom` still works.

### RESOURCE 2 — `is_bottom` note

Updated to mention "with or without a reason string" — `is_bottom` returns true for both.

### RESOURCE 2 — content-addressed imports

RPC API section updated to `v2.0+`. New V3-2 remote symbol resolution section added:
- `codifide store push sha256:<hash> --registry <url>`
- `codifide run <file> --registry <url>`
- `codifide serve --read-only`

### Manifest JSON block

`is_bottom` primitive entry updated with `note` field documenting reason-string behavior.

---

## What was NOT changed

- Task spec (Programs 1–5) — unchanged; still the right test surface
- FOR_AGENTS.md section — unchanged
- Primitive table — no new primitives in v3.0
- Surface keyword table — unchanged

---

*Filed by: Douglas Jones + Claude*
