# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Consistency tests for pattern data integrity (65aa566 lineage).

Validates:
- Migration refs are canonical catalog names or well-formed external refs
- No malformed domain slugs (commas, spaces)

Note: arch's 1:1 ArchitectureStyle↔JSON-file completeness check does not
apply here — the agent catalog has 61 patterns mapping many-to-one onto the
8 AgentTopology values. That mapping is validated by
tests/unit/test_catalog.py::test_every_json_topology_field_is_valid_enum_value.
Domain-enum validity, suitable/unsuitable disjointness, and catalog size are
also covered by test_catalog.py.
"""

from __future__ import annotations

from src.patterns.loader import PatternLoader


class TestMigrationRefConsistency:
    """Migration refs should be canonical catalog names or well-formed external refs."""

    def test_all_migration_refs_are_valid(self) -> None:
        """Every migration_from/to entry is a catalog name or well-formed external ref."""

        from src.schemas.enums import AgentTopology

        catalog = {item.value for item in AgentTopology}

        loader = PatternLoader()
        patterns = loader.load_all()

        bad_refs: list[tuple[str, str, str, str]] = []
        for p in patterns:
            name = p.get("name", "?")
            for field in ("migration_from", "migration_to"):
                for ref in p.get(field, []):
                    is_catalog = ref in catalog
                    is_well_formed = bool(
                        ref and
                        ref == ref.lower() and
                        " " not in ref and
                        "," not in ref
                    )
                    if not is_catalog and not is_well_formed:
                        bad_refs.append((name, field, ref, "malformed slug"))

        assert not bad_refs, (
            f"Found {len(bad_refs)} malformed migration refs:\n" +
            "\n".join(f"  {n} {f}: '{r}'" for n, f, r, _ in bad_refs)
        )

    def test_all_migration_refs_point_to_existing_patterns_or_external(self) -> None:
        """Every migration ref resolves to a known catalog name or documented external."""
        from src.schemas.enums import AgentTopology

        catalog = {item.value for item in AgentTopology}

        loader = PatternLoader()
        patterns = loader.load_all()

        bad_refs: list[tuple[str, str, str]] = []
        for p in patterns:
            name = p.get("name", "?")
            for field in ("migration_from", "migration_to"):
                for ref in p.get(field, []):
                    if ref not in catalog and not ref.islower():
                        bad_refs.append((name, field, ref))

        assert not bad_refs, (
            f"Found {len(bad_refs)} non-catalog refs with uppercase:\n" +
            "\n".join(f"  {n} {f}: '{r}'" for n, f, r in bad_refs)
        )


class TestDomainSlugIntegrity:
    """Domain slugs must not contain commas or spaces."""

    def test_no_domain_slug_contains_comma_or_space(self) -> None:
        """No suitable_domains or unsuitable_domains entry contains ',' or ' '."""
        loader = PatternLoader()
        patterns = loader.load_all()

        bad: list[tuple[str, str, str, str]] = []
        for p in patterns:
            name = p.get("name", "?")
            for field in ("suitable_domains", "unsuitable_domains"):
                for v in p.get(field, []):
                    if not isinstance(v, str):
                        continue
                    if "," in v or " " in v:
                        bad.append((name, field, v, "contains comma or space"))

        assert not bad, (
            f"Found {len(bad)} malformed domain slugs:\n" +
            "\n".join(f"  {n} {f}: '{v}'" for n, f, v in bad)
        )
