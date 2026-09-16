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
Unit tests for AnalyzeAgentSystemTool.
"""

from unittest.mock import MagicMock

import pytest

from src.agent import AgentSystemArchitect

from src.pipeline import AnalysisResult, AgentPatternPipeline
from src.schemas.quality import QualityMetrics

from fastmcp.exceptions import ToolError

from src.tools.analyze import (
    ERROR_LLM_PROVIDER,
    AnalyzeAgentSystemOutput,
    AnalyzeAgentSystemTool,
    analyze_agent_system_tool,
)


@pytest.fixture
def mock_agent():
    """Create a mock AgentSystemArchitect."""
    agent = MagicMock(spec=AgentSystemArchitect)
    agent._generator = MagicMock()
    agent._generator.provider = "openai"
    agent._generator.config.model = "gpt-4"
    return agent


@pytest.fixture
def mock_pipeline():
    """Create a mock AgentPatternPipeline."""
    pipeline = MagicMock(spec=AgentPatternPipeline)
    return pipeline


@pytest.fixture
def sample_quality_metrics():
    """Create sample QualityMetrics for testing."""
    return QualityMetrics(
        reliability=8.0,
        cost_efficiency=7.5,
        latency=7.0,
        output_quality=8.5,
        observability=7.0,
        safety=8.0
    )


@pytest.fixture
def sample_analysis_result(sample_quality_metrics):
    """Create a sample AnalysisResult for testing."""
    return AnalysisResult(
        strengths=["High scalability", "Strong reliability"],
        weaknesses=["Complex initial setup"],
        recommendations=["Consider using patterns for multi-agent coordination"],
        quality_metrics=sample_quality_metrics,
        recommended_topology="hierarchical",
        selected_patterns=[
            {"name": "supervisor-worker", "topology": "hierarchical", "context": "Hierarchical task decomposition", "category": "planning", "benefits": ["Task decomposition"], "tradeoffs": ["Complexity"], "quality_attributes": {"reliability": 7.0}},
            {"name": "react", "topology": "single-agent-loop", "context": "ReAct agent pattern", "category": "reasoning", "benefits": ["Simple"], "tradeoffs": ["Limited"], "quality_attributes": {"reliability": 6.0}}
        ],
    )


class TestAnalyzeAgentSystemToolInit:
    """Test suite for AnalyzeAgentSystemTool initialization."""

    def test_tool_initialization_with_agent_and_pipeline(self, mock_agent, mock_pipeline):
        """Verify AnalyzeAgentSystemTool class exists and accepts agent and pipeline."""
        tool = AnalyzeAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        assert tool is not None
        assert isinstance(tool, AnalyzeAgentSystemTool)
        assert tool._agent is mock_agent
        assert tool._pipeline is mock_pipeline

    def test_factory_function_creates_tool(self, mock_agent, mock_pipeline):
        """Factory function returns properly initialized tool."""
        tool = analyze_agent_system_tool(agent=mock_agent, pipeline=mock_pipeline)

        assert tool is not None
        assert isinstance(tool, AnalyzeAgentSystemTool)
        assert tool._agent is mock_agent
        assert tool._pipeline is mock_pipeline


class TestAnalyzeAgentSystemOutput:
    """Test suite for AnalyzeAgentSystemOutput model."""

    def test_output_model_with_all_fields(self, sample_quality_metrics):
        """Creating output with all fields sets them correctly."""
        output = AnalyzeAgentSystemOutput(
            strengths=["High scalability"],
            weaknesses=["Complex setup"],
            recommendations=["Use patterns"],
            recommended_topology="hierarchical",
            selected_patterns=[{"name": "test-pattern"}],
            quality_metrics={
                "reliability": 8.0,
                "cost_efficiency": 7.5,
                "latency": 7.0,
                "output_quality": 8.5,
                "observability": 7.0,
                "safety": 8.0
            }
        )

        assert len(output.strengths) == 1
        assert len(output.weaknesses) == 1
        assert len(output.recommendations) == 1
        assert output.recommended_topology == "hierarchical"
        assert len(output.selected_patterns) == 1

    def test_output_model_default_values(self):
        """Creating output with defaults sets them correctly."""
        output = AnalyzeAgentSystemOutput()

        assert output.strengths == []
        assert output.weaknesses == []
        assert output.recommendations == []
        assert output.recommended_topology == ""
        assert output.selected_patterns == []
        assert output.quality_metrics is None


class TestAnalyzeAgentSystemToolAnalyze:
    """Test suite for AnalyzeAgentSystemTool.analyze() method."""

    @pytest.mark.asyncio
    async def test_analyze_returns_output_successfully(
        self,
        mock_agent,
        mock_pipeline,
        sample_analysis_result
    ):
        """analyze() returns dict with analysis results."""
        mock_pipeline.analyze.return_value = sample_analysis_result

        tool = AnalyzeAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        expected_output = AnalyzeAgentSystemOutput(
            strengths=["High scalability", "Strong reliability"],
            weaknesses=["Complex initial setup"],
            recommendations=["Consider using patterns for multi-agent coordination"],
            recommended_topology="hierarchical",
            selected_patterns=[],
            quality_metrics={
                "reliability": 8.0,
                "cost_efficiency": 7.5,
                "latency": 7.0,
                "output_quality": 8.5,
                "observability": 7.0,
                "safety": 8.0
            }
        )
        tool._map_to_output = MagicMock(return_value=expected_output)

        output = await tool.analyze(
            requirements="System needs high scalability",
            domain="multi-agent-systems"
        )

        assert isinstance(output, dict)
        assert len(output['strengths']) == 2
        assert output['recommended_topology'] == "hierarchical"

    @pytest.mark.asyncio
    async def test_analyze_maps_quality_metrics_correctly(
        self,
        mock_agent,
        mock_pipeline,
        sample_analysis_result
    ):
        """Quality metrics are properly mapped to dict."""
        mock_pipeline.analyze.return_value = sample_analysis_result

        tool = AnalyzeAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        expected_output = AnalyzeAgentSystemOutput(
            strengths=["High scalability"],
            weaknesses=["Complex setup"],
            recommendations=["Use patterns"],
            recommended_topology="hierarchical",
            selected_patterns=[],
            quality_metrics={
                "reliability": 8.0,
                "cost_efficiency": 7.5,
                "latency": 7.0,
                "output_quality": 8.5,
                "observability": 7.0,
                "safety": 8.0
            }
        )
        tool._map_to_output = MagicMock(return_value=expected_output)

        output = await tool.analyze(
            requirements="System needs high scalability",
            domain="multi-agent-systems"
        )

        assert output['quality_metrics'] is not None
        assert "reliability" in output['quality_metrics']
        assert "cost_efficiency" in output['quality_metrics']
        assert "latency" in output['quality_metrics']
        assert "output_quality" in output['quality_metrics']
        assert "observability" in output['quality_metrics']
        assert "safety" in output['quality_metrics']

    @pytest.mark.asyncio
    async def test_analyze_delegates_to_pipeline(
        self,
        mock_agent,
        mock_pipeline,
        sample_analysis_result
    ):
        """analyze() delegates to pipeline.analyze with correct parameters."""
        mock_pipeline.analyze.return_value = sample_analysis_result

        tool = AnalyzeAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        tool._map_to_output = MagicMock(return_value=AnalyzeAgentSystemOutput())

        await tool.analyze(
            requirements="System needs high scalability",
            domain="multi-agent-systems"
        )

        mock_pipeline.analyze.assert_called_once_with(
            requirements="System needs high scalability",
            domain="multi-agent-systems"
        )


class TestAnalyzeArchitectureErrorHandling:
    """Test suite for AnalyzeAgentSystemTool error handling."""

    @pytest.mark.asyncio
    async def test_llm_error_raises_tool_error(self, mock_agent, mock_pipeline):
        """LLM error raises ToolError."""
        from src.agent import LLMError
        mock_pipeline.analyze.side_effect = LLMError(
            provider="openai",
            error=ERROR_LLM_PROVIDER,
            provider_message="API rate limit exceeded"
        )

        tool = AnalyzeAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        with pytest.raises(ToolError):
            await tool.analyze(
                requirements="System needs high scalability",
                domain="multi-agent-systems"
            )

    @pytest.mark.asyncio
    async def test_no_patterns_error_returns_empty_result(self, mock_agent, mock_pipeline):
        """No patterns found returns empty result with warning."""
        mock_pipeline.analyze.side_effect = Exception("no patterns found for domain")

        tool = AnalyzeAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        output = await tool.analyze(
            requirements="System needs high scalability",
            domain="unknown-domain"
        )

        assert output['strengths'] == []
        assert len(output['weaknesses']) > 0
        assert "No patterns found" in output['weaknesses'][0]
        assert output['recommended_topology'] == "single-agent-loop"
        assert output['recommended_pattern_name'] == "react"
        assert output['selected_patterns'] == []

    def test_is_llm_error_detects_llm_errors(self, mock_agent, mock_pipeline):
        """_is_llm_error returns True for LLMError instances."""
        tool = AnalyzeAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        from src.agent import LLMError
        error = LLMError(provider="openai", error="ERR_009", provider_message="test")

        assert tool._is_llm_error(error) is True

    def test_is_no_patterns_error_detects_pattern_errors(self, mock_agent, mock_pipeline):
        """_is_no_patterns_error returns True for no patterns errors."""
        tool = AnalyzeAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        assert tool._is_no_patterns_error(Exception("no patterns found")) is True
        assert tool._is_no_patterns_error(Exception("no pattern found")) is True
        assert tool._is_no_patterns_error(Exception("pattern not found")) is True
        assert tool._is_no_patterns_error(Exception("empty result")) is True

        assert tool._is_no_patterns_error(Exception("connection timeout")) is False
