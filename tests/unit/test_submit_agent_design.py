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
Unit tests for the async submit_agent_design_job / get_agent_design_status trio.

Covers:
- Parity: stored job result contains all 9 fields that
  design_agent_system returns (including matched_domains,
  is_fallback, and alternative_topologies)
- Job lifecycle: PENDING -> RUNNING -> COMPLETED
- get_agent_design_status returns parsed result with all fields intact
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent import AgentSystemArchitect
from src.pipeline import AgentPatternPipeline, CancellationToken
from src.schemas.contracts import MessageContract
from src.schemas.design import AgentSystemDesign, AgentSystemOverview
from src.schemas.components import Agent, Relationship
from src.schemas.enums import AgentTopology, PatternCategory
from src.schemas.evaluation import (
    AgentSystemEvaluation,
    EvaluationSummary,
    MetricResult,
    PipelineResult,
)
from src.schemas.quality import QualityMetrics
from src.tools.design import DesignAgentSystemOutput, pipeline_result_to_output
from src.tools.get_agent_design_status import GetAgentDesignStatusTool
from src.tools.jobs import JobsStore
from src.tools.submit_agent_design import (
    SubmitAgentDesignJobTool,
    submit_agent_design_job_tool,
)


@pytest.fixture
def mock_agent():
    """Create a mock AgentSystemArchitect."""
    return MagicMock(spec=AgentSystemArchitect)


@pytest.fixture
def mock_pipeline():
    """Create a mock AgentPatternPipeline."""
    pipeline = MagicMock(spec=AgentPatternPipeline)
    pipeline.run_design = AsyncMock()
    return pipeline


@pytest.fixture
def sample_pipeline_result():
    """Create a PipelineResult with matched_domains and is_fallback populated."""
    design = AgentSystemDesign(
        overview=AgentSystemOverview(
            topology=AgentTopology.HIERARCHICAL,
            category=PatternCategory.PLANNING,
            principles=["principle1", "principle2"],
        ),
        agents=[
            Agent(
                id="planner-agent",
                name="Planner Agent",
                role="planner",
                description="Plans task decomposition",
                responsibilities=["decompose goals"],
            ),
        ],
        relationships=[
            Relationship(source="planner-agent", target="executor-agent", type="handoff", description=""),
        ],
        quality_attributes={"reliability": 9.0, "output_quality": 8.0},
        tool_contracts=[],
        shared_state_models=[],
        message_contracts=[
            MessageContract(
                message_name="task.assigned",
                payload_schema={"task_id": "string"},
                published_by="planner-agent",
                consumed_by=[],
                description="",
            ),
        ],
    )

    evaluation = AgentSystemEvaluation(
        summary=EvaluationSummary(
            reasoning="Evaluator reasoning for the assessment",
            overall_score=82.0,
            strengths=["Strong separation of concerns"],
            weaknesses=["Consider adding caching"],
            critical_findings=[],
        ),
        metrics=[
            MetricResult(
                name="reliability",
                score=9.0,
                description="Reliability assessment",
                findings=[],
                recommendations=[],
            ),
        ],
        recommendations={"reliability": ["Add retries"], "safety": ["Add guardrails"]},
    )

    return PipelineResult(
        design=design,
        evaluation=evaluation,
        attempts=1,
        final_topology="hierarchical",
        quality_metrics=QualityMetrics(
            reliability=9.0,
            cost_efficiency=8.0,
            latency=8.5,
            output_quality=8.0,
            observability=7.5,
            safety=8.0,
            simplicity=7.0,
        ),
        final_quality_score=82.0,
        matched_domains=[
            {"slug": "planning", "fusion_score": 0.95, "rerank_score": 0.9},
            {"slug": "multi-agent", "fusion_score": 0.72, "rerank_score": 0.7},
        ],
        is_fallback=False,
    )


@pytest.fixture
def sample_pipeline_result_fallback():
    """PipelineResult with is_fallback=True and empty matched_domains."""
    design = AgentSystemDesign(
        overview=AgentSystemOverview(
            topology=AgentTopology.SINGLE_AGENT_LOOP,
            category=PatternCategory.REASONING,
            principles=["principle1"],
        ),
        agents=[
            Agent(
                id="core-agent",
                name="Core Agent",
                role="executor",
                description="Single agent core loop",
                responsibilities=["task execution"],
            ),
        ],
        relationships=[],
        quality_attributes={},
        tool_contracts=[],
        shared_state_models=[],
        message_contracts=[],
    )

    evaluation = AgentSystemEvaluation(
        summary=EvaluationSummary(
            reasoning="Evaluator reasoning for the assessment",
            overall_score=60.0,
            strengths=[],
            weaknesses=["Fallback pattern — limited domain match"],
            critical_findings=["Used single-agent-loop fallback"],
        ),
        metrics=[
            MetricResult(
                name="overall_quality",
                score=60.0,
                description="",
                findings=[],
                recommendations=[],
            ),
        ],
        recommendations={},
    )

    return PipelineResult(
        design=design,
        evaluation=evaluation,
        attempts=3,
        final_topology="single-agent-loop",
        final_quality_score=60.0,
        matched_domains=[],
        is_fallback=True,
    )


class TestSubmitAgentDesignJobTool:
    """Test suite for SubmitAgentDesignJobTool."""

    def test_factory_function(self, mock_agent, mock_pipeline):
        """DP-4: Factory function creates a properly initialised tool."""
        tool = submit_agent_design_job_tool(
            agent=mock_agent, pipeline=mock_pipeline
        )
        assert tool is not None
        assert isinstance(tool, SubmitAgentDesignJobTool)
        assert tool._agent is mock_agent
        assert tool._pipeline is mock_pipeline

    @pytest.mark.asyncio
    async def test_submit_job_returns_job_id_and_pending_job(
        self, mock_agent, mock_pipeline, jobs_store: JobsStore
    ):
        """submit_job returns immediately with a job_id and stores a PENDING job."""
        tool = SubmitAgentDesignJobTool(agent=mock_agent, pipeline=mock_pipeline)
        result = await tool.submit_job(
            requirements="Build a research assistant that gathers and summarises sources",
            domain="research_reports",
        )

        assert "job_id" in result
        assert result["status"] == "pending"
        job = await jobs_store.get_job(result["job_id"])
        assert job is not None
        assert job["status"] == "pending"
        assert job["requirements"] == "Build a research assistant that gathers and summarises sources"
        assert job["domain"] == "research_reports"
        assert job["override_topology"] is None


class TestPipelineResultToOutputParity:
    """Verify pipeline_result_to_output produces identical fields to DesignAgentSystemOutput."""

    def test_all_nine_fields_present(self, sample_pipeline_result):
        """
        pipeline_result_to_output must include all 9 DesignAgentSystemOutput fields.

        Parity: design_agent_system and the async job path must return
        the same field set.
        """
        output = pipeline_result_to_output(sample_pipeline_result)
        dump = output.model_dump()

        expected_keys = {
            "design",
            "evaluation",
            "attempts",
            "final_topology",
            "final_pattern_name",
            "quality_metrics",
            "final_quality_score",
            "matched_domains",
            "is_fallback",
            "alternative_topologies",
        }
        assert set(dump.keys()) == expected_keys

    def test_matched_domains_values(self, sample_pipeline_result):
        """matched_domains must serialize with slug and fusion_score."""
        output = pipeline_result_to_output(sample_pipeline_result)
        dump = output.model_dump()

        assert len(dump["matched_domains"]) == 2
        assert dump["matched_domains"][0]["slug"] == "planning"
        assert dump["matched_domains"][0]["fusion_score"] == 0.95
        assert dump["matched_domains"][1]["slug"] == "multi-agent"
        assert dump["matched_domains"][1]["fusion_score"] == 0.72

    def test_is_fallback_false(self, sample_pipeline_result):
        """is_fallback=False when domain matched."""
        output = pipeline_result_to_output(sample_pipeline_result)
        assert output.is_fallback is False
        assert output.model_dump()["is_fallback"] is False

    def test_is_fallback_true(self, sample_pipeline_result_fallback):
        """is_fallback=True and matched_domains=[] when using fallback pattern."""
        output = pipeline_result_to_output(sample_pipeline_result_fallback)
        dump = output.model_dump()
        assert dump["is_fallback"] is True
        assert dump["matched_domains"] == []

    def test_parity_with_design_agent_system_output_keys(
        self, sample_pipeline_result
    ):
        """
        Keys of pipeline_result_to_output dump must exactly match
        keys of DesignAgentSystemOutput(...).model_dump().

        This is the canonical parity assertion: both code paths produce
        structurally identical output.
        """
        expected_keys = set(DesignAgentSystemOutput().model_dump().keys())
        actual_keys = set(pipeline_result_to_output(sample_pipeline_result).model_dump().keys())
        assert actual_keys == expected_keys


class TestRunJobStoresAllFields:
    """Test that _run_job stores a result with all 9 fields including matched_domains and is_fallback."""

    @pytest.mark.asyncio
    async def test_run_job_stores_matched_domains_and_is_fallback(
        self,
        mock_agent,
        mock_pipeline,
        sample_pipeline_result,
        jobs_store: JobsStore,
    ):
        """
        After _run_job completes, the stored result JSON must contain
        matched_domains and is_fallback fields (parity fix).
        """
        mock_pipeline.run_design.return_value = sample_pipeline_result
        tool = SubmitAgentDesignJobTool(agent=mock_agent, pipeline=mock_pipeline)

        job_id = await jobs_store.create_job(
            requirements="Build a research assistant that gathers and summarises sources",
            domain="research_reports",
        )

        await tool._run_job(
            job_id=job_id,
            requirements="Build a research assistant that gathers and summarises sources",
            domain="research_reports",
            override_topology=None,
            ctx=None,
            cancellation=CancellationToken(),
        )

        job = await jobs_store.get_job(job_id)
        assert job["status"] == "completed"

        stored_result = json.loads(job["result"])
        assert "matched_domains" in stored_result
        assert stored_result["matched_domains"][0]["slug"] == "planning"
        assert stored_result["matched_domains"][0]["fusion_score"] == 0.95
        assert "is_fallback" in stored_result
        assert stored_result["is_fallback"] is False

    @pytest.mark.asyncio
    async def test_run_job_stores_fallback_fields(
        self,
        mock_agent,
        mock_pipeline,
        sample_pipeline_result_fallback,
        jobs_store: JobsStore,
    ):
        """Fallback case: is_fallback=True and matched_domains=[] must be stored."""
        mock_pipeline.run_design.return_value = sample_pipeline_result_fallback
        tool = SubmitAgentDesignJobTool(agent=mock_agent, pipeline=mock_pipeline)

        job_id = await jobs_store.create_job(
            requirements="Build a system",
            domain="unknown-domain-xyz",
        )

        await tool._run_job(
            job_id=job_id,
            requirements="Build a system",
            domain="unknown-domain-xyz",
            override_topology=None,
            ctx=None,
            cancellation=CancellationToken(),
        )

        job = await jobs_store.get_job(job_id)
        stored_result = json.loads(job["result"])
        assert stored_result["is_fallback"] is True
        assert stored_result["matched_domains"] == []


class TestGetAgentDesignStatusReturnsAllFields:
    """Test that get_agent_design_status surfaces all 9 fields when completed."""

    @pytest.mark.asyncio
    async def test_get_status_returns_matched_domains_and_is_fallback(
        self,
        mock_agent,
        mock_pipeline,
        sample_pipeline_result,
        jobs_store: JobsStore,
    ):
        """
        get_agent_design_status must return the full 9-field result
        (including matched_domains and is_fallback) when status is completed.
        """
        mock_pipeline.run_design.return_value = sample_pipeline_result
        tool = SubmitAgentDesignJobTool(agent=mock_agent, pipeline=mock_pipeline)

        job_id = await jobs_store.create_job(
            requirements="Build a research assistant that gathers and summarises sources",
            domain="research_reports",
        )
        await tool._run_job(
            job_id=job_id,
            requirements="Build a research assistant that gathers and summarises sources",
            domain="research_reports",
            override_topology=None,
            ctx=None,
            cancellation=CancellationToken(),
        )

        status_tool = GetAgentDesignStatusTool()
        status = await status_tool.get_status(job_id=job_id)

        assert status["status"] == "completed"
        assert "result" in status

        result = status["result"]
        assert "matched_domains" in result
        assert result["matched_domains"][0]["slug"] == "planning"
        assert result["matched_domains"][0]["fusion_score"] == 0.95
        assert "is_fallback" in result
        assert result["is_fallback"] is False

    @pytest.mark.asyncio
    async def test_get_status_returns_error_on_failure(
        self,
        mock_agent,
        mock_pipeline,
        jobs_store: JobsStore,
    ):
        """Failed jobs must return the error string instead of raising."""
        mock_pipeline.run_design.side_effect = RuntimeError("LLM provider unreachable")
        tool = SubmitAgentDesignJobTool(agent=mock_agent, pipeline=mock_pipeline)

        job_id = await jobs_store.create_job(
            requirements="Build a system",
            domain="research_reports",
        )
        await tool._run_job(
            job_id=job_id,
            requirements="Build a system",
            domain="research_reports",
            override_topology=None,
            ctx=None,
            cancellation=CancellationToken(),
        )

        status_tool = GetAgentDesignStatusTool()
        status = await status_tool.get_status(job_id=job_id)

        assert status["status"] == "failed"
        assert "error" in status
        assert "LLM provider" in status["error"]


class TestOverrideTopologyValidation:
    """Strict enum validation of override_topology at the submit boundary."""

    @pytest.mark.asyncio
    async def test_submit_rejects_invalid_override_topology(
        self, mock_agent, mock_pipeline, jobs_store: JobsStore
    ):
        """override_topology outside the AgentTopology enum fails with ERR_001."""
        from fastmcp.exceptions import ToolError

        tool = SubmitAgentDesignJobTool(agent=mock_agent, pipeline=mock_pipeline)
        with pytest.raises(ToolError) as exc_info:
            await tool.submit_job(
                requirements="Build a research assistant",
                domain="research_reports",
                override_topology="event-driven",
            )
        assert "ERR_001" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_accepts_canonical_override_topology(
        self, mock_agent, mock_pipeline, jobs_store: JobsStore
    ):
        """A canonical AgentTopology value is stored on the job unchanged."""
        tool = SubmitAgentDesignJobTool(agent=mock_agent, pipeline=mock_pipeline)
        result = await tool.submit_job(
            requirements="Build a research assistant",
            domain="research_reports",
            override_topology="hierarchical",
        )
        job = await jobs_store.get_job(result["job_id"])
        assert job is not None
        assert job["override_topology"] == "hierarchical"
