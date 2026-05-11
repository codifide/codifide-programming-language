# Session journal — Noema → Codifide rename

*Live notes as I execute the rename. The earlier capability-manifest
journal set the pattern: capture the decisions so they're recoverable.*

## Decision

The language is being renamed from "Noema" to "Codifide." Reasons
captured in the chat thread and `docs/brand/codifide-copy.md`:

- Four other software projects already use "Noema" in adjacent
  spaces. Cleanup would be ongoing and incomplete.
- Codifide Inc. is an established s-corp with trademarked branding
  and the tagline "confidence in code" — which describes exactly
  what the language mechanically does.
- The name decomposes as **Codified + Fidelity**, both halves of
  which map directly to concrete language properties.
- Rename under an existing IP umbrella is cleaner than fighting
  for contested ground.

## Scope

Everything that says "Noema" or "noema" as a current identifier
gets renamed to "Codifide" / "codifide". This includes:

- Python package: `noema/` → `codifide/`
- Rust crate: `crates/noema-canonical/` → `crates/codifide-canonical/`
- CLI entry: `python3 -m noema` → `python3 -m codifide`
- File extension: `.nm` → `.cod`
- Default store path: `~/.noema/store` → `~/.codifide/store`
- Environment variable: `NOEMA_STORE` → `CODIFIDE_STORE`
- Canonical form top-level tag: `"noema": "0.1"` → `"codifide": "0.1"`
- Capability schema: `noema_capability` → `codifide_capability`
- All documentation references to the language
- All error messages referencing the language name

## What is preserved unchanged

- **Historical dispatches** at `dispatches/2026-05-10-*.{md,yaml}`.
  Those were authored when the language was called Noema. Rewriting
  them rewrites history; the honest path is to leave them and let
  the rename dispatch explain the transition.
- **Session journals** for past work.
- **The brand copy file** at `docs/brand/codifide-copy.md` — already
  written under the new name.
- **The Codifide language logos** — already renamed.
- **The Noema logo files** — to be deleted at the end of this pass.

## Consequences accepted

Every existing canonical hash becomes invalid. The capability
manifest hash changes. Every example's content hash changes. Every
stored symbol would need to be re-put. Because nothing external
depends on these hashes yet (no public release, no agent has
consumed them), this is a one-time cost paid at a low-risk moment.

## Execution order

1. Move package directories (Python + Rust).
2. Bulk-replace identifiers in source.
3. Rename file extensions on examples.
4. Update all string literals that reference old names.
5. Update configuration (pyproject.toml, Cargo.toml).
6. Update all documentation.
7. Regenerate the capability manifest.
8. Run full test suite; fix any breakage.
9. Update README and GETTING_STARTED.
10. Clean up obsolete logo files.
11. Write governance doc (`GOVERNANCE.md`).
12. Write rename dispatch (paired Quill/Glyph).
13. Update session state.
14. Commit.

Beginning now.
