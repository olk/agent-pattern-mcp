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
Real-data catalog tests — verifies 61 agent patterns load correctly
with the dict-based PatternLoader and that topology/category invariants hold.
"""

import json
from pathlib import Path

import pytest

from src.patterns.loader import PatternLoader
from src.schemas.enums import AgentDomain, AgentTopology, PatternCategory

PATTERN_DIR = Path(__file__).parent.parent.parent / "pattern"


@pytest.fixture
def loader():
    return PatternLoader(str(PATTERN_DIR))


@pytest.fixture
def patterns(loader):
    return loader.load_all()


def test_loader_loads_all(patterns):
    assert len(patterns) == 61


def test_pattern_names_are_unique(patterns):
    names = [p["name"] for p in patterns]
    assert len(set(names)) == len(names), "Duplicate pattern names found"


def test_loader_get_by_name(loader):
    react = loader.get_by_name("react")
    assert react is not None and react["category"] == "tool_use"
    assert loader.get_by_name("does-not-exist") is None


def test_every_pattern_has_valid_topology(patterns):
    valid_topologies = {t.value for t in AgentTopology}
    for p in patterns:
        topo = p.get("topology")
        assert topo is not None, f"{p['name']}: missing topology field"
        assert topo in valid_topologies, f"{p['name']}: invalid topology {topo!r}"


def test_every_json_topology_field_is_valid_enum_value(loader):
    for p in loader.load_all():
        json_path = Path(loader._patterns_dir) / f"{p['name']}-pattern.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "topology" in data, f"{p['name']}: topology field missing from JSON"
        topo = data["topology"]
        try:
            AgentTopology(topo)
        except ValueError:
            pytest.fail(f"{p['name']}: invalid topology value {topo!r}")


TOPOLOGY_EXAMPLE_PAIRS = [
    ("react", "single-agent-loop"),
    ("evaluator-optimizer", "evaluator-loop"),
    ("rewoo", "plan-execute"),
    ("llm-compiler", "parallel-fan-out"),
    ("prompt-chaining", "pipeline"),
    ("graph-orchestration", "graph-orchestrated"),
    ("supervisor-worker", "hierarchical"),
    ("swarm", "swarm"),
]


@pytest.mark.parametrize(("pattern_name", "expected_topology"), TOPOLOGY_EXAMPLE_PAIRS)
def test_topology_matches_approved_mapping(loader, pattern_name, expected_topology):
    p = loader.get_by_name(pattern_name)
    assert p is not None, f"Pattern {pattern_name!r} not found"
    assert p["topology"] == expected_topology, (
        f"{pattern_name}: expected topology {expected_topology!r}, got {p['topology']!r}"
    )


def test_every_topology_has_at_least_one_pattern(patterns):
    for topo in AgentTopology:
        patterns_with_topo = [p for p in patterns if p["topology"] == topo.value]
        assert len(patterns_with_topo) >= 1, f"Topology {topo.value} has no patterns"


def test_every_category_has_patterns(patterns):
    for cat in PatternCategory:
        patterns_in_cat = [p for p in patterns if p["category"] == cat.value]
        assert len(patterns_in_cat) >= 1, f"Category {cat.value} has no patterns"


def test_category_counts(patterns):
    from collections import Counter
    counts = Counter(p["category"] for p in patterns)
    assert counts["multi_agent"] == 11
    assert counts["observability"] == 3
    assert counts["reflection"] == 7


def test_quality_scores_in_range(patterns):
    for p in patterns:
        qa = p["quality_attributes"]
        values = list(qa.values())
        assert all(1.0 <= v <= 10.0 for v in values), f"{p['name']}: QA values out of range"
        mean = sum(values) / len(values)
        score = round(mean * 10, 1)
        assert 10.0 <= score <= 100.0


def test_loader_filter_by_domain(loader):
    filtered = loader.filter_by_domain("tool-use-tasks")
    assert len(filtered) > 0
    for p in filtered:
        assert "tool-use-tasks" in [d.lower().replace(" ", "-") for d in p.get("suitable_domains", [])]


def test_domains_are_disjoint(patterns):
    for p in patterns:
        name = p["name"]
        suitable = {d.lower().replace(" ", "-") for d in p.get("suitable_domains", [])}
        unsuitable = {d.lower().replace(" ", "-") for d in p.get("unsuitable_domains", [])}
        overlap = suitable & unsuitable
        assert not overlap, (
            f"Pattern '{name}': suitable_domains and unsuitable_domains overlap: {sorted(overlap)}"
        )


def test_migration_edges_exist(patterns):
    all_names = {p["name"] for p in patterns}
    for p in patterns:
        name = p["name"]
        for ref in p.get("migration_from", []):
            assert ref in all_names, (
                f"Pattern '{name}' migration_from references unknown pattern '{ref}'"
            )
        for ref in p.get("migration_to", []):
            assert ref in all_names, (
                f"Pattern '{name}' migration_to references unknown pattern '{ref}'"
            )


def test_no_non_ascii_in_key_fields(patterns):
    for p in patterns:
        name = p["name"]
        for ch in name:
            assert ord(ch) < 128, f"Pattern '{name}' has non-ASCII character in name: {ch!r}"
        topo = p.get("topology", "")
        for ch in topo:
            assert ord(ch) < 128, f"Pattern '{name}' has non-ASCII in topology: {ch!r}"
        cat = p.get("category", "")
        for ch in cat:
            assert ord(ch) < 128, f"Pattern '{name}' has non-ASCII in category: {ch!r}"
        for d in p.get("suitable_domains", []):
            for ch in d:
                assert ord(ch) < 128, f"Pattern '{name}' has non-ASCII in suitable_domains: {ch!r}"
        for d in p.get("unsuitable_domains", []):
            for ch in d:
                assert ord(ch) < 128, f"Pattern '{name}' has non-ASCII in unsuitable_domains: {ch!r}"


def test_all_domains_in_enum(patterns):
    valid = {d.value for d in AgentDomain}
    for p in patterns:
        for d in p.get("suitable_domains", []):
            assert d in valid, f"{p['name']}: suitable_domains value {d!r} not in AgentDomain enum"
        for d in p.get("unsuitable_domains", []):
            assert d in valid, f"{p['name']}: unsuitable_domains value {d!r} not in AgentDomain enum"


def test_every_domain_has_at_least_one_pattern(patterns):
    """Every AgentDomain value must appear in some pattern's suitable_domains.

    Prevents the dead-entry class (database-operations/devops/multimodal/
    scientific-research were valid enum values that no pattern declared, so
    users passing those domains got imprecise nearest-neighbour matches).
    """
    seen = {d for p in patterns for d in p.get("suitable_domains", [])}
    for ad in AgentDomain:
        assert ad.value in seen, (
            f"AgentDomain {ad.value!r} is dead — no pattern declares it in "
            f"suitable_domains. Curate at least one pattern or remove the enum entry."
        )


@pytest.mark.parametrize(
    ("domain", "expected_min"),
    [
        ("cybersecurity", 5),            # min 5 of 7 curated
        ("gui-computer-use", 6),         # min 6 of 11 curated
        ("personal-productivity", 6),    # min 6 of 8 curated
        ("devops", 3),                   # min 3 of 4 curated (revived dead entry)
        ("education", 5),                # min 5 of 7 curated
        ("legal-research", 4),           # min 4 of 6 curated
        ("scientific-research", 4),      # min 4 of 6 curated (revived dead entry)
        ("it-service-management", 4),    # min 4 of 6 curated
        ("workflow-automation", 6),      # min 6 of 8 curated
        ("enterprise-search", 5),        # min 5 of 7 curated
        ("e-commerce", 4),               # min 4 of 5 curated
        ("software-testing", 4),         # min 4 of 5 curated
        ("multimodal", 3),               # min 3 of 4 curated (revived dead entry)
        ("database-operations", 3),      # min 3 of 4 curated (revived dead entry)
    ],
)
def test_loader_filter_by_domain_new_domains(loader, domain, expected_min):
    """New-slung precision smoke: each added domain recalls its curated set.

    Aliases do not enter this path — filter_by_domain receives the canonical
    slug, mirroring what the pipeline's corpus resolution does.
    """
    filtered = loader.filter_by_domain(domain)
    assert len(filtered) >= expected_min, (
        f"Domain '{domain}' yielded {len(filtered)} patterns; expected >= {expected_min}"
    )
    for p in filtered:
        assert domain in p.get("suitable_domains", []), (
            f"{p['name']}: recalled for '{domain}' but not in its suitable_domains"
        )
