# V4-3 Vercel Registry — Complete

**Date:** 2026-05-14  
**Persona:** Quill

---

## What happened

The public registry was redesigned from Fly.io (persistent process) to
Vercel Blob (persistent store). The user's architecture analysis was correct:
persistent store first, long-running server second. Vercel Blob is the right
backing store — it's already in the user's account, it's durable across
restarts and deployments, and it works with Vercel's serverless functions.

## What shipped

**`codifide/store/blob_store.py`** — `BlobStore` class. Same interface as
`SymbolStore`. Reads/writes symbols to Vercel Blob using the `vercel_blob`
Python package. Hash-verifies every read. Idempotent writes. Optional
dependency (`pip install codifide[blob]`).

**`publicsite/api/health.py`** — `GET /health` serverless function.

**`publicsite/api/symbols/index.py`** — `POST /symbols` serverless function.
Write-protected by `REGISTRY_WRITE_TOKEN` with constant-time comparison
(AUD-VR-03 applied).

**`publicsite/api/symbols/[identity].py`** — `GET /symbols/<hash>` and
`GET /symbols/<hash>/imports` serverless functions. Public reads, no auth.

**`publicsite/vercel.json`** — updated routing: `/health` and `/symbols/*`
route to the new functions before the catch-all.

**`publicsite/requirements.txt`** — `vercel_blob>=0.3.0` and `codifide`
from GitHub.

**`docs/DEPLOY_VERCEL.md`** — step-by-step Vercel deploy guide.

**`pyproject.toml`** — `[project.optional-dependencies] blob = [vercel_blob>=0.3.0]`.

## Sable findings applied

- AUD-VR-01 (P2): Removed `sys.path.insert` from serverless functions
- AUD-VR-02 (P2): Tightened exception handling in `BlobStore.has()`
- AUD-VR-03 (P1): Constant-time token comparison with `hmac.compare_digest()`
- AUD-VR-05 (P3): Changed `vercel_blob==0.3.0` to `>=0.3.0`

## What's left for you (3 steps)

1. Create a Vercel Blob store in your project dashboard (Storage → Create Database → Blob)
2. Set `REGISTRY_WRITE_TOKEN` in Vercel environment variables
3. Push the publicsite repo — Vercel deploys automatically

Then seed: `./scripts/seed_registry.sh --registry https://codifide.com`

## What I'm not yet sure of

Whether `vercel_blob.head()` raises a typed `BlobNotFoundError` or a generic
exception. The `has()` method checks the exception class name and message —
this should work but hasn't been tested against a live Vercel Blob store.
If it fails, the fix is to check the specific exception type from the
`vercel_blob` package.
