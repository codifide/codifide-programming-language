# Deploying the Codifide Public Registry

The public registry serves canonical CBOR for any symbol published to it.
It runs `python3 -m codifide serve --read-only` in a Docker container on
Fly.io, with a persistent volume for the symbol store.

---

## Prerequisites

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Log in
flyctl auth login
```

---

## First-time deploy

```bash
# 1. Create the app (one time only)
flyctl launch --no-deploy --name codifide-registry

# 2. Create the persistent volume for the symbol store
flyctl volumes create codifide_store --size 1 --region iad

# 3. Deploy
flyctl deploy

# 4. Verify the health endpoint
curl https://codifide-registry.fly.dev/health
# → {"status":"ok"}

# 5. Add the custom domain
flyctl certs create registry.codifide.com
# Then add a CNAME in your DNS: registry.codifide.com → codifide-registry.fly.dev
```

---

## Seed the registry with the canonical pipeline symbols

After the server is running:

```bash
# Store the pipeline symbols locally first (if not already done)
python3 -m codifide store put content_classifier.cod
python3 -m codifide store put moderation_gate.cod
python3 -m codifide store put escalation_router.cod

# Push to the registry
./scripts/seed_registry.sh --registry https://registry.codifide.com
```

---

## Subsequent deploys

```bash
flyctl deploy
```

The persistent volume survives deploys — the symbol store is not wiped.

---

## Verify a symbol is reachable

```bash
curl -s https://registry.codifide.com/symbols/sha256:377099c5bddb8cebe9e8bc6b8499bb00ea99083798d1b064799ac82c55636fae \
  -H "Accept: application/json" | python3 -m json.tool | head -5
```

---

## Test end-to-end

```bash
python3 -m codifide run pipeline_composed.cod \
  --registry https://registry.codifide.com
# → blocked
```

---

## Architecture

```
Agent machine                    Fly.io (iad)
─────────────────                ──────────────────────────────────
codifide run ──────── HTTPS ───► codifide-registry.fly.dev:443
  --registry                       │
  https://registry.codifide.com    ▼ (TLS terminated by Fly proxy)
                                 codifide serve --read-only
                                   --host 0.0.0.0
                                   --port 7777
                                   │
                                   ▼
                                 /data/store  (persistent volume)
```

Fly.io handles TLS termination. The Python server binds to `0.0.0.0:7777`
inside the container; Fly's proxy forwards HTTPS traffic to it.

---

## Monitoring

```bash
# Live logs
flyctl logs

# App status
flyctl status

# Volume info
flyctl volumes list
```

---

## Cost

Fly.io free tier covers:
- 3 shared-cpu-1x 256mb VMs
- 3GB persistent volume storage
- 160GB outbound data transfer/month

The registry is well within free tier for typical agent usage.

---

*Deploy guide version 1.0 — May 2026*
