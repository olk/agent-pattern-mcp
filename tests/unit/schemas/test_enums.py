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
Unit tests for schema enumerations: PatternCategory, AgentDomain, AgentTopology.
"""

from src.schemas.enums import AgentDomain, AgentTopology, PatternCategory


class TestPatternCategory:
    """Test suite for PatternCategory enum."""

    def test_has_exactly_10_values(self):
        """Verify PatternCategory enum contains exactly 10 values."""
        actual_values = len(PatternCategory)
        assert actual_values == 10, f"Expected 10 values, got {actual_values}"

    def test_all_categories_present(self):
        """Verify all required categories are present."""
        expected_categories = {
            "reasoning",
            "tool_use",
            "planning",
            "reflection",
            "research_synthesis",
            "multi_agent",
            "memory",
            "retrieval",
            "safety_control",
            "observability",
        }
        actual_categories = {item.value for item in PatternCategory}
        assert actual_categories == expected_categories

    def test_is_str_enum(self):
        """Verify PatternCategory is a str Enum for JSON serialization compatibility."""
        for item in PatternCategory:
            assert isinstance(item.value, str), f"{item.name} value is not a string"

    def test_enum_member_accessible(self):
        """Verify enum members are accessible by name."""
        assert PatternCategory.REASONING.value == "reasoning"
        assert PatternCategory.TOOL_USE.value == "tool_use"
        assert PatternCategory.PLANNING.value == "planning"
        assert PatternCategory.REFLECTION.value == "reflection"
        assert PatternCategory.RESEARCH_SYNTHESIS.value == "research_synthesis"
        assert PatternCategory.MULTI_AGENT.value == "multi_agent"
        assert PatternCategory.MEMORY.value == "memory"
        assert PatternCategory.RETRIEVAL.value == "retrieval"
        assert PatternCategory.SAFETY_CONTROL.value == "safety_control"
        assert PatternCategory.OBSERVABILITY.value == "observability"


class TestAgentTopology:
    """Test suite for AgentTopology enum."""

    def test_has_8_values(self):
        """Verify AgentTopology enum contains exactly 8 values."""
        actual_values = len(AgentTopology)
        assert actual_values == 8, f"Expected 8 values, got {actual_values}"

    def test_topology_values_from_patterns(self):
        """Verify AgentTopology values match pattern topologies."""
        expected = {
            "evaluator-loop",
            "graph-orchestrated",
            "hierarchical",
            "parallel-fan-out",
            "pipeline",
            "plan-execute",
            "single-agent-loop",
            "swarm",
        }
        actual_styles = {item.value for item in AgentTopology}
        assert actual_styles == expected

    def test_is_str_enum(self):
        """Verify AgentTopology is a str Enum for JSON serialization compatibility."""
        for item in AgentTopology:
            assert isinstance(item.value, str), f"{item.name} value is not a string"

    def test_key_topology_members_accessible(self):
        """Verify key AgentTopology members are accessible by name."""
        assert AgentTopology.SINGLE_AGENT_LOOP.value == "single-agent-loop"
        assert AgentTopology.HIERARCHICAL.value == "hierarchical"
        assert AgentTopology.SWARM.value == "swarm"


class TestAgentDomain:
    """Test suite for AgentDomain enum."""

    def test_has_36_values(self):
        """Verify AgentDomain enum contains exactly 36 values.

        Grew from 20 during catalog expansion (35e6338): + database-operations,
        devops, document-processing, multimodal, scientific-research,
        web-automation. Grew from 26 during the domain-taxonomy expansion:
        + cybersecurity, e-commerce, education, enterprise-search,
        gui-computer-use, it-service-management, legal-research,
        personal-productivity, software-testing, workflow-automation.
        """
        actual_values = len(AgentDomain)
        assert actual_values == 36, f"Expected 36 values, got {actual_values}"

    def test_all_key_domains_present(self):
        """Verify all key problem-space domains are present."""
        key_domains = {
            "api-automation",
            "autonomous-task-execution",
            "code-generation",
            "complex-reasoning",
            "multi-agent-systems",
            "rag-applications",
            "tool-use-tasks",
        }
        actual_domains = {item.value for item in AgentDomain}
        for domain in key_domains:
            assert domain in actual_domains, f"Expected domain '{domain}' not found in AgentDomain"

    def test_is_str_enum(self):
        """Verify AgentDomain is a str Enum for JSON serialization compatibility."""
        for item in AgentDomain:
            assert isinstance(item.value, str), f"{item.name} value is not a string"

    def test_domain_values_are_lowercase(self):
        """Verify all AgentDomain values are lowercase strings."""
        for item in AgentDomain:
            assert item.value == item.value.lower(), (
                f"AgentDomain value '{item.value}' should be lowercase"
            )

    def test_domain_values_are_hyphenated(self):
        """Verify all AgentDomain values use hyphenated lowercase format."""
        for item in AgentDomain:
            assert "-" in item.value or "_" not in item.value, (
                f"AgentDomain value '{item.value}' should use hyphens not underscores"
            )
