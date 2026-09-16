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
Unit tests for the pattern catalog access tools.
"""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from src.patterns.loader import PatternLoader
from src.tools.patterns import (
    GetAgentPatternTool,
    ListAgentPatternsTool,
    get_agent_pattern_tool,
    list_agent_patterns_tool,
)


@pytest.fixture
def loader():
    """Load patterns from the bundled pattern/ directory."""
    return PatternLoader()


@pytest.fixture
def list_tool(loader):
    return ListAgentPatternsTool(loader)


@pytest.fixture
def get_tool(loader):
    return GetAgentPatternTool(loader)


@pytest.mark.asyncio
async def test_list_patterns_returns_all(list_tool):
    """list_agent_patterns returns entries for all bundled patterns."""
    result = await list_tool.list_agent_patterns()
    assert isinstance(result, list)
    MIN_PATTERNS = 30
    assert len(result) >= MIN_PATTERNS, f"Expected {MIN_PATTERNS}+ patterns, got {len(result)}"


@pytest.mark.asyncio
async def test_list_patterns_entries_have_name_and_description(list_tool):
    """Each entry has 'name' and 'description' keys only (minimal output)."""
    result = await list_tool.list_agent_patterns()
    assert result
    for entry in result:
        assert set(entry.keys()) == {"name", "description"}, (
            f"Entry should have only 'name' and 'description', got: {entry.keys()}"
        )
        assert isinstance(entry["name"], str)
        assert entry["name"]
        assert isinstance(entry["description"], str)


@pytest.mark.asyncio
async def test_list_patterns_minimal_output_no_uri(list_tool):
    """The 'uri' field from the resource format must not leak into tool output."""
    result = await list_tool.list_agent_patterns()
    assert result
    for entry in result:
        assert "uri" not in entry, "tool output must not include 'uri'"


@pytest.mark.asyncio
async def test_list_patterns_category_filter_planning(list_tool):
    """category='planning' returns only planning patterns."""
    result = await list_tool.list_agent_patterns(category="planning")
    assert result
    assert all(isinstance(e["name"], str) for e in result)
    names = {e["name"] for e in result}
    assert "plan-and-solve" in names


@pytest.mark.asyncio
async def test_list_patterns_category_filter_reasoning(list_tool):
    """category='reasoning' returns only reasoning patterns."""
    result = await list_tool.list_agent_patterns(category="reasoning")
    assert result
    names = {e["name"] for e in result}
    assert "chain-of-thought" in names


@pytest.mark.asyncio
async def test_list_patterns_category_unknown_returns_empty(list_tool):
    """Unknown category returns empty list (graceful, not error)."""
    result = await list_tool.list_agent_patterns(category="not-a-real-category")
    assert result == []


@pytest.mark.asyncio
async def test_list_patterns_domain_filter(list_tool):
    """domain filter matches against suitable_domains."""
    result = await list_tool.list_agent_patterns(domain="multi-agent-systems")
    assert isinstance(result, list)
    unfiltered = await list_tool.list_agent_patterns()
    assert len(result) <= len(unfiltered)


@pytest.mark.asyncio
async def test_get_pattern_returns_full_json(get_tool):
    """get_agent_pattern returns the complete pattern dict."""
    result = await get_tool.get_agent_pattern(name="react")
    assert isinstance(result, dict)
    assert result["name"] == "react"
    for field in ("category", "context", "benefits", "tradeoffs", "quality_attributes"):
        assert field in result, f"Missing required field: {field}"


@pytest.mark.asyncio
async def test_get_pattern_unknown_raises_tool_error(get_tool):
    """Unknown pattern name raises ToolError."""
    with pytest.raises(ToolError, match="Pattern not found"):
        await get_tool.get_agent_pattern(name="does-not-exist-xyz")


@pytest.mark.asyncio
async def test_get_pattern_supervisor_worker(get_tool):
    """Spot-check: supervisor-worker pattern is retrievable."""
    result = await get_tool.get_agent_pattern(name="supervisor-worker")
    assert result["name"] == "supervisor-worker"
    assert result["category"] == "multi_agent"


def test_factory_functions_return_instances(loader):
    """Factory functions return correctly-typed instances."""
    list_inst = list_agent_patterns_tool(loader)
    get_inst = get_agent_pattern_tool(loader)
    assert isinstance(list_inst, ListAgentPatternsTool)
    assert isinstance(get_inst, GetAgentPatternTool)
