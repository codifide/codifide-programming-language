# Codifide Public Registry

The public registry at `https://codifide.com` serves canonical CBOR for
any symbol published to it. Agents resolve content identities across
machines without out-of-band coordination. Hash-verification makes trust
automatic: a server cannot lie about a symbol's content without changing
its identity.

---

## What's in the registry

The five canonical pipeline symbols from the agent case studies are
published at the following identities:

| Symbol | Identity |
|--------|----------|
| `classify_content` | `sha256:377099c5bddb8cebe9e8bc6b8499bb00ea99083798d1b064799ac82c55636fae` |
| `moderate` | `sha256:1bbe69ba7dae84a1fc1a5b335ac2fd9f4be3e4462857db3cc0d38c4af5be4a2a` |
| `route_message` | `sha256:68c15e1108ac195e211634d2755f58353422db61b077690ec59686ad87d2d964` |

These are the symbols from the content-moderation pipeline task spec
(`docs/AGENT_TASK_SPEC.md`). They are the canonical test case for
content-addressed composition.

---

## Resolving symbols from the registry

Pass `--registry https://codifide.com` to `codifide run`:

```bash
python3 -m codifide run pipeline_composed.cod \
  --registry https://codifide.com
```

The runtime fetches any import not found in the local store from the
registry, verifies the hash, and caches it locally. Subsequent runs
use the local cache.

---

## Publishing to the registry

Use `codifide store push`:

```bash
# Store the symbol locally first
python3 -m codifide store put my_module.cod

# Push to the public registry
python3 -m codifide store push sha256:<hash> \
  --registry https://codifide.com
```

The registry returns the identity on success. Pushes are idempotent —
pushing the same symbol twice returns the existing identity.

---

## Hash stability guarantees

A symbol's identity is the SHA-256 hash of its canonical CBOR bytes.
The canonical form includes the symbol's intent, signature, effects,
and candidate bodies — everything that defines what the symbol does.

**Guarantees:**
1. The same identity always resolves to the same bytes.
2. A server cannot serve different bytes under the same identity —
   the runtime verifies the hash on every fetch.
3. An identity is stable forever. Published symbols are never deleted
   or modified.

---

## Running a private registry

Start a read-only registry server locally:

```bash
python3 -m codifide serve --read-only --port 7777
```

For production deployment on Vercel (recommended), see `docs/DEPLOY_VERCEL.md`.
For self-hosted deployment on Fly.io, see `docs/DEPLOY.md`.

---

## Cookbook: publish-and-resolve workflow

```bash
# 1. Write your module
cat > my_classifier.cod << 'EOF'
module my_classifier

def classify
  intent "classify a message"
  sig    (msg: String) -> Label
  effects {}
  cand
    intent "unsafe"
    when   contains(lower(msg), "spam")
    belief("unsafe", 0.90)
  cand
    intent "safe fallback"
    belief("safe", 0.75)
EOF

# 2. Store it locally
python3 -m codifide store put my_classifier.cod
# Output: sha256:abc123...  classify

# 3. Push to the public registry
python3 -m codifide store push sha256:abc123... \
  --registry https://codifide.com

# 4. Share the identity with another agent
# The other agent can now resolve it:
# import classify = sha256:abc123...
# python3 -m codifide run their_program.cod \
#   --registry https://codifide.com
```

---

*Registry documentation version 1.0 — May 2026*  
*Part of Codifide v4.0*
