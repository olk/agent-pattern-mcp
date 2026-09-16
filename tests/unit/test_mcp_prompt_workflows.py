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
Unit tests for src/mcp_prompts/workflows.py (FR-247 to FR-250).

Directly registers the four workflow prompts on a bare FastMCP server with a
stub PatternLoader (no full server lifespan) and asserts the rendered content:

- register_prompts returns the registration count (4)
- explore_pattern_catalog: empty-catalog fallback, live catalog embedding,
  domain/category filter note, no-match fallback note
- compare_agent_topologies: happy path embeds both topologies + requirements
- design_agent_system_workflow: topology override is embedded
- evaluate_my_agent_system: focus note is embedded
"""

from typing import Any, cast

import pytest
from fastmcp import Client, FastMCP

from src.mcp_prompts.workflows import register_prompts
from src.patterns.loader import PatternLoader


class _StubPatternLoader:
    """Minimal PatternLoader stand-in returning fixed pattern dicts."""

    def __init__(self, patterns: list[dict[str, Any]]) -> None:
        self._patterns = patterns

    def load_all(self) -> list[dict[str, Any]]:
        return list(self._patterns)

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        return next((p for p in self._patterns if p["name"] == name), None)


def _two_patterns() -> list[dict[str, Any]]:
    return [
        {
            "name": "react",
            "context": "Reason + act loop for autonomous-task-execution agents.",
        },
        {
            "name": "supervisor-worker",
            "context": "A coordinator delegates subtasks to specialised workers.",
        },
    ]


def _as_loader(stub: _StubPatternLoader) -> PatternLoader:
    """The stub satisfies the loader protocol structurally; tests are not type-gated."""
    return cast("PatternLoader", stub)


def _register(patterns: list[dict[str, Any]] | None = None) -> FastMCP:
    server: FastMCP = FastMCP("test-workflows")
    register_prompts(server, _as_loader(_StubPatternLoader(patterns if patterns is not None else _two_patterns())))
    return server


async def _render(server: FastMCP, name: str, arguments: dict[str, str] | None = None) -> str:
    """Render a prompt via the in-process client and concatenate message texts."""
    async with Client(server) as client:
        result = await client.get_prompt(name, arguments or {})
    return "\n".join(
        m.content.text for m in result.messages if hasattr(m.content, "text") and m.content.text
    )


class TestRegistration:
    async def test_register_prompts_returns_four(self) -> None:
        """register_prompts returns the number of registered prompts (4)."""
        server: FastMCP = FastMCP("count-check")
        assert register_prompts(server, _as_loader(_StubPatternLoader(_two_patterns()))) == 4

    async def test_all_four_prompts_are_listed(self) -> None:
        """All four workflow prompt names appear in prompts/list."""
        async with Client(_register()) as client:
            prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert names == {
            "design_agent_system_workflow",
            "explore_pattern_catalog",
            "evaluate_my_agent_system",
            "compare_agent_topologies",
        }


class TestExplorePatternCatalog:
    async def test_empty_catalog_renders_misconfiguration_hint(self) -> None:
        """With no patterns loaded, the prompt explains the likely misconfiguration."""
        text = await _render(_register(patterns=[]), "explore_pattern_catalog")
        assert "empty or is misconfigured" in text
        assert "pattern_directory" in text

    async def test_catalog_body_embeds_live_pattern_names(self) -> None:
        """The rendered prompt lists the live catalog names and the count."""
        text = await _render(_register(), "explore_pattern_catalog")
        assert "2 pattern(s)" in text
        assert "react" in text
        assert "supervisor-worker" in text
        assert "Matching" not in text

    async def test_domain_filter_adds_matching_note(self) -> None:
        """A domain filter that matches descriptions adds a 'Matching' line."""
        text = await _render(
            _register(), "explore_pattern_catalog", {"domain": "autonomous-task-execution"}
        )
        assert "Matching 'autonomous-task-execution': react." in text

    async def test_category_filter_matches_on_name(self) -> None:
        """A category filter matches against pattern names."""
        text = await _render(_register(), "explore_pattern_catalog", {"category": "supervisor"})
        assert "Matching 'supervisor': supervisor-worker." in text

    async def test_no_match_falls_back_to_full_catalog(self) -> None:
        """When nothing matches, the prompt says so and still lists everything."""
        text = await _render(_register(), "explore_pattern_catalog", {"domain": "quantum-blockchain"})
        assert "No patterns matched 'quantum-blockchain'" in text
        assert "react" in text
        assert "supervisor-worker" in text


class TestCompareTopologies:
    async def test_happy_path_embeds_topologies_and_requirements(self) -> None:
        """compare_agent_topologies renders both topologies and the requirements."""
        text = await _render(
            _register(),
            "compare_agent_topologies",
            {
                "topology_a": "hierarchical",
                "topology_b": "peer-to-peer",
                "requirements": "Build a fault-tolerant ETL pipeline",
            },
        )
        assert "topology='hierarchical'" in text
        assert "topology='peer-to-peer'" in text
        assert "Build a fault-tolerant ETL pipeline" in text
        assert "generate_agent_system" in text
        assert "within 5 points" in text


class TestDesignWorkflow:
    async def test_topology_override_is_embedded(self) -> None:
        """An explicit topology override appears in the rendered tool call."""
        text = await _render(
            _register(),
            "design_agent_system_workflow",
            {"requirements": "Build a RAG assistant", "domain": "rag", "topology": "hierarchical"},
        )
        assert "requirements='Build a RAG assistant'" in text
        assert "domain='rag'" in text
        assert "topology='hierarchical'" in text

    async def test_omitted_topology_leaves_argument_out(self) -> None:
        """Without a topology argument no topology is embedded in the tool call."""
        text = await _render(
            _register(),
            "design_agent_system_workflow",
            {"requirements": "Build a RAG assistant"},
        )
        assert "topology=" not in text


class TestEvaluateWorkflow:
    async def test_focus_attribute_is_embedded(self) -> None:
        """evaluate_my_agent_system embeds the focus attribute note."""
        text = await _render(_register(), "evaluate_my_agent_system", {"focus": "safety"})
        assert "extra attention to the 'safety'" in text
        assert "evaluate_agent_system" in text

    @pytest.mark.parametrize("arguments", [None, {}])
    async def test_without_focus_no_attention_note(self, arguments: dict[str, str] | None) -> None:
        """Without focus, no attention note is rendered."""
        text = await _render(_register(), "evaluate_my_agent_system", arguments)
        assert "extra attention" not in text
