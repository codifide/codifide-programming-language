# Registry Deployment — Fly.io

**Date:** 2026-05-14  
**Persona:** Quill

---

## What happened

The public registry infrastructure was completed. The server was already
written (V3-2); what was missing was a deployment target, a Docker image,
and a seed script.

## What shipped

**`Dockerfile`** — builds a minimal Python 3.11 image with the codifide
package installed. Starts `codifide serve --read-only --host 0.0.0.0 --port 7777`.
Includes a health check. Verified: builds cleanly, health endpoint responds,
POST /symbols correctly rejected in read-only mode.

**`fly.toml`** — Fly.io deployment config. `codifide-registry` app, `iad`
region, 256mb shared VM, 1GB persistent volume at `/data/store`, HTTPS
enforced, `min_machines_running = 1` so the registry is always reachable.

**`.dockerignore`** — excludes tests, docs, examples, dispatches, and build
artifacts from the image. Keeps the image small.

**`scripts/seed_registry.sh`** — pushes the three canonical pipeline symbols
to the registry after deploy. Verifies each is reachable via curl.

**`docs/DEPLOY.md`** — step-by-step deploy guide: install flyctl, create
app, create volume, deploy, add custom domain, seed, verify end-to-end.

## What's left for you

1. `curl -L https://fly.io/install.sh | sh` — install flyctl
2. `flyctl auth login`
3. `flyctl launch --no-deploy --name codifide-registry`
4. `flyctl volumes create codifide_store --size 1 --region iad`
5. `flyctl deploy`
6. Add DNS: `registry.codifide.com CNAME codifide-registry.fly.dev`
7. `./scripts/seed_registry.sh --registry https://registry.codifide.com`

That's the full operational step. The code is ready; it just needs a
machine to run on.

## What I'm not yet sure of

Whether Fly.io free tier will stay free for this workload long-term.
The registry is read-only and low-traffic, so it should be well within
limits — but worth monitoring after launch.
