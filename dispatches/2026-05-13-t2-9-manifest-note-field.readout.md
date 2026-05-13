# T2-9 — Capability Manifest Note Field

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 2, Task T2-9

---

## What happened

Added a `note` field to the capability manifest's primitive schema. The first
use is the `is_bottom()` caveat surfaced by Sable in the Track 1 audit
(AUD-T1-01).

## What changed

**`codifide/runtime/primitives.py`**
- `PrimitiveSpec` dataclass: added `note: Optional[str] = None`
- `PrimitiveRegistry.register()`: added `note` parameter
- `is_bottom` registration: added the caveat note explaining it cannot catch
  propagated `bottom`

**`codifide/capability.py`**
- `_primitives()`: includes `note` in the manifest entry when present

**`docs/capability-0.1.json`**
- Regenerated. New manifest hash:
  `sha256:713d6f6b3a6cfb747cec3bfba0f25331c61b0052bdd166523c175daa2c1f6756`
  (was `sha256:23fdde779caebc2c471ade0e1c407422d044e2e0f1adc7e59a189325deccd27d`)

**`docs/CAPABILITY.md`**
- Added `note` field documentation to the Primitives section

## What this closes

AUD-T1-01 (P2): any agent reading only the capability manifest would fall into
the `is_bottom()` trap — the manifest listed it with no caveat. Now the manifest
itself carries the warning. An agent that reads `python3 -m codifide capability`
will see the note before writing any code that uses `is_bottom()`.

## What this enables

T2-1 (generate manifest files for the public endpoint) can now proceed. The
manifest that goes live at `codifide.com/capability.json` will carry the
`is_bottom()` note from day one.

## 289 tests passing, 0 regressions.
