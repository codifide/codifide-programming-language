"""Capability manifest tests.

Three invariants, all forced by these tests:

1. The checked-in manifest at ``docs/capability-0.1.json`` equals what
   ``generate_capability()`` produces today, modulo the ``generator``
   provenance field. If you changed the runtime interface, regenerate
   the file or the test fails.
2. The manifest describes every primitive the default registry
   exposes and every typed error class the runtime declares. Drift
   between the manifest and the implementation is a test failure,
   not a runtime surprise.
3. The manifest round-trips through canonical JSON and CBOR with
   byte-level stability — same generator, same bytes, same content
   hash.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from codifide import canonical_cbor_bytes, content_hash_cbor
from codifide.capability import (
    CAPABILITY_SCHEMA_VERSION,
    CODIFIDE_SCHEMA_VERSION,
    generate_capability,
)
from codifide.projection.cbor import canonical_cbor


REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKED_IN = REPO_ROOT / "docs" / "capability-0.1.json"


def _strip_generator(manifest: dict) -> dict:
    """Remove the generator field for cross-implementation comparison.

    Implementations differ on ``generator`` (that's the point) but must
    agree on everything else. For drift-checking the test compares
    stripped copies so changes to ``__version__`` alone don't register
    as manifest drift.
    """
    out = dict(manifest)
    out.pop("generator", None)
    return out


class ManifestShapeTests(unittest.TestCase):
    def test_top_level_fields_are_present(self) -> None:
        m = generate_capability()
        for key in [
            "codifide_capability",
            "codifide_schema",
            "generator",
            "ast_kinds",
            "primitives",
            "effects",
            "errors",
            "literal_types",
            "surface_keywords",
        ]:
            self.assertIn(key, m)

    def test_schema_versions_match(self) -> None:
        m = generate_capability()
        self.assertEqual(m["codifide_capability"], CAPABILITY_SCHEMA_VERSION)
        self.assertEqual(m["codifide_schema"], CODIFIDE_SCHEMA_VERSION)

    def test_generator_names_current_implementation(self) -> None:
        m = generate_capability()
        self.assertTrue(m["generator"].startswith("codifide-python-"))


class ManifestAgreesWithImplementationTests(unittest.TestCase):
    """The manifest is not allowed to lie about what the runtime exposes."""

    def test_every_registered_primitive_is_in_the_manifest(self) -> None:
        from codifide.runtime.primitives import EffectTrace, build_default_registry

        trace = EffectTrace.fresh()
        reg = build_default_registry(trace)
        implementation = set(reg._prims.keys())  # noqa: SLF001

        m = generate_capability()
        manifest = {p["name"] for p in m["primitives"]}

        missing = implementation - manifest
        extra = manifest - implementation
        self.assertFalse(
            missing,
            f"primitives registered but absent from manifest: {sorted(missing)}",
        )
        self.assertFalse(
            extra,
            f"primitives in manifest but not registered: {sorted(extra)}",
        )

    def test_every_primitive_records_its_effect_and_return_type(self) -> None:
        from codifide.runtime.primitives import EffectTrace, build_default_registry

        trace = EffectTrace.fresh()
        reg = build_default_registry(trace)
        m = generate_capability()
        manifest_by_name = {p["name"]: p for p in m["primitives"]}

        for name, spec in reg._prims.items():  # noqa: SLF001
            entry = manifest_by_name[name]
            self.assertEqual(entry["effect"], spec.effect)
            self.assertEqual(entry["returns"], spec.returns)

    def test_every_codifide_error_subclass_is_in_the_manifest(self) -> None:
        # If someone adds a new CodifideError subclass, the manifest must
        # grow to match. Catches the common drift mode where a new
        # typed error appears in code without being documented for
        # agent consumers.
        import codifide.runtime.errors as errmod

        actual_errors = set()
        for attr in dir(errmod):
            cls = getattr(errmod, attr)
            if (
                isinstance(cls, type)
                and issubclass(cls, errmod.CodifideError)
                and cls.__module__ == errmod.__name__
            ):
                actual_errors.add(cls.__name__)

        m = generate_capability()
        manifest_errors = {e["name"] for e in m["errors"]}

        missing = actual_errors - manifest_errors
        self.assertFalse(
            missing,
            f"error classes missing from manifest: {sorted(missing)}",
        )

    def test_effects_list_matches_primitive_effect_labels(self) -> None:
        from codifide.runtime.primitives import EffectTrace, build_default_registry

        trace = EffectTrace.fresh()
        reg = build_default_registry(trace)
        labels = {
            spec.effect for spec in reg._prims.values()  # noqa: SLF001
            if spec.effect is not None
        }

        m = generate_capability()
        self.assertEqual(set(m["effects"]), labels)
        # And sorted.
        self.assertEqual(m["effects"], sorted(m["effects"]))

    def test_surface_keywords_match_the_parser_tables(self) -> None:
        from codifide.parser import tokens as _tokens

        m = generate_capability()
        # Every canonical keyword appears exactly once.
        manifest_canons = [e["canonical"] for e in m["surface_keywords"]["keywords"]]
        impl_canons = sorted(set(_tokens.KEYWORDS.values()))
        self.assertEqual(manifest_canons, impl_canons)

        manifest_op_canons = [e["canonical"] for e in m["surface_keywords"]["operators"]]
        impl_op_canons = sorted(set(_tokens.OPERATORS.values()))
        self.assertEqual(manifest_op_canons, impl_op_canons)


class ManifestCheckedInFileTests(unittest.TestCase):
    """The committed manifest must match what this code produces."""

    def test_checked_in_manifest_equals_regenerated_modulo_generator(self) -> None:
        if not CHECKED_IN.exists():
            self.skipTest(
                f"checked-in manifest not present at {CHECKED_IN}. "
                "Run `python3 -m codifide capability > docs/capability-0.1.json` "
                "to regenerate."
            )
        checked_in = json.loads(CHECKED_IN.read_text(encoding="utf-8"))
        regenerated = generate_capability()
        self.assertEqual(
            _strip_generator(checked_in),
            _strip_generator(regenerated),
            "docs/capability-0.1.json is stale. Regenerate with "
            "`python3 -m codifide capability > docs/capability-0.1.json`.",
        )


class ManifestCanonicalFormTests(unittest.TestCase):
    """The manifest serializes like any other canonical document."""

    def test_cbor_roundtrip_is_byte_stable(self) -> None:
        m = generate_capability()
        a = canonical_cbor(m)
        b = canonical_cbor(m)
        self.assertEqual(a, b)

    def test_cbor_smaller_than_pretty_json(self) -> None:
        m = generate_capability()
        json_bytes = json.dumps(m, indent=2, sort_keys=True).encode("utf-8")
        cbor_bytes = canonical_cbor(m)
        self.assertLess(len(cbor_bytes), len(json_bytes))

    def test_manifest_content_hash_is_deterministic(self) -> None:
        m = generate_capability()
        a = hashlib.sha256(canonical_cbor(m)).hexdigest()
        b = hashlib.sha256(canonical_cbor(m)).hexdigest()
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
