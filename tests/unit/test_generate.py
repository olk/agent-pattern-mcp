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
Unit tests for GenerateAgentSystemTool.

AC-222: Verify GenerateAgentSystemTool class exists, accepts AgentSystemArchitect
Test Case IDs: UT-13, IT-3

Validates:
- FR-222: GenerateAgentSystemTool class exists
- E-3: Failed to generate architecture design handling (ERR_003)
- E-9: LLM provider returned error handling (ERR_009)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent import LLMError, AgentSystemArchitect

# Import for mocking the pipeline
from src.pipeline import AgentPatternPipeline
from src.schemas.contracts import ToolContract, ToolContract, StateModel, MessageContract, StateField

from src.schemas.design import AgentSystemDesign, AgentSystemOverview
from src.schemas.components import Agent, Relationship
from src.schemas.enums import AgentTopology, PatternCategory

# Import the tool class and related agents
from fastmcp.exceptions import ToolError

from src.tools.generate import (
    ERROR_GENERATION_FAILED,
    ERROR_LLM_PROVIDER,
    GenerateAgentSystemOutput,
    GenerateAgentSystemTool,
    generate_agent_system_tool,
)

# Test fixtures

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
    pipeline = MagicMock()
    pipeline.generate = AsyncMock()
    # Provide a mock pattern_loader that returns None so names resolve to
    # nothing (the tool logs a WARNING and proceeds with empty patterns).
    loader = MagicMock()
    loader.get_by_name.return_value = None
    pipeline._pattern_loader = loader
    return pipeline


@pytest.fixture
def sample_architecture_design():
    """Create a sample AgentSystemDesign for testing."""
    return AgentSystemDesign(
        overview=AgentSystemOverview(
            topology=AgentTopology.HIERARCHICAL,
            category=PatternCategory.PLANNING,
            principles=["principle1", "principle2"],
        ),
        agents=[
            Agent(
                id="api-gateway",
                name="API Gateway",
                role="gateway",
                description="Entry point for all client requests",
                responsibilities=["routing", "authentication", "rate limiting"],
            ),
            Agent(
                id="user-service",
                name="User Service",
                role="service",
                description="User management microservice",
                responsibilities=["user CRUD", "authentication"],
            ),
        ],
        relationships=[
            Relationship(source="api-gateway", target="user-service", type="http", description=""),
        ],
        quality_attributes={
            "reliability": 8.0,
            "cost_efficiency": 7.0,
            "latency": 6.0,
            "output_quality": 8.0,
            "observability": 7.0,
            "safety": 7.0,
            "simplicity": 6.0,
        },
        tool_contracts=[
            ToolContract(
                tool_name="get_user",
                agent_id="user-service",
                description="Get user by ID",
                input_schema={"type": "object", "properties": {"user_id": {"type": "string"}}},
                output_schema={"type": "object"},
                auth_required=True,
            ),
        ],
        shared_state_models=[
            StateModel(
                name="User",
                fields=[
                    StateField(name="id", type="str"),
                    StateField(name="name", type="str"),
                    StateField(name="email", type="str"),
                ],
                description="User data model",
            ),
        ],
        message_contracts=[
            MessageContract(
                message_name="UserCreated",
                payload_schema={"user_id": "string"},
                published_by="user-service",
                consumed_by=[],
                description="",
            ),
        ],
    )


# AC-222: Verify GenerateAgentSystemTool class exists, accepts AgentSystemArchitect

class TestGenerateAgentSystemToolInit:
    """Test suite for GenerateAgentSystemTool initialization."""

    def test_tool_initialization_with_agent_and_pipeline(self, mock_agent, mock_pipeline):
        """
        AC-222: Verify GenerateAgentSystemTool class exists, accepts AgentSystemArchitect
        
        given_precondition: AgentSystemArchitect initialized
        when_action: System creates GenerateAgentSystemTool instance
        then_outcome: GenerateAgentSystemTool generates valid AgentSystemDesign
        """
        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        assert tool is not None
        assert tool._agent is mock_agent
        assert tool._pipeline is mock_pipeline

    def test_tool_initialization_logs_debug_message(self, mock_agent, mock_pipeline, caplog):
        """Test that initialization logs a debug message."""
        import logging
        caplog.set_level(logging.DEBUG)

        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        assert "GenerateAgentSystemTool initialized" in caplog.text


class TestGenerateAgentSystemOutput:
    """Test suite for GenerateAgentSystemOutput Pydantic model."""

    def test_valid_output_with_all_fields(self, sample_architecture_design):
        """Test valid output with all fields."""
        output = GenerateAgentSystemOutput(
            overview=sample_architecture_design.overview.model_dump(),
            agents=[c.model_dump() for c in sample_architecture_design.agents],
            relationships=[r.model_dump() for r in sample_architecture_design.relationships],
            quality_attributes=sample_architecture_design.quality_attributes,
            tool_contracts=[a.model_dump() for a in sample_architecture_design.tool_contracts],
            shared_state_models=[m.model_dump() for m in sample_architecture_design.shared_state_models],
            message_contracts=[e.model_dump() for e in sample_architecture_design.message_contracts],
        )

        assert output.overview["topology"] == sample_architecture_design.overview.topology.value
        assert len(output.agents) == 2
        assert len(output.relationships) == 1

    def test_empty_output(self):
        """Test output with default values."""
        output = GenerateAgentSystemOutput()

        assert output.overview == {}
        assert output.agents == []
        assert output.relationships == []


class TestGenerateAgentSystemToolGenerate:
    """Test suite for GenerateAgentSystemTool.generate() method."""

    @pytest.mark.asyncio
    async def test_generate_success(self, mock_agent, mock_pipeline, sample_architecture_design):
        """
        AC-222: Verify GenerateAgentSystemTool class generates valid AgentSystemDesign

        given_precondition: AgentSystemArchitect initialized
        when_action: System creates GenerateAgentSystemTool instance and calls generate()
        then_outcome: GenerateAgentSystemTool returns valid AgentSystemDesign
        """
        # Wire the pattern_loader mock so name "CQRS" resolves to a stub pattern dict.
        cqrs_dict = {"name": "CQRS", "context": "Read/write segregation", "category": "structural",
                     "quality_attributes": {"maintainability": 7, "scalability": 7,
                                            "reliability": 7, "security": 7, "performance": 7}}
        mock_pipeline._pattern_loader.get_by_name.return_value = cqrs_dict
        mock_pipeline.generate.return_value = sample_architecture_design

        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        result = await tool.generate(
            requirements="Build a scalable web application",
            topology="hierarchical",
            domain="web applications",
            selected_patterns=["CQRS"]
        )

        mock_pipeline.generate.assert_called_once_with(
            requirements="Build a scalable web application",
            topology="hierarchical",
            domain="web applications",
            selected_patterns=[cqrs_dict]
        )

        assert result['overview'] == sample_architecture_design.overview.model_dump()
        assert len(result['agents']) == 2

    @pytest.mark.asyncio
    async def test_generate_logs_info_on_start(self, mock_agent, mock_pipeline, sample_architecture_design):
        """Test that generate() logs info message at start via ctx."""
        from unittest.mock import MagicMock, AsyncMock

        mock_pipeline.generate.return_value = sample_architecture_design
        ctx = MagicMock()
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()

        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)
        await tool.generate(
            requirements="Build a scalable web application",
            topology="hierarchical",
            domain="web applications",
            selected_patterns=[],
            ctx=ctx
        )

        ctx.info.assert_called()
        info_calls = ctx.info.call_args_list
        first_call_args = info_calls[0][0][0]
        assert "generate_agent_system" in first_call_args
        assert "hierarchical" in first_call_args

    @pytest.mark.asyncio
    async def test_generate_logs_info_on_completion(self, mock_agent, mock_pipeline, sample_architecture_design):
        """Test that generate() logs info message on completion via ctx."""
        from unittest.mock import MagicMock, AsyncMock

        mock_pipeline.generate.return_value = sample_architecture_design
        ctx = MagicMock()
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()

        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)
        result = await tool.generate(
            requirements="Build a scalable web application",
            topology="hierarchical",
            domain="web applications",
            selected_patterns=[],
            ctx=ctx
        )

        ctx.info.assert_called()
        info_calls = ctx.info.call_args_list
        last_call_args = info_calls[-1][0][0]
        assert "generate_agent_system completed" in last_call_args


class TestGenerateArchitectureErrorHandling:
    """Test suite for GenerateAgentSystemTool error handling."""

    @pytest.mark.asyncio
    async def test_llm_error_raises_generate_error(self, mock_agent, mock_pipeline):
        """
        E-9: ERR_009 - LLM provider returned error

        given_precondition: LLM provider error occurs
        when_action: generate() is called
        then_outcome: ToolError is raised with ERR_009
        """
        llm_error = LLMError(provider="openai", error="ERR_009", provider_message="API key invalid")
        mock_pipeline.generate.side_effect = llm_error

        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        with pytest.raises(ToolError) as exc_info:
            await tool.generate(
                requirements="Build a scalable web application",
                topology="hierarchical",
                domain="web applications",
                selected_patterns=[]
            )

        error_msg = str(exc_info.value)
        assert ERROR_LLM_PROVIDER in error_msg
        assert "LLM provider returned error" in error_msg

    @pytest.mark.asyncio
    async def test_llm_error_logs_error_with_context(self, mock_agent, mock_pipeline):
        """
        E-9: ERR_009 - LLM provider returned error logging context

        Validates that ctx.error is called with error details
        """
        from unittest.mock import MagicMock, AsyncMock

        llm_error = LLMError(provider="openai", error="ERR_009", provider_message="API key invalid")
        mock_pipeline.generate.side_effect = llm_error
        ctx = MagicMock()
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()

        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        with pytest.raises(ToolError):
            await tool.generate(
                requirements="Build a scalable web application",
                topology="hierarchical",
                domain="web applications",
                selected_patterns=[],
                ctx=ctx
            )

        ctx.error.assert_called()
        call_args = ctx.error.call_args[0][0]
        assert "LLM provider error during generation" in call_args

    @pytest.mark.asyncio
    async def test_generation_failure_raises_error(self, mock_agent, mock_pipeline):
        """
        E-3: ERR_003 - Failed to generate architecture design

        given_precondition: Generation fails for non-LLM reason
        when_action: generate() is called
        then_outcome: ToolError is raised with ERR_003
        """
        mock_pipeline.generate.side_effect = Exception("Generation failed due to invalid requirements")

        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        with pytest.raises(ToolError) as exc_info:
            await tool.generate(
                requirements="Build a scalable web application",
                topology="hierarchical",
                domain="web applications",
                selected_patterns=[]
            )

        error_msg = str(exc_info.value)
        assert ERROR_GENERATION_FAILED in error_msg
        assert "Failed to generate agent system design" in error_msg

    @pytest.mark.asyncio
    async def test_generation_failure_logs_error_with_context(self, mock_agent, mock_pipeline):
        """
        E-3: ERR_003 - Failed to generate architecture design logging context

        Validates that ctx.error is called with error details
        """
        from unittest.mock import MagicMock, AsyncMock

        mock_pipeline.generate.side_effect = Exception("Invalid requirements format")
        ctx = MagicMock()
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()

        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        with pytest.raises(ToolError):
            await tool.generate(
                requirements="Build a scalable web application",
                topology="hierarchical",
                domain="web applications",
                selected_patterns=[],
                ctx=ctx
            )

        ctx.error.assert_called()
        call_args = ctx.error.call_args[0][0]
        assert "Failed to generate agent system design" in call_args


class TestGenerateAgentSystemToolFactory:
    """Test suite for generate_agent_system_tool factory function."""

    def test_factory_creates_tool_with_correct_dependencies(self, mock_agent, mock_pipeline):
        """
        DP-4: Factory Pattern - Consistent tool initialization with proper dependencies
        
        given_precondition: agent and pipeline available
        when_action: factory function is called
        then_outcome: Tool instance created with correct dependencies
        """
        tool = generate_agent_system_tool(agent=mock_agent, pipeline=mock_pipeline)

        assert tool is not None
        assert tool._agent is mock_agent
        assert tool._pipeline is mock_pipeline


class TestMapToOutput:
    """Test suite for _map_to_output helper method."""

    def test_maps_all_fields_correctly(self, mock_agent, mock_pipeline, sample_architecture_design):
        """Test that all AgentSystemDesign fields are mapped to output."""
        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        output = tool._map_to_output(sample_architecture_design)

        assert output.overview["topology"] == sample_architecture_design.overview.topology.value
        assert output.overview["category"] == sample_architecture_design.overview.category.value
        assert len(output.agents) == len(sample_architecture_design.agents)
        assert output.agents[0]["id"] == sample_architecture_design.agents[0].id
        assert output.quality_attributes == sample_architecture_design.quality_attributes


class TestIsLlmError:
    """Test suite for _is_llm_error helper method."""

    def test_returns_true_for_llm_error(self, mock_agent, mock_pipeline):
        """Test that LLMError returns True."""
        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        error = LLMError(provider="openai", error="ERR_009", provider_message="API key invalid")
        assert tool._is_llm_error(error) is True

    def test_returns_false_for_generic_error(self, mock_agent, mock_pipeline):
        """Test that generic Exception returns False."""
        tool = GenerateAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        error = Exception("Some other error")
        assert tool._is_llm_error(error) is False
