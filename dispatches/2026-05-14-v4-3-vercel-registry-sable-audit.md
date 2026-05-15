# Sable Audit — Vercel Registry (V4-3)

**Date:** 2026-05-14  
**Persona:** Sable  
**Scope:** `codifide/store/blob_store.py`, `publicsite/api/`, `publicsite/vercel.json`

---

## Audit scope

Three new surfaces:
1. `BlobStore` — Python class that reads/writes to Vercel Blob
2. Vercel serverless functions — `api/health.py`, `api/symbols/index.py`, `api/symbols/[identity].py`
3. `vercel.json` routing changes

---

## Findings

### AUD-VR-01 (P2) — `sys.path.insert` in serverless functions is fragile

**What:** `api/symbols/index.py` and `api/symbols/[identity].py` use
`sys.path.insert(0, ...)` to find the `codifide` package. This works when
the package is installed via `requirements.txt` but the path manipulation
is unnecessary and could break if Vercel changes its working directory.

**Fix:** Remove the `sys.path.insert` calls. The `requirements.txt` installs
`codifide` as a proper package, so `import codifide` works without path
manipulation.

**Severity:** P2 — fragile but not a security issue. Will cause silent
failures if the path assumption breaks.

**Resolution:** Applied — removed `sys.path.insert` calls from both files.

---

### AUD-VR-02 (P2) — `BlobStore.has()` catches all exceptions, masking errors

**What:** The `has()` method catches all exceptions and checks for "not found"
in the error string. This is fragile — a network error or auth failure would
return `False` instead of raising, causing `put()` to attempt an upload that
will also fail, with a confusing error.

**Fix:** Only catch `BlobNotFoundError` (or equivalent) from `vercel_blob`.
Let other exceptions propagate.

**Severity:** P2 — can mask real errors as "symbol not found."

**Resolution:** Applied — tightened exception handling in `has()`.

---

### AUD-VR-03 (P1) — Write token comparison is not constant-time

**What:** `api/symbols/index.py` compares the write token with `!=`. Python
string comparison is not constant-time, enabling timing attacks to enumerate
valid tokens character by character.

**Fix:** Use `hmac.compare_digest()` for the token comparison.

**Severity:** P1 — timing attack on the write token. Must fix before enabling
writes.

**Resolution:** Applied — replaced `!=` with `hmac.compare_digest()`.

---

### AUD-VR-04 (P3) — `vercel.json` catch-all may intercept `/symbols/` before function

**What:** The `"source": "/(.*)"` catch-all rewrite is listed after the
`/symbols/:path*` rewrite, which is correct. But Vercel processes rewrites
in order, so if the order is wrong, `/symbols/sha256:...` would serve
`index.html` instead of the function.

**Probe:** Verified the order in `vercel.json` — `/symbols/:path*` appears
before `/(.*)`). Order is correct.

**Severity:** P3 — already correct, but worth documenting.

**Resolution:** No change needed. Order is correct.

---

### AUD-VR-05 (P3) — `requirements.txt` pins `vercel_blob==0.3.0` but version may not exist

**What:** `vercel_blob==0.3.0` is pinned. If this version doesn't exist on
PyPI, the Vercel build will fail.

**Fix:** Verify the version exists, or use `vercel_blob>=0.3.0` with a
comment explaining the minimum version requirement.

**Severity:** P3 — build-time failure, not a security issue.

**Resolution:** Applied — changed to `vercel_blob>=0.3.0` with a note.

---

## What I did not test

- Whether `vercel_blob.head()` raises `BlobNotFoundError` specifically or a
  generic exception — the error handling in `has()` depends on this.
- Whether the Vercel function bundle size stays under 500 MB with the
  `codifide` package included.
- Whether the `git+https://` dependency in `requirements.txt` works in
  Vercel's build environment (it should, but pip's git support requires git
  to be installed in the build image).

---

## Overall assessment

Two P2 findings and one P1 finding. The P1 (timing attack on write token)
must be fixed before enabling writes. The P2 findings are fragility issues
that should be fixed before production. The P3 findings are documentation
gaps. All findings are applied in this session.
