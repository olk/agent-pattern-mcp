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

"""Tests for the per-topology canonical-shape guidance injected into the
GENERATE-phase system prompt.

Guards the contract that every AgentTopology enum value has explicit
guidance and that no entry can balloon the prompt size.
"""

import pytest

from src.prompts.topology_guidance import (
    DEFAULT_TOPOLOGY_GUIDANCE,
    TOPOLOGY_GUIDANCE,
    get_topology_guidance,
)
from src.schemas.enums import AgentTopology


class TestTopologyGuidanceCoverage:
    """Every enum topology must have explicit guidance."""

    def test_every_agent_topology_has_explicit_guidance(self):
        missing = [s.value for s in AgentTopology if s.value not in TOPOLOGY_GUIDANCE]
        assert missing == []

    def test_guidance_count_matches_enum_count(self):
        assert len(TOPOLOGY_GUIDANCE) == len(AgentTopology)

    def test_no_extra_keys_beyond_enum_values(self):
        enum_values = {s.value for s in AgentTopology}
        extra = set(TOPOLOGY_GUIDANCE) - enum_values
        assert extra == set()


@pytest.mark.parametrize("topology", list(AgentTopology), ids=lambda t: t.value)
class TestTopologyGuidanceEntryQuality:
    """Per-entry quality gates, reported per topology."""

    def test_entry_is_meaningful(self, topology: AgentTopology):
        guidance = TOPOLOGY_GUIDANCE[topology.value]
        assert len(guidance) >= 50, f"{topology.value}: guidance too short ({len(guidance)} chars)"

    def test_entry_within_size_bound(self, topology: AgentTopology):
        guidance = TOPOLOGY_GUIDANCE[topology.value]
        assert len(guidance) <= 800, f"{topology.value}: guidance too long ({len(guidance)} chars)"

    def test_entry_has_no_placeholders(self, topology: AgentTopology):
        guidance = TOPOLOGY_GUIDANCE[topology.value].upper()
        for placeholder in ("TODO", "XXX", "TBD", "PLACEHOLDER", "FILL ME"):
            assert placeholder not in guidance, f"{topology.value}: contains {placeholder}"


class TestDefaultFallback:
    def test_default_fallback_is_meaningful(self):
        assert 50 <= len(DEFAULT_TOPOLOGY_GUIDANCE) <= 800

    def test_default_fallback_has_no_placeholders(self):
        upper = DEFAULT_TOPOLOGY_GUIDANCE.upper()
        for placeholder in ("TODO", "XXX", "TBD", "PLACEHOLDER"):
            assert placeholder not in upper


class TestGetTopologyGuidance:
    def test_known_topology_returns_exact_entry(self):
        for topology in AgentTopology:
            assert get_topology_guidance(topology.value) is TOPOLOGY_GUIDANCE[topology.value]

    def test_unknown_topology_returns_default(self):
        assert get_topology_guidance("definitely-not-a-topology") is DEFAULT_TOPOLOGY_GUIDANCE

    def test_empty_string_returns_default(self):
        assert get_topology_guidance("") is DEFAULT_TOPOLOGY_GUIDANCE
