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
Unit tests for DesignAgentSystemTool.

AC-224: Verify DesignAgentSystemTool class exists and delegates to pipeline.run
Test Case IDs: UT-14, IT-1

Validates:
- FR-224: DesignAgentSystemTool class exists
- E-1: Requirements validation fails handling (ERR_001)
- E-9: LLM provider returned error handling (ERR_009)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent import AgentSystemArchitect

from src.pipeline import AgentPatternPipeline
from src.schemas.contracts import MessageContract

from src.schemas.design import AgentSystemDesign, AgentSystemOverview, Agent, Relationship
from src.schemas.enums import AgentTopology, PatternCategory
from src.schemas.evaluation import AgentSystemEvaluation, EvaluationSummary, MetricResult, PipelineResult

# Import the tool class and related agents
from src.tools.design import (
    ERROR_LLM_PROVIDER,
    ERROR_REQUIREMENTS_VALIDATION,
    DesignAgentSystemOutput,
    DesignAgentSystemTool,
    design_agent_system_tool,
)
from fastmcp.exceptions import ToolError

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
    pipeline = MagicMock(spec=AgentPatternPipeline)
    pipeline.run_design = AsyncMock()
    return pipeline


@pytest.fixture
def sample_refined_architecture():
    """Create a sample RefinedArchitecture for testing."""
    design = AgentSystemDesign(
        overview=AgentSystemOverview(
            topology=AgentTopology.HIERARCHICAL,
            category=PatternCategory.PLANNING,
            principles=["principle1", "principle2"],
        ),
        agents=[
            Agent(id="api-gateway", name="API Gateway", role="gateway", description="API Gateway component", responsibilities=["routing"]),
            Agent(id="user-service", name="User Service", role="service", description="User Service component", responsibilities=["user management"]),
            Agent(id="order-service", name="Order Service", role="service", description="Order Service component", responsibilities=["order management"]),
        ],
        relationships=[
            Relationship(source="api-gateway", target="user-service", type="http", description=""),
            Relationship(source="api-gateway", target="order-service", type="http", description=""),
        ],
        quality_attributes={"reliability": 8.0, "cost_efficiency": 7.5},
        tool_contracts=[],
        shared_state_models=[],
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

    evaluation = AgentSystemEvaluation(
        summary=EvaluationSummary(
            reasoning="test rationale",
            overall_score=85.5,
            strengths=["Good architecture design"],
            weaknesses=["Consider additional monitoring"],
            critical_findings=["None"]
        ),
        metrics=[
            MetricResult(name="overall_quality", score=85.5, description="Overall quality", findings=[], recommendations=[])
        ],
        recommendations={}
    )

    return PipelineResult(
        design=design,
        evaluation=evaluation,
        attempts=2,
        final_topology="hierarchical",
        final_quality_score=85.5,
        alternative_topologies=[],
        matched_domains=[],
        is_fallback=False,
    )


@pytest.fixture
def sample_architecture_design():
    """Create a sample AgentSystemDesign for testing."""
    return AgentSystemDesign(
        overview=AgentSystemOverview(
            topology=AgentTopology.HIERARCHICAL,
            category=PatternCategory.PLANNING,
            principles=["principle1"],
        ),
        agents=[
            Agent(id="api-gateway", name="API Gateway", role="gateway", description="API Gateway component", responsibilities=["routing"]),
            Agent(id="user-service", name="User Service", role="service", description="User Service component", responsibilities=["user management"]),
        ],
        relationships=[
            Relationship(source="api-gateway", target="user-service", type="http", description=""),
        ],
        quality_attributes={"reliability": 8.0},
        tool_contracts=[],
        shared_state_models=[],
        message_contracts=[],
    )


# AC-224: Verify DesignAgentSystemTool class exists, accepts AgentSystemArchitect

class TestDesignAgentSystemToolInit:
    """Test suite for DesignAgentSystemTool initialization."""

    def test_tool_initialization_with_agent_and_pipeline(self, mock_agent, mock_pipeline):
        """
        AC-224: Verify DesignAgentSystemTool class exists, accepts AgentSystemArchitect
        
        given_precondition: AgentSystemArchitect initialized
        when_action: System creates DesignAgentSystemTool instance
        then_outcome: DesignAgentSystemTool class exists with proper initialization
        """
        # When: Creating DesignAgentSystemTool with agent and pipeline
        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        # Then: Tool should be initialized properly
        assert tool is not None
        assert isinstance(tool, DesignAgentSystemTool)
        assert tool._agent is mock_agent
        assert tool._pipeline is mock_pipeline

    def test_factory_function_creates_tool(self, mock_agent, mock_pipeline):
        """
        DP-4: Factory Pattern - Consistent tool initialization
        
        given_precondition: agent and pipeline available
        when_action: Factory function is called
        then_outcome: Properly initialized tool is returned
        """
        # When: Using factory function to create tool
        tool = design_agent_system_tool(agent=mock_agent, pipeline=mock_pipeline)

        # Then: Should return properly initialized tool
        assert tool is not None
        assert isinstance(tool, DesignAgentSystemTool)
        assert tool._agent is mock_agent
        assert tool._pipeline is mock_pipeline


class TestDesignAgentSystemOutput:
    """Test suite for DesignAgentSystemOutput model."""

    def test_output_model_with_all_fields(self, sample_refined_architecture):
        """
        FR-224: Returns PipelineResult combining AgentSystemDesign and AgentSystemEvaluation
        ENT-12: AgentSystemDesign with overview, agents, relationships, patterns, etc.
        
        given_precondition: RefinedArchitecture data available
        when_action: Creating output model
        then_outcome: All fields are properly set
        """
        # When: Creating output with all fields
        output = DesignAgentSystemOutput(
            design={
                "overview": {"title": "Test Architecture"},
                "agents": [{"id": "test", "name": "Test Agent"}],
                "relationships": [],
                "patterns": [],
                "quality_attributes": {},
                "tool_contracts": [],
                "shared_state_models": [],
                "message_contracts": [],
            },
            attempts=2,
            final_quality_score=85.5
        )

        # Then: All fields should be set correctly
        assert "overview" in output.design
        assert output.attempts == 2
        assert output.final_quality_score == 85.5

    def test_output_model_default_values(self):
        """
        given_precondition: None
        when_action: Creating output with defaults
        then_outcome: Default values are set correctly
        """
        # When: Creating output with minimal data
        output = DesignAgentSystemOutput()

        # Then: Default values should be set
        assert output.design == {}
        assert output.attempts == 1
        assert output.final_quality_score == 0.0


class TestDesignAgentSystemToolDesign:
    """Test suite for DesignAgentSystemTool.design() method."""

    @pytest.mark.asyncio
    async def test_design_returns_output_successfully(
        self,
        mock_agent,
        mock_pipeline,
        sample_refined_architecture
    ):
        """
        FR-224: DesignAgentSystemTool class delegates to pipeline.run
        
        given_precondition: Pipeline configured with patterns
        when_action: design() is called with requirements and domain
        then_outcome: dict is returned with complete design
        """
        mock_pipeline.run_design.return_value = sample_refined_architecture

        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        output = await tool.design(
            requirements="System needs high scalability",
            domain="microservices"
        )

        assert isinstance(output, dict)
        assert "design" in output
        assert output["attempts"] == 2
        assert output["final_quality_score"] == 85.5

    @pytest.mark.asyncio
    async def test_design_with_override_topology(
        self,
        mock_agent,
        mock_pipeline,
        sample_refined_architecture
    ):
        """
        CF-1: OPARAM-1 (override_topology) parameter
        
        given_precondition: Pipeline configured
        when_action: design() is called with override_topology
        then_outcome: Pipeline.run is called with override_topology as style
        """
        mock_pipeline.run_design.return_value = sample_refined_architecture

        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        await tool.design(
            requirements="System needs high scalability",
            domain="microservices",
            override_topology="hierarchical"
        )

        mock_pipeline.run_design.assert_called_once_with(
            requirements="System needs high scalability",
            domain="microservices",
            topology="hierarchical"
        )

    @pytest.mark.asyncio
    async def test_design_rejects_invalid_override_topology(
        self,
        mock_agent,
        mock_pipeline,
        sample_refined_architecture
    ):
        """
        Strict enum validation: override_topology outside the AgentTopology
        enum is rejected with a ToolError before the pipeline is invoked.
        """
        mock_pipeline.run_design.return_value = sample_refined_architecture

        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        with pytest.raises(ToolError) as exc_info:
            await tool.design(
                requirements="System needs high scalability",
                domain="microservices",
                override_topology="event-driven"
            )

        assert "ERR_001" in str(exc_info.value)
        mock_pipeline.run_design.assert_not_called()

    @pytest.mark.asyncio
    async def test_design_delegates_to_pipeline(
        self,
        mock_agent,
        mock_pipeline,
        sample_refined_architecture
    ):
        """
        DF-1: Flow - MCP Client -> DesignAgentSystemTool.design()
              -> AgentPatternPipeline.run()
        
        given_precondition: Pipeline configured
        when_action: design() is called
        then_outcome: Pipeline.run is called with correct parameters
        """
        mock_pipeline.run_design.return_value = sample_refined_architecture

        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        await tool.design(
            requirements="System needs high scalability",
            domain="microservices"
        )

        mock_pipeline.run_design.assert_called_once_with(
            requirements="System needs high scalability",
            domain="microservices",
            topology=None
        )

    @pytest.mark.asyncio
    async def test_design_maps_design_correctly(
        self,
        mock_agent,
        mock_pipeline,
        sample_refined_architecture
    ):
        """
        ENT-12: AgentSystemDesign - Complete architecture design
        
        given_precondition: RefinedArchitecture with AgentSystemDesign
        when_action: design() is called
        then_outcome: AgentSystemDesign is properly mapped to dict
        """
        mock_pipeline.run_design.return_value = sample_refined_architecture

        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        output = await tool.design(
            requirements="System needs high scalability",
            domain="microservices"
        )

        design = output["design"]
        assert "overview" in design
        assert "agents" in design
        assert "relationships" in design
        assert len(design["agents"]) == 3

    @pytest.mark.asyncio
    async def test_design_preserves_populated_contracts(
        self,
        mock_agent,
        mock_pipeline,
        sample_refined_architecture
    ):
        """
        tool_contracts, shared_state_models, and message_contracts from PipelineResult
        are preserved verbatim in the tool's output dict.
        """
        mock_pipeline.run_design.return_value = sample_refined_architecture

        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        output = await tool.design(
            requirements="System needs high scalability",
            domain="microservices"
        )

        design = output["design"]
        assert len(design["tool_contracts"]) == 0
        assert len(design["shared_state_models"]) == 0
        assert len(design["message_contracts"]) == 1
        assert design["message_contracts"][0]["message_name"] == "UserCreated"


class TestDesignArchitectureErrorHandling:
    """Test suite for DesignAgentSystemTool error handling."""

    @pytest.mark.asyncio
    async def test_empty_requirements_raises_error(self, mock_agent, mock_pipeline):
        """
        E-1: ERR_001 - Requirements validation fails (HTTP 400, severity: warn)
        
        given_precondition: Empty requirements provided
        when_action: design() is called
        then_outcome: ToolError is raised with ERR_001
        """
        from fastmcp.exceptions import ToolError

        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        with pytest.raises(ToolError) as exc_info:
            await tool.design(
                requirements="",
                domain="microservices"
            )

        assert ERROR_REQUIREMENTS_VALIDATION in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_domain_raises_error(self, mock_agent, mock_pipeline):
        """
        E-1: ERR_001 - Requirements validation fails (HTTP 400, severity: warn)
        
        given_precondition: Empty domain provided
        when_action: design() is called
        then_outcome: ToolError is raised with ERR_001
        """
        from fastmcp.exceptions import ToolError

        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        with pytest.raises(ToolError) as exc_info:
            await tool.design(
                requirements="Valid requirements",
                domain=""
            )

        assert ERROR_REQUIREMENTS_VALIDATION in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_whitespace_only_requirements_raises_error(self, mock_agent, mock_pipeline):
        """
        E-1: ERR_001 - Requirements validation fails (HTTP 400, severity: warn)
        
        given_precondition: Whitespace-only requirements provided
        when_action: design() is called
        then_outcome: ToolError is raised with ERR_001
        """
        from fastmcp.exceptions import ToolError

        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        with pytest.raises(ToolError) as exc_info:
            await tool.design(
                requirements="   ",
                domain="microservices"
            )

        assert ERROR_REQUIREMENTS_VALIDATION in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_llm_error_raises_tool_error(self, mock_agent, mock_pipeline):
        """
        E-9: ERR_009 - LLM provider returned error (HTTP 502, severity: error)
        
        given_precondition: LLM provider returns error
        when_action: design() is called
        then_outcome: ToolError is raised with ERR_009
        """
        from fastmcp.exceptions import ToolError
        from src.agent import LLMError

        mock_pipeline.run_design.side_effect = LLMError(
            provider="openai",
            error=ERROR_LLM_PROVIDER,
            provider_message="API rate limit exceeded"
        )

        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)

        with pytest.raises(ToolError) as exc_info:
            await tool.design(
                requirements="System needs high scalability",
                domain="microservices"
            )

        assert ERROR_LLM_PROVIDER in str(exc_info.value)

    def test_is_llm_error_detects_llm_errors(self, mock_agent, mock_pipeline):
        """
        E-9: Error detection helper method
        
        given_precondition: LLMError instance
        when_action: _is_llm_error() is called
        then_outcome: Returns True for LLMError instances
        """
        from src.agent import LLMError

        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)
        error = LLMError(provider="openai", error="ERR_009", provider_message="test")

        assert tool._is_llm_error(error) is True

    def test_is_llm_error_rejects_non_llm_errors(self, mock_agent, mock_pipeline):
        """
        E-9: Error detection helper method
        
        given_precondition: Non-LLM error instance
        when_action: _is_llm_error() is called
        then_outcome: Returns False for non-LLMError instances
        """
        tool = DesignAgentSystemTool(agent=mock_agent, pipeline=mock_pipeline)
        error = ValueError("Invalid input")

        assert tool._is_llm_error(error) is False



