---
inclusion: manual
---

# Publicsite (codifide.com) — Rules

## Version Sync — The Website Must Track the Code

The publicsite is the agent-facing interface to Codifide. Stale content
misleads agents and users. These rules are enforced by `dispatch-check`
and are on the Sable auditor checklist.

### Rules

1. **`publicsite/capability.json` and `publicsite/capability.cbor` must be
   regenerated on every release.** Run:
   ```bash
   python3 -m codifide capability > /path/to/publicsite/capability.json
   python3 -m codifide capability --cbor > /path/to/publicsite/capability.cbor
   ```
   The `generator` field in the published JSON must match the current
   `codifide-python-X.Y.Z` version. A mismatch is a release blocker.

2. **The version stat in `index.html` must match the current release.**
   The `<span class="lang-stat-num">` element showing the version number
   (e.g. `v2.0`) must be updated on every release. The release description
   text alongside it must also reflect the new release.

3. **Any agent-facing doc change (AGENT_QUICKREF.md, FOR_AGENTS.md,
   AGENT_COOKBOOK.md) must be reflected on the site** if the site links to
   or embeds that content. Check `index.html` for stale inline excerpts.

4. **`dispatch-check` enforces rules 1 and 2 automatically.** It compares
   the `generator` field in `publicsite/capability.json` against the live
   manifest and checks the version stat in `index.html`. A mismatch causes
   `dispatch-check` to exit non-zero.

5. **The publicsite update must be committed in the same session as the
   release.** Do not close a release session with a stale publicsite.

### What "same session" means

A release session ends when `dispatch-check` exits 0 and the
session-close dispatch pair is filed. The publicsite sync must happen
before that close, not after.

---

## Vercel Content Security Policy

The `vercel.json` for the publicsite enforces a strict CSP:

```
style-src 'self' https://fonts.googleapis.com
```

**This means inline `<style>` blocks are blocked by the browser and silently ignored.**

### Rules

1. **Never write inline `<style>` blocks in any HTML file deployed to Vercel.** They will be blocked by the CSP and the page will render unstyled.

2. **All CSS must be in external `.css` files** referenced via `<link rel="stylesheet" href="...">`.

3. **When adding a new page**, create a corresponding `.css` file (e.g. `launch.html` → `launch.css`) and link it externally.

4. **The main design system is `styles.css`** — always link this first, then any page-specific CSS file second.

5. **Do not add `'unsafe-inline'` to the CSP** to work around this — fix the CSS instead.

### Example

Wrong:
```html
<style>
  .my-class { color: red; }
</style>
```

Right:
```html
<link rel="stylesheet" href="my-page.css" />
```
