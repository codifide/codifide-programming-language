# T2-1 + T2-2 — Capability Manifest Endpoint Live

**Date:** 2026-05-13  
**Persona:** Quill  
**Initiative:** Agent Adoption — Track 2, Tasks T2-1 and T2-2

---

## What happened

T2-1 and T2-2 completed in one pass. The capability manifest is now live at
stable public URLs, accessible to any agent without cloning the repo.

## What's live

**`https://www.codifide.com/capability.json`**
- 12.8 KB JSON
- `Content-Type: application/json; charset=utf-8`
- `Cache-Control: public, max-age=3600`
- `Access-Control-Allow-Origin: *` (CORS open — agents need this)
- Manifest hash: `sha256:713d6f6b3a6cfb747cec3bfba0f25331c61b0052bdd166523c175daa2c1f6756`
- Includes `is_bottom` note field (T2-9 work)

**`https://www.codifide.com/capability.cbor`**
- 6.4 KB CBOR (50% of JSON size)
- `Content-Type: application/cbor`
- Same cache and CORS headers

## What changed

**publicsite:**
- `capability.json` and `capability.cbor` added as static files
- `vercel.json`: specific routes for both files added before the catch-all
  rewrite (without this, the catch-all would serve `index.html` for both URLs)
- Correct `Content-Type` headers set per file type
- Deployed to production via `vercel --prod`

## Verification

Both endpoints return HTTP 200 with correct Content-Type. The live JSON
manifest contains 57 primitives, the `is_bottom` note field, and the correct
capability schema version. The CBOR file is served as `application/cbor`.

## What this enables

Any agent can now bootstrap Codifide knowledge with a single HTTP request:

```bash
curl https://www.codifide.com/capability.json
curl https://www.codifide.com/capability.cbor
```

No repo clone required. No Python installation required. The manifest is the
language's interface — it's now at a stable URL that won't change between
sessions.

## One note on cache

`max-age=3600` (1 hour) is intentionally short. The manifest changes with
every language release. A longer TTL would mean agents cache a stale manifest
after a release. When the language stabilizes, this can be extended.
