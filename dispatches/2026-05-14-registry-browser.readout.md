# Registry Browser — codifide.com/registry

**Date:** 2026-05-14  
**Persona:** Quill

---

## What shipped

A full symbol browser at `https://codifide.com/registry`.

**Features:**
- Live status indicator — green dot + "Registry live" when `/health` responds
- Three canonical pipeline symbols listed with intent strings, type signatures, and effect badges
- Hash display with one-click copy button for each symbol
- "View canonical JSON →" link opens the live symbol in the browser
- Expand/collapse usage panels showing import syntax and CLI examples
- "Try it live" panel with the full pipeline command
- Publish workflow — 3-step guide for publishing your own symbols
- API reference table — all five endpoints with method badges
- Responsive — works on mobile
- Matches the existing design system exactly (same CSS variables, fonts, nav, footer)

**Navigation:**
- "Registry" link added to the main nav on `index.html`
- "Browse the registry →" link added to the v4.0 announcement section
- Registry link added to the footer nav

**Files:**
- `publicsite/registry.html` — the page
- `publicsite/registry.css` — page-specific styles extending `styles.css`
- `publicsite/registry.js` — live status check, copy buttons, expand/collapse
- `publicsite/vercel.json` — `/registry` route added
- `publicsite/index.html` — nav and footer updated

## What I'm not yet sure of

Whether the "View canonical JSON →" links will work correctly once the symbols
are seeded. They point to `/symbols/sha256:...` which routes to the serverless
function — that function needs the symbols in the blob store to return JSON
rather than a 404.
