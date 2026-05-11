# Codifide Language — logo usage

Three marks ship, all in Codifide palette (cyan / blue / purple /
navy). Pick the one that matches the context.

## Files

- **`codifide-language-mark.svg`** — the mark on its own. Use at
  favicon sizes and anywhere a small square logo is needed. The
  hexagonal frame carries Codifide color; the three-node interior
  carries the language's distinctive signature (first-class
  refusal as a hollow node).

- **`codifide-language-wordmark.svg`** — the mark paired with
  *codifide* (primary) and *language* (sub-brand descriptor). Use
  on README headers, documentation pages, and anywhere the full
  language identity needs to appear together.

- The legacy **`noema-*.svg`** files remain in this directory
  for historical reference during the rename transition. They
  will be removed once the Codifide rename is finalized.

## Relationship to the Codifide company mark

The language mark is a sub-brand, not a replacement. It must never
appear as if it *is* the Codifide company mark.

When both appear together (website, press, co-branded materials):

- **Codifide company logo takes visual precedence.** It is the
  parent; the language is the child.
- **Leave breathing room between them.** Minimum horizontal gap
  of 1.5× the hexagon width.
- **Never mix the two into a single mark.** The Codifide C and
  the language hypergraph are separate marks with separate meanings.

Recommended lockup pattern:

```
  ┌─────────────────────────┬─────────────────────────────┐
  │                         │                             │
  │   [Codifide mark]       │   [language mark]           │
  │   codifide              │   codifide                  │
  │   confidence in code    │   language                  │
  │                         │                             │
  └─────────────────────────┴─────────────────────────────┘
         company                    product
```

When the language mark appears alone (inside the project
repository, on GitHub, as a favicon for docs), the Codifide
company context is implicit — no lockup needed.

## Color values (Codifide palette)

Used consistently across the language mark and wordmark:

| Role                              | Hex        | Use                                          |
|-----------------------------------|------------|----------------------------------------------|
| Cyan — top-right edges            | `#3EA8C1`  | Hexagon top face echo                        |
| Blue — right/bottom edges         | `#2C6CB8`  | Hexagon right face                           |
| Purple — left edges               | `#6B4199`  | Hexagon left face echo                       |
| Light blue — "codi" wordmark half | `#3A8FC8`  | First syllable of the wordmark               |
| Navy — "fide" half, sub-brand, interior nodes | `#1D3A7B` / `#0A2E5E` | Second syllable, descriptor, hypergraph |

These are proposed matches derived from the company logo; a
designer working from Codifide's brand guide should confirm exact
values and update if needed.

## The wordmark's split-color convention

The company wordmark splits **codi** (lighter blue-cyan) from
**fide** (deeper navy). The language wordmark reproduces that
split exactly.

The split is not arbitrary — it echoes the syllabic break in the
name itself: **codi**(fied) + (fi)**de**lity. The design intent is
already embedded in the company mark; we preserve it.

Never recolor the wordmark into a single flat color unless the
rendering context makes two colors impossible (single-color print,
a terminal with no color support). In those cases use the navy
value for the full word.

## What Option A is not

This version is a flat mark that adopts Codifide's palette. The
company mark is 3D isometric. A future Option B would redraw the
language mark as a true 3D isometric hexagon matching the company
mark's dimensionality exactly — with the hypergraph nodes
replacing the negative-space C. That variant should be produced
by whoever designed the company mark, so the isometric treatment
is pixel-true. For now, this flat version carries the family
resemblance through color and geometry alone.

## Attribution

Designed in this repository during the Codifide naming discussion
on 2026-05-10. Released under the same MIT license as the rest of
the codebase.
