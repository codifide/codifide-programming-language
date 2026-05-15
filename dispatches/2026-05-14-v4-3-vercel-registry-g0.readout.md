# V4-3 Vercel Registry — G0 Problem Statement

**Date:** 2026-05-14  
**Persona:** Quill  
**Initiative:** V4-3 (public registry) — Vercel Blob backend

---

## Problem

The Fly.io deployment built earlier requires a new account and a persistent
process. The user already has a Vercel account. The architecture review
(user + team) confirmed: persistent store first, long-running server second.
Vercel Blob is the right persistent store — it's object storage backed by
Vercel's CDN, accessible from serverless functions, and already in the
user's account.

## Scope

Replace the Fly.io deployment plan with a Vercel-native deployment:

1. **`BlobStore`** — a new store backend in `codifide/store/blob_store.py`
   that reads/writes symbols to Vercel Blob using the REST API directly
   (no new Python dependencies — stdlib `urllib` only).

2. **Vercel serverless functions** — three Python functions in `api/`:
   - `api/symbols/[identity].py` — GET a symbol by hash
   - `api/symbols/index.py` — POST a symbol (write-protected)
   - `api/health.py` — liveness check

3. **`vercel.json`** — routing config for the publicsite repo that adds
   `/symbols/*` and `/health` routes pointing at the new functions.

4. **`codifide store push`** — already works; just needs the Vercel
   deployment URL as the registry.

## What is out of scope

- Modifying the existing `SymbolStore` filesystem backend (stays as-is)
- The Fly.io artifacts (Dockerfile, fly.toml) — kept as self-hosted option
- Any changes to the language, interpreter, or canonical form

## G0 decision

Approved. Problem is real, scope is bounded, no new accounts required.
Proceeding to G1.
