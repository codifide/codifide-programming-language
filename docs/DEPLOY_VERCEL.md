# Deploying the Codifide Public Registry on Vercel

The public registry runs as Python serverless functions on Vercel, backed by
Vercel Blob for persistent symbol storage. No new accounts needed — it deploys
to the same Vercel project as `codifide.com`.

---

## Architecture

```
Agent request
    ↓
codifide.com/symbols/<hash>   (Vercel serverless function)
    ↓
Vercel Blob (symbol files, keyed by sha256 hash, public CDN)
    ↓
Return canonical CBOR
```

Vercel handles TLS, CDN caching, and scaling automatically. The Python
functions are stateless — all state lives in Vercel Blob.

---

## One-time setup

### 1. Create a Vercel Blob store

1. Go to your Vercel project dashboard → **Storage** tab
2. Select **Create Database** → **Blob**
3. Set access to **Public** (symbols are content-addressed — no secrets)
4. Name it `codifide-symbols`
5. Connect it to the `publicsite` project
6. Vercel automatically adds `BLOB_READ_WRITE_TOKEN` to your project's
   environment variables

### 2. Set the write token (optional but recommended)

The `REGISTRY_WRITE_TOKEN` controls who can publish new symbols. Without it,
`POST /symbols` is disabled (read-only mode).

In your Vercel project → **Settings** → **Environment Variables**:
```
REGISTRY_WRITE_TOKEN = <generate a strong random token>
```

Keep this secret. It's separate from `BLOB_READ_WRITE_TOKEN`.

### 3. Deploy

Push the publicsite repo to GitHub. Vercel deploys automatically on push.

Or deploy manually:
```bash
cd /Users/douglasjones/Projects/publicsite
npx vercel --prod
```

### 4. Verify

```bash
curl https://codifide.com/health
# → {"status":"ok"}
```

---

## Seed the registry with the canonical pipeline symbols

After the registry is live, push the five canonical pipeline symbols:

```bash
cd /Users/douglasjones/Projects/CodifideProgrammingLanguage

# Store locally first (if not already done)
python3 -m codifide store put content_classifier.cod
python3 -m codifide store put moderation_gate.cod
python3 -m codifide store put escalation_router.cod

# Push to the registry
python3 -m codifide store push \
  sha256:377099c5bddb8cebe9e8bc6b8499bb00ea99083798d1b064799ac82c55636fae \
  --registry https://codifide.com

python3 -m codifide store push \
  sha256:1bbe69ba7dae84a1fc1a5b335ac2fd9f4be3e4462857db3cc0d38c4af5be4a2a \
  --registry https://codifide.com

python3 -m codifide store push \
  sha256:68c15e1108ac195e211634d2755f58353422db61b077690ec59686ad87d2d964 \
  --registry https://codifide.com
```

If `REGISTRY_WRITE_TOKEN` is set, add the auth header:
```bash
python3 -m codifide store push sha256:377099... \
  --registry https://codifide.com \
  --token <REGISTRY_WRITE_TOKEN>
```

---

## Test end-to-end

```bash
python3 -m codifide run pipeline_composed.cod \
  --registry https://codifide.com
# → blocked
```

---

## Publishing your own symbols

```bash
# Store locally
python3 -m codifide store put my_module.cod

# Push to the registry
python3 -m codifide store push sha256:<hash> \
  --registry https://codifide.com \
  --token <REGISTRY_WRITE_TOKEN>
```

---

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness check |
| `/symbols/<hash>` | GET | Retrieve symbol (CBOR or JSON) |
| `/symbols/<hash>` | HEAD | Existence check |
| `/symbols/<hash>/imports` | GET | Resolve direct imports |
| `/symbols` | POST | Publish a symbol (requires write token) |

---

## Pricing

Vercel Blob free tier:
- 500 MB storage (~500,000 symbols at ~1 KB each)
- 100 GB bandwidth/month
- Serverless function invocations: 100,000/month on free tier

This is well within free tier for typical agent usage.

---

## Monitoring

Check the Vercel dashboard → **Functions** tab for invocation logs and errors.
Check **Storage** → **Blob** for the symbol store contents.

---

*Deploy guide version 1.0 — May 2026*
