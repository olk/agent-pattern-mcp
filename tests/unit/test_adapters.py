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
Unit tests for src/tools/_adapters.py.
"""

import pytest

from src.errors import ERROR_INVALID_AGENT_SYSTEM, MalformedAgentSystemOverviewError
from src.schemas.enums import AgentTopology, PatternCategory
from src.tools._adapters import _parse_overview, design_from_dict


class TestParseOverviewValidInput:
    """Happy-path: valid overview dicts are accepted unchanged."""

    def test_accepts_valid_overview_dict(self):
        """Valid input returns a typed AgentSystemOverview."""
        data = {
            "topology": "single-agent-loop",
            "category": "reasoning",
            "principles": ["principle1", "principle2"],
            "constraints": ["constraint1"],
        }
        result = _parse_overview(data)

        assert result.topology == AgentTopology.SINGLE_AGENT_LOOP
        assert result.category == PatternCategory.REASONING
        assert result.principles == ["principle1", "principle2"]
        assert result.constraints == ["constraint1"]

    def test_preserves_exact_topology_from_input(self):
        """The topology value from the input is preserved when valid."""
        for topo in ["hierarchical", "swarm", "plan-execute"]:
            data = {
                "topology": topo,
                "category": "reasoning",
                "principles": ["p1"],
                "constraints": [],
            }
            result = _parse_overview(data)
            assert result.topology.value == topo

    def test_accepts_minimal_valid_overview(self):
        """Only required fields (topology, category, principles[min=1]) are needed."""
        data = {
            "topology": "hierarchical",
            "category": "reasoning",
            "principles": ["p1"],
        }
        result = _parse_overview(data)
        assert result.topology == AgentTopology.HIERARCHICAL
        assert result.category == PatternCategory.REASONING
        assert result.principles == ["p1"]


class TestParseOverviewInvalidInput:
    """Malformed input raises MalformedAgentSystemOverviewError (ERR_012)."""

    def _assert_rejects(self, data: dict, expected_locator: str = "overview"):
        """Helper: asserts that _parse_overview rejects data with ERR_012."""
        with pytest.raises(MalformedAgentSystemOverviewError) as exc_info:
            _parse_overview(data)
        exc = exc_info.value
        assert exc.code == ERROR_INVALID_AGENT_SYSTEM
        assert exc.locator == expected_locator
        assert exc.errors is not None
        assert len(exc.errors) > 0

    def test_rejects_unknown_topology(self):
        """Unknown topology string raises ERR_012."""
        self._assert_rejects({
            "topology": "completely-unknown-topology",
            "category": "reasoning",
            "principles": ["p1"],
        })

    def test_rejects_missing_topology(self):
        """Missing 'topology' field raises ERR_012."""
        self._assert_rejects({
            "category": "reasoning",
            "principles": ["p1"],
        })

    def test_rejects_missing_category(self):
        """Missing 'category' field raises ERR_012."""
        self._assert_rejects({
            "topology": "hierarchical",
            "principles": ["p1"],
        })

    def test_rejects_invalid_category(self):
        """Non-existent category value raises ERR_012."""
        self._assert_rejects({
            "topology": "hierarchical",
            "category": "not-a-real-category",
            "principles": ["p1"],
        })

    def test_rejects_empty_principles(self):
        """Empty principles list violates min_length=1 and raises ERR_012."""
        self._assert_rejects({
            "topology": "hierarchical",
            "category": "reasoning",
            "principles": [],
        })

    def test_rejects_missing_principles(self):
        """Missing 'principles' field raises ERR_012."""
        self._assert_rejects({
            "topology": "hierarchical",
            "category": "reasoning",
        })

    def test_rejects_null_overview(self):
        """None/null overview raises ERR_012."""
        self._assert_rejects({})

    def test_does_not_silently_default_to_hierarchical(self, caplog):
        """
        When validation fails the error is raised, not silently replaced
        with hierarchical + reasoning placeholder.
        """
        import logging
        with caplog.at_level(logging.WARNING):
            with pytest.raises(MalformedAgentSystemOverviewError):
                _parse_overview({
                    "topology": "unknown",
                    "category": "reasoning",
                    "principles": [],
                })
        assert any("Malformed agent system overview" in r.message for r in caplog.records)


class TestDesignFromDict:
    """design_from_dict propagates _parse_overview errors."""

    def _assert_rejects(self, data: dict):
        with pytest.raises(MalformedAgentSystemOverviewError) as exc_info:
            design_from_dict(data)
        exc = exc_info.value
        assert exc.code == ERROR_INVALID_AGENT_SYSTEM

    def test_rejects_malformed_overview_in_design(self):
        """An overview that fails validation surfaces ERR_012."""
        self._assert_rejects({
            "overview": {
                "topology": "not-a-valid-topology",
                "category": "reasoning",
                "principles": ["p1"],
            },
            "agents": [
                {
                    "id": "c1",
                    "name": "Agent 1",
                    "type": "service",
                    "description": "A component",
                    "responsibilities": ["test"],
                }
            ],
        })

    def test_accepts_valid_architecture_design(self):
        """Full valid architecture dict is accepted."""
        data = {
            "overview": {
                "topology": "single-agent-loop",
                "category": "reasoning",
                "principles": ["p1"],
                "constraints": [],
            },
            "agents": [
                {
                    "id": "api-gateway",
                    "name": "API Gateway",
                    "type": "gateway",
                    "description": "Gateway component",
                    "responsibilities": ["routing"],
                }
            ],
        }
        result = design_from_dict(data)
        assert result.overview.topology == AgentTopology.SINGLE_AGENT_LOOP
        assert len(result.agents) == 1
