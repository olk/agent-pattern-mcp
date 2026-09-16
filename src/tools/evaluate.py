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
EvaluateAgentSystemTool - MCP tool for evaluating agent system designs against criteria.

FR-223: The system SHALL provide an EvaluateAgentSystemTool class
API-4: /tools/evaluate_agent_system endpoint (POST) for evaluating agent system designs
CF-4: evaluate_agent_system function with agent_system, criteria, and domain parameters
DF-4: Evaluate with pattern benchmarking flow

Error Handling:
- E-4: ERR_004 - Agent system design does not meet minimum requirements (HTTP 400, severity: warn)
- E-9: ERR_009 - LLM provider returned error (HTTP 502, severity: error)
- E-12: ERR_012 - Malformed agent system overview at I/O boundary (HTTP 400, severity: warn)

Implementation Notes:
- Uses FastMCP @tool decorator for MCP protocol
- Pydantic v2 for input validation
- Delegates to AgentPatternPipeline for evaluation with pattern benchmarking
- Factory Pattern (DP-4) for consistent tool initialization

Architecture:
- ADR-1: Python 3.12+ with FastMCP for MCP Protocol Implementation
- ADR-3: MCP Tool-Based API with Four Core Tools
- DP-7: Adapter Pattern for protocol interface adaptation
"""

import asyncio
import contextlib
import logging
from typing import Annotated, Any

from pydantic import BaseModel, Field

from fastmcp import Context
from src.schemas.design import AgentSystemDesign
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from mcp.types import ToolAnnotations

from src.agent import ERROR_LLM_PROVIDER, LLMError, AgentSystemArchitect
from src.config import TasksConfig
from src.errors import ERROR_INVALID_AGENT_SYSTEM, ERROR_REQUIREMENTS_VALIDATION, MalformedAgentSystemOverviewError
from src.pipeline import AgentPatternPipeline
from src.schemas.evaluation import AgentSystemEvaluation
from src.text_validation import DomainName, PrintableText, ensure_printable_text

logger = logging.getLogger(__name__)


# Error codes for E-4, E-9, and E-12
ERROR_MIN_REQUIREMENTS = "ERR_004"


class EvaluateAgentSystemOutput(BaseModel):
    """
    Output schema for EvaluateAgentSystemTool.

    ENT-13: AgentSystemEvaluation with summary, metrics, recommendations

    Attributes:
        summary: Evaluation summary text
        metrics: Quality metrics dictionary (e.g., reliability, cost_efficiency, latency, output_quality, observability, safety, simplicity)
        recommendations: List of agent system recommendations
    """

    # ENT-13: AgentSystemEvaluation summary attribute
    summary: str = Field(
        default="",
        description="Evaluation summary text"
    )

    # ENT-13: AgentSystemEvaluation metrics attribute
    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Quality metrics (reliability, cost_efficiency, latency, output_quality, observability, safety, simplicity)"
    )

    # ENT-13: AgentSystemEvaluation recommendations attribute
    recommendations: list[str] = Field(
        default_factory=list,
        description="Agent system recommendations"
    )


class EvaluateAgentSystemTool:
    """
    MCP tool for evaluating agent system designs against specified criteria and domain.

    FR-223: The system SHALL provide an EvaluateAgentSystemTool class
    AC-223: Verify EvaluateAgentSystemTool class exists, accepts AgentSystemArchitect

    This tool evaluates agent system designs using AgentSystemArchitect for LLM-based
    evaluation and delegates to AgentPatternPipeline for pattern benchmarking.

    Attributes:
        _agent: AgentSystemArchitect instance for LLM interactions
        _pipeline: AgentPatternPipeline instance for orchestrating evaluation
        _tasks_config: TasksConfig for heartbeat settings

    Error Handling:
        E-4 (ERR_004): Agent system design does not meet minimum requirements - logged with design context
        E-9 (ERR_009): LLM provider returned error - logged with provider context

    DP-4: Factory Pattern - Tool creation with consistent initialization
    DP-7: Adapter Pattern - Adapts FastMCP protocol to internal implementation
    """

    def __init__(
        self,
        agent: AgentSystemArchitect,
        pipeline: AgentPatternPipeline,
        tasks_config: TasksConfig | None = None,
    ) -> None:
        """
        Initialize EvaluateAgentSystemTool.

        AC-223: Verify EvaluateAgentSystemTool class exists, accepts AgentSystemArchitect

        Args:
            agent: AgentSystemArchitect instance for LLM interactions
            pipeline: AgentPatternPipeline instance for orchestrating evaluation
            tasks_config: Heartbeat configuration for long-running tool defence
        """
        self._agent = agent
        self._pipeline = pipeline
        self._tasks_config = tasks_config

        logger.debug(
            "EvaluateAgentSystemTool initialized",
            extra={
                "agent_type": type(agent).__name__,
                "pipeline_type": type(pipeline).__name__
            }
        )

    @tool(
        name="evaluate_agent_system",
        description="Evaluate an agent system design against specified criteria and domain using pattern benchmarking.",
        tags={"agent", "evaluation"},
        annotations=ToolAnnotations(
            title="Evaluate Agent System",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )
    async def evaluate(  # noqa: PLR0912
        self,
        agent_system: Annotated[dict[str, Any], Field(description="Agent system design as dictionary")],
        criteria: Annotated[PrintableText, Field(description="Evaluation criteria description (1-100000 chars, must contain visible text)")],
        domain: Annotated[DomainName, Field(description="Target agent domain (1-200 chars, must contain visible text)")],
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate an agent system design against specified criteria and domain.

        FR-223: EvaluateAgentSystemTool class evaluates agent system designs
        CF-4: evaluate_agent_system function with agent_system, criteria, domain
        API-4: /tools/evaluate_agent_system endpoint

        DF-4: Flow - MCP Client -> MCPAgentPatternServer -> EvaluateAgentSystemTool.evaluate()
              -> AgentPatternPipeline.evaluate() -> pattern benchmarking

        This method:
        1. Converts the agent_system dict to AgentSystemDesign
        2. Checks minimum requirements (E-4)
        3. Delegates to AgentPatternPipeline.evaluate() for pattern benchmarking
        4. Maps AgentSystemEvaluation to output dict
        5. Handles E-4 and E-9 errors appropriately

        Args:
            agent_system: Agent system design as dictionary
            criteria: Evaluation criteria description
            domain: Target agent domain
            ctx: FastMCP context for logging and progress reporting

        Returns:
            dict with evaluation results

        Error Responses:
            E-4: Agent system design does not meet minimum requirements (raised as ToolError)
            E-9: LLM provider returned error (raised as ToolError)
        """
        if ctx is not None:
            await ctx.info(
                f"evaluate_agent_system: domain={domain}, criteria_len={len(criteria)}, "
                f"design_keys={list(agent_system.keys()) if agent_system else []}"
            )

        try:
            criteria = ensure_printable_text(criteria, field="criteria")
        except ValueError as e:
            raise ToolError(f"{ERROR_REQUIREMENTS_VALIDATION}: {e}") from e

        try:
            domain = ensure_printable_text(domain, field="domain", allow_line_breaks=False)
        except ValueError as e:
            raise ToolError(f"{ERROR_REQUIREMENTS_VALIDATION}: {e}") from e

        try:
            agent_system_design = self._convert_to_agent_system_design(agent_system)

            if not self._check_minimum_requirements(agent_system_design):
                if ctx is not None:
                    await ctx.error("Agent system design does not meet minimum requirements")
                raise ToolError(
                    f"{ERROR_MIN_REQUIREMENTS}: Agent system design does not meet minimum requirements"
                )

            hb = self._start_heartbeat(ctx, "evaluate_agent_system")
            try:
                evaluation = await self._pipeline.evaluate(
                    design=agent_system_design,
                    criteria=criteria,
                    domain=domain,
                )
            finally:
                if hb is not None:
                    hb.cancel()

            output = self._map_to_output(evaluation)

            if ctx is not None:
                await ctx.info(
                    f"evaluate_agent_system completed: summary_len={len(output.summary)}, "
                    f"metrics={len(output.metrics)}"
                )

            return output.model_dump()

        except LLMError as e:
            if ctx is not None:
                await ctx.error(f"LLM provider error during evaluation: {e.provider_message}")
            raise ToolError(
                f"{ERROR_LLM_PROVIDER}: LLM provider returned error: {e.provider_message}"
            ) from e

        except ToolError:
            raise

        except MalformedAgentSystemOverviewError as exc:
            if ctx is not None:
                await ctx.error(f"Malformed agent system overview: {exc.locator} failed validation")
            raise ToolError(
                f"{ERROR_INVALID_AGENT_SYSTEM}: {exc.locator} failed validation"
            ) from exc

        except Exception as e:
            error_msg = str(e)
            if ctx is not None:
                await ctx.error(f"Unexpected error during evaluation: {error_msg}")
            raise ToolError(f"{ERROR_LLM_PROVIDER}: Evaluation failed: {error_msg}") from e

    def _start_heartbeat(
        self, ctx: Context | None, label: str
    ) -> asyncio.Task[None] | None:
        """Start a parallel heartbeat that emits progress notifications.

        Keeps client HTTP/stdio idle timers alive during long synchronous calls.
        Silently no-ops when ctx is None, heartbeat is disabled, or ctx.report_progress
        is not supported by the client transport.
        """
        cfg = self._tasks_config
        if ctx is None or cfg is None or not cfg.heartbeat_enabled:
            return None

        async def _hb() -> None:
            step = 0
            try:
                while True:
                    await asyncio.sleep(cfg.heartbeat_interval_seconds)
                    step += 1
                    with contextlib.suppress(Exception):
                        await ctx.report_progress(progress=step, message=f"{label} in progress")
            except asyncio.CancelledError:
                pass

        return asyncio.create_task(_hb())

    def _convert_to_agent_system_design(self, agent_system: dict[str, Any]) -> AgentSystemDesign:
        """
        Convert an agent_system dictionary to AgentSystemDesign instance.

        Args:
            agent_system: Agent system design as dictionary

        Returns:
            AgentSystemDesign instance
        """
        from src.tools._adapters import design_from_dict
        return design_from_dict(agent_system)

    def _check_minimum_requirements(self, agent_system: AgentSystemDesign) -> bool:
        """
        Check if the agent system design meets minimum requirements.

        E-4: ERR_004 - Agent system design does not meet minimum requirements

        Minimum requirements:
        - Must have at least one agent
        - Must have an overview

        Args:
            agent_system: AgentSystemDesign to check

        Returns:
            True if the design meets minimum requirements
        """
        if not agent_system.agents:
            return False

        if not agent_system.overview:
            return False

        return True

    def _map_to_output(self, evaluation: AgentSystemEvaluation) -> EvaluateAgentSystemOutput:
        """
        Map AgentSystemEvaluation from pipeline to EvaluateAgentSystemOutput.

        Args:
            evaluation: AgentSystemEvaluation from AgentPatternPipeline.evaluate()

        Returns:
            EvaluateAgentSystemOutput mapped from evaluation
        """
        metrics_dict = {m.name: m.score / 10.0 for m in evaluation.metrics}
        recommendations_list = []
        for recs in evaluation.recommendations.values():
            recommendations_list.extend(recs)

        return EvaluateAgentSystemOutput(
            summary=f"Overall score: {evaluation.summary.overall_score:.1f}/100",
            metrics=metrics_dict,
            recommendations=recommendations_list
        )


# MCP Tool definition function
# ADR-3: MCP Tool-Based API - FastMCP @tool decorator
def evaluate_agent_system_tool(
    agent: AgentSystemArchitect,
    pipeline: AgentPatternPipeline,
    tasks_config: TasksConfig | None = None,
) -> EvaluateAgentSystemTool:
    """
    Factory function to create EvaluateAgentSystemTool instance.

    DP-4: Factory Pattern - Consistent tool initialization with proper dependencies

    Args:
        agent: AgentSystemArchitect instance for LLM interactions
        pipeline: AgentPatternPipeline instance for orchestrating evaluation
        tasks_config: Heartbeat configuration for long-running tool defence (None = defaults applied)

    Returns:
        EvaluateAgentSystemTool instance ready for MCP tool registration
    """
    return EvaluateAgentSystemTool(agent=agent, pipeline=pipeline, tasks_config=tasks_config)
