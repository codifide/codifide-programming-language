# Manifest Docs Field — V2-4 Complete

**Date:** 2026-05-14  
**Persona:** Quill  
**Tasks:** V2-4-1 through V2-4-5

---

## What happened

REQ-V2-4 is complete. The capability manifest now has a `docs` field.
An agent that fetches `codifide.com/capability.json` can now discover
the cookbook, quickref, and onboarding guide without reading the README.

---

## What changed

**`codifide/capability.py`:** `generate_capability()` now includes a
`docs` field with stable URLs for `for_agents`, `quickref`, `cookbook`,
`capability`, and `capability_cbor`.

**`docs/CAPABILITY.md`:** Schema documentation updated with the `docs`
field shape and key descriptions.

**`docs/capability-0.1.json`:** Regenerated. New manifest hash:
`sha256:42d73647ba8de29a7d219bf2218bad0a42dc2a11d7878cac12ee931be2a1a185`

**publicsite:** `capability.json` and `capability.cbor` updated.

**`tests/test_capability.py`:** New test `test_docs_field_has_required_keys`
verifies `for_agents`, `quickref`, and `cookbook` are present and are
HTTPS URLs.

---

## What's next

All four v2.0 requirements are complete. The v2.0 roadmap is done.

Next: session close, commit, push. Then update the session state file.

---

## What I'm not yet sure of

Whether the publicsite needs a Vercel deployment to serve the updated
manifest. The files are updated locally; a push to the publicsite repo
and a Vercel deploy would make them live. That's a separate step.
