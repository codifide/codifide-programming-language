"""Dispatch-stream index generator.

22 dispatches were filed on 2026-05-11 alone. The stream of
Quill readouts, Glyph YAMLs, and Sable audits is the project's
journal; reading them in filename order reconstructs how Codifide
evolved. A generated index makes the stream browseable for
future agents — first as a Markdown table at
``dispatches/INDEX.md``, later (possibly) as structured data a
dispatch-consuming tool could iterate.

The index is derived from filenames and, where available, from
the ``subject`` field of Glyph YAML dispatches. Quill readouts
and Sable audits are identified by filename convention.

Running ``python3 -m codifide dispatch-index`` writes
``dispatches/INDEX.md``. Running ``python3 -m codifide
dispatch-index --check`` verifies the checked-in file matches
what would be generated now — a drift guard analogous to the
capability manifest drift test.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


# Filename convention for dispatch artifacts:
#
#   <date>-<slug>.readout.md   — Quill (human readout)
#   <date>-<slug>.yaml         — Glyph (structured)
#   <date>-<slug>.md           — Sable audit, or a readout that did not
#                                need a paired YAML (rare)
#
# A few dispatches don't follow the paired convention perfectly
# (e.g., ``2026-05-10-security-audit.md`` is a standalone Sable
# audit; ``2026-05-10-rename-journal.md`` is a raw execution
# journal). The index surfaces whatever is present and annotates
# the shape.


_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


@dataclass(frozen=True)
class DispatchEntry:
    """One row in the index.

    ``date`` and ``slug`` come from the filename. ``readout_path``
    and ``yaml_path`` are set when the corresponding artifacts
    exist. ``audit_path`` is a Sable audit paired with the slug.
    ``subject`` is pulled from the Glyph YAML's ``subject`` field
    when present.
    """
    date: str
    slug: str
    readout_path: Optional[str]
    yaml_path: Optional[str]
    audit_path: Optional[str]
    subject: Optional[str]


def _extract_subject(yaml_path: Path) -> Optional[str]:
    """Best-effort parse of ``subject:`` from a Glyph YAML dispatch.

    We don't pull in a full YAML parser because the dispatches are
    hand-written and the ``subject`` field follows a predictable
    shape: indented two spaces, ``subject:`` key, value continues
    on the same line. This keeps the index generator a
    zero-dependency Python utility.
    """
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    # Look for `  subject: <value>` or `  subject: >` + next line.
    for i, line in enumerate(text.splitlines()):
        stripped = line.lstrip()
        if not stripped.startswith("subject:"):
            continue
        after = stripped[len("subject:"):].strip()
        if after == ">":
            # Multi-line literal; grab the next non-empty line.
            for j in range(i + 1, min(i + 10, len(text.splitlines()))):
                nxt = text.splitlines()[j].strip()
                if nxt:
                    return nxt
            return None
        if after.startswith(">"):
            after = after[1:].strip()
        # Strip surrounding quotes if present.
        if after.startswith('"') and after.endswith('"') and len(after) >= 2:
            after = after[1:-1]
        return after
    return None


def _collect_entries(dispatch_dir: Path) -> List[DispatchEntry]:
    """Scan ``dispatch_dir`` and group artifacts into DispatchEntries.

    Groups by ``<date>-<slug>``. Readouts and YAMLs with the same
    slug are grouped; Sable audits (recognized by the suffix
    ``-audit.md``) are attached to the same slug when one exists,
    else listed as their own entry.
    """
    by_key: dict[Tuple[str, str], dict] = {}
    feedback_dir_prefix = "feedback/"

    for path in sorted(dispatch_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(dispatch_dir).as_posix()
        # Skip the index itself and the feedback template folder.
        if rel == "INDEX.md":
            continue
        if rel.startswith(feedback_dir_prefix):
            continue

        name = path.name
        # ``readout.md`` suffix
        if name.endswith(".readout.md"):
            base = name[: -len(".readout.md")]
            m = _DATE_RE.match(base)
            if not m:
                continue
            date, slug = m.group(1), m.group(2)
            key = (date, slug)
            entry = by_key.setdefault(key, {})
            entry["readout_path"] = rel
            continue
        # ``yaml`` suffix
        if name.endswith(".yaml"):
            base = name[: -len(".yaml")]
            m = _DATE_RE.match(base)
            if not m:
                continue
            date, slug = m.group(1), m.group(2)
            key = (date, slug)
            entry = by_key.setdefault(key, {})
            entry["yaml_path"] = rel
            entry["subject"] = _extract_subject(path)
            continue
        # Plain ``.md``. Distinguish audits by -audit.md suffix.
        if name.endswith(".md"):
            base = name[: -len(".md")]
            m = _DATE_RE.match(base)
            if not m:
                continue
            date, slug = m.group(1), m.group(2)
            if slug.endswith("-audit"):
                # Attach audit to the core slug (slug minus "-audit")
                core_slug = slug[: -len("-audit")]
                key = (date, core_slug)
                entry = by_key.setdefault(key, {})
                entry["audit_path"] = rel
            else:
                # Standalone md dispatch — treat it as its own entry.
                key = (date, slug)
                entry = by_key.setdefault(key, {})
                # Use as readout if no readout yet present.
                if "readout_path" not in entry:
                    entry["readout_path"] = rel
            continue

    out: List[DispatchEntry] = []
    for (date, slug), entry in sorted(by_key.items()):
        out.append(
            DispatchEntry(
                date=date,
                slug=slug,
                readout_path=entry.get("readout_path"),
                yaml_path=entry.get("yaml_path"),
                audit_path=entry.get("audit_path"),
                subject=entry.get("subject"),
            )
        )
    return out


def render_index_markdown(entries: Iterable[DispatchEntry]) -> str:
    """Render an index as a Markdown table.

    Grouped by date so a reader can scan a day's work at a
    glance. Columns: slug, subject (if known), links to the
    artifacts that exist.
    """
    lines: List[str] = []
    lines.append("# Dispatch Stream — Index\n")
    lines.append(
        "Generated from the filenames and YAML subjects in "
        "`dispatches/`. Produced by "
        "`python3 -m codifide dispatch-index`. If this file is out "
        "of sync with the directory contents, regenerate it.\n"
    )
    lines.append(
        "Filename convention:\n"
        "- `<date>-<slug>.readout.md` — Quill readout (human)\n"
        "- `<date>-<slug>.yaml`       — Glyph dispatch (structured)\n"
        "- `<date>-<slug>-audit.md`   — Sable audit\n"
        "- `<date>-<slug>.md`         — standalone dispatch (rare)\n"
    )

    # Group by date.
    entries_list = list(entries)
    dates = sorted({e.date for e in entries_list}, reverse=True)
    for date in dates:
        day_entries = [e for e in entries_list if e.date == date]
        day_entries.sort(key=lambda e: e.slug)
        lines.append(f"\n## {date}\n")
        lines.append("| slug | subject | readout | yaml | audit |")
        lines.append("|---|---|---|---|---|")
        for e in day_entries:
            subject = (e.subject or "").replace("|", "\\|")
            readout = f"[md](./{e.readout_path})" if e.readout_path else ""
            yml = f"[yaml](./{e.yaml_path})" if e.yaml_path else ""
            audit = f"[md](./{e.audit_path})" if e.audit_path else ""
            lines.append(
                f"| `{e.slug}` | {subject} | {readout} | {yml} | {audit} |"
            )

    lines.append("")
    return "\n".join(lines)


def build_index(dispatch_dir: Path) -> str:
    entries = _collect_entries(dispatch_dir)
    return render_index_markdown(entries)


def write_index(dispatch_dir: Path, index_path: Optional[Path] = None) -> Path:
    """Generate and write INDEX.md.

    Defaults the index path to ``<dispatch_dir>/INDEX.md``. Returns
    the path written to.
    """
    if index_path is None:
        index_path = dispatch_dir / "INDEX.md"
    content = build_index(dispatch_dir)
    index_path.write_text(content, encoding="utf-8")
    return index_path


def check_index(dispatch_dir: Path, index_path: Optional[Path] = None) -> bool:
    """Return True iff the checked-in index matches what would be generated.

    Used as a drift guard so a committer who adds a new dispatch
    without regenerating the index is surfaced by the test suite.
    """
    if index_path is None:
        index_path = dispatch_dir / "INDEX.md"
    if not index_path.exists():
        return False
    generated = build_index(dispatch_dir)
    current = index_path.read_text(encoding="utf-8")
    return generated == current
