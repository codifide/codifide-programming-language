"""Drift guard for ``dispatches/INDEX.md``.

The index is generated from filenames and YAML subjects in
``dispatches/`` by ``python3 -m codifide dispatch-index``. If the
checked-in file falls behind the directory contents (e.g., a new
dispatch landed without regenerating), this test surfaces it the
same way the capability manifest drift test surfaces a stale
``docs/capability-0.1.json``.

The fix is always the same: run ``python3 -m codifide
dispatch-index`` and commit the result.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from codifide.dispatch_index import build_index


REPO_ROOT = Path(__file__).resolve().parent.parent
DISPATCH_DIR = REPO_ROOT / "dispatches"
INDEX_PATH = DISPATCH_DIR / "INDEX.md"


class DispatchIndexDriftTests(unittest.TestCase):
    def test_index_exists(self) -> None:
        self.assertTrue(
            INDEX_PATH.exists(),
            "dispatches/INDEX.md does not exist; run "
            "`python3 -m codifide dispatch-index` to generate it.",
        )

    def test_index_matches_regenerated(self) -> None:
        self.assertTrue(DISPATCH_DIR.exists())
        generated = build_index(DISPATCH_DIR)
        current = INDEX_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            current,
            generated,
            "dispatches/INDEX.md is stale.\n"
            "Regenerate with `python3 -m codifide dispatch-index` "
            "and commit the result.",
        )


if __name__ == "__main__":
    unittest.main()
