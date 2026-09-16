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
DesignAgentSystemTool - High-level wrapper tool delegating to full agent system pipeline.

FR-224: The system SHALL provide a DesignAgentSystemTool class
API-1: /tools/design_agent_system endpoint (POST)
CF-1: design_agent_system function with requirements, domain, optional override_topology
DF-1: Full pipeline execute flow

Error Handling:
- E-1: ERR_001 - Requirements validation fails (HTTP 400, severity: warn)
- E-9: ERR_009 - LLM provider returned error (HTTP 502, severity: error)
- E-12: ERR_012 - Malformed agent system overview at I/O boundary (HTTP 400, severity: warn)

Implementation Notes:
- Uses FastMCP @tool decorator for MCP protocol
- Pydantic v2 for input validation
- Delegates to AgentPatternPipeline.run() for complete design generation
- Factory Pattern (DP-4) for consistent tool initialization
- Adapter Pattern (DP-7) for protocol interface adaptation

Architecture:
- ADR-1: Python 3.12+ with FastMCP for MCP Protocol Implementation
- ADR-3: MCP Tool-Based API with Four Core Tools
- DP-1: Pipeline Pattern - delegate to AgentPatternPipeline.run()
- DP-4: Factory Pattern - tool creation with consistent initialization
- DP-5: Dependency Injection - receive dependencies via constructor
- DP-7: Adapter Pattern - adapts FastMCP protocol to internal implementation
"""

import asyncio
import contextlib
import logging
from typing import Annotated, Any

from pydantic import BaseModel, Field

from fastmcp import Context
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from mcp.types import ToolAnnotations

from src.agent import ERROR_LLM_PROVIDER, LLMError, AgentSystemArchitect
from src.config import TasksConfig
from src.errors import ERROR_INVALID_AGENT_SYSTEM, MalformedAgentSystemOverviewError
from src.pipeline import AgentPatternPipeline
from src.schemas.evaluation import PipelineResult
from src.text_validation import DomainName, PrintableText, ensure_printable_text
from src.schemas.enums import validate_topology_value

logger = logging.getLogger(__name__)


# Error codes for E-1, E-9, and E-12
# E-1: ERR_001 - Requirements validation fails (HTTP 400, severity: warn)
# E-9: ERR_009 - LLM provider returned error (HTTP 502, severity: error)
ERROR_REQUIREMENTS_VALIDATION = "ERR_001"


class DesignAgentSystemOutput(BaseModel):
    """
    Output schema for DesignAgentSystemTool.

    FR-224: Returns PipelineResult combining AgentSystemDesign and AgentSystemEvaluation
    ENT-12: AgentSystemDesign with overview, agents, relationships, etc.
    ENT-13: AgentSystemEvaluation with summary, metrics, recommendations

    Attributes:
        design: Complete agent system design
        evaluation: Full agent system evaluation with metrics, risks, and recommendations
        attempts: Total generate attempts made (initial + retries)
        final_topology: Final agent topology
        quality_metrics: Aggregated quality metrics from analysis
        final_quality_score: Final quality score after best attempt
    """

    design: dict[str, Any] = Field(
        default_factory=dict,
        description="Complete agent system design"
    )

    evaluation: dict[str, Any] = Field(
        default_factory=dict,
        description="Full agent system evaluation with metrics, risks, and recommendations"
    )

    attempts: int = Field(
        default=1,
        ge=1,
        description="Total generate attempts made (initial + retries)"
    )

    final_topology: str = Field(
        default="",
        description="Final agent topology (an AgentTopology value)"
    )

    final_pattern_name: str = Field(
        default="",
        description="Name of the top-scored pattern matching final_topology ('' when the topology was overridden or no patterns were scored)"
    )

    quality_metrics: dict[str, Any] | None = Field(
        default=None,
        description="Aggregated quality metrics from analysis"
    )

    final_quality_score: float = Field(
        default=0.0,
        description="Final quality score after best attempt"
    )
    matched_domains: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Top matched domain slugs from retrieval recall"
    )
    is_fallback: bool = Field(
        default=False,
        description="True when retrieval produced no real candidates and used fallback"
    )
    alternative_topologies: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Runner-up topologies the analyzer scored but did not select"
    )


class DesignAgentSystemTool:
    """
    High-level wrapper tool that delegates to the full agent system pipeline.

    FR-224: The system SHALL provide a DesignAgentSystemTool class
    AC-224: Verify DesignAgentSystemTool class exists and delegates to pipeline.run

    This tool provides a simplified interface for complete agent system design generation.
    It accepts requirements and domain, optionally allowing topology override, and returns
    a complete agent system design with evaluation.

    Attributes:
        _agent: AgentSystemArchitect instance for LLM interactions
        _pipeline: AgentPatternPipeline instance for orchestrating the design pipeline
        _tasks_config: TasksConfig for heartbeat settings

    Error Handling:
        E-1 (ERR_001): Requirements validation fails - logged with requirements context
        E-9 (ERR_009): LLM provider returned error - logged with provider context

    # DP-4: Factory Pattern - Tool creation with consistent initialization
    # DP-5: Dependency Injection - Constructor injection of dependencies
    # DP-7: Adapter Pattern - Adapts FastMCP protocol to internal implementation
    """

    def __init__(
        self,
        agent: AgentSystemArchitect,
        pipeline: AgentPatternPipeline,
        tasks_config: TasksConfig | None = None,
    ) -> None:
        """
        Initialize DesignAgentSystemTool.

        DP-5: Dependency Injection - Constructor injection of all dependencies

        AC-224: Verify DesignAgentSystemTool class exists, accepts AgentSystemArchitect

        Args:
            agent: AgentSystemArchitect instance for LLM interactions
            pipeline: AgentPatternPipeline instance for orchestrating design pipeline
            tasks_config: Heartbeat configuration for long-running tool defence
        """
        self._agent = agent
        self._pipeline = pipeline
        self._tasks_config = tasks_config

        logger.debug(
            "DesignAgentSystemTool initialized",
            extra={
                "agent_type": type(agent).__name__,
                "pipeline_type": type(pipeline).__name__
            }
        )

    @tool(
        name="design_agent_system",
        description=(
            "Default tool for creating an agent system design. Runs the full pipeline "
            "(analyze → generate → evaluate → refine, up to 3 attempts) and returns the complete design, "
            "evaluation, and quality scores in a single response. Takes 5-10 minutes; emits progress "
            "notifications every 30 s so clients stay connected. Use this whenever the user wants an "
            "agent system design, including when they explicitly request design_agent_system. "
            "Do NOT use submit_agent_design_job for ordinary design requests — that tool is only for clients "
            "with short request timeouts (Cursor, Claude Desktop) and returns only a job_id."
        ),
        tags={"agent", "design"},
        annotations=ToolAnnotations(
            title="Design Agent System (default)",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )
    async def design(  # noqa: PLR0912

        self,
        requirements: Annotated[PrintableText, Field(description="Agent system requirements description (1-100000 chars, must contain visible text)")],
        domain: Annotated[DomainName, Field(description="Target agent domain (1-200 chars, must contain visible text)")],
        override_topology: Annotated[PrintableText | None, Field(description="Override the derived agent topology")] = None,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """
        Generate complete agent system design with evaluation.

        FR-224: DesignAgentSystemTool class delegates to pipeline.run
        CF-1: design_agent_system function with requirements, domain, optional override_topology
        API-1: /tools/design_agent_system endpoint

        DF-1: Flow - MCP Client -> MCPAgentPatternServer -> DesignAgentSystemTool.design()
              -> AgentPatternPipeline.run() -> RefinedAgentSystemDesign

        This method:
        1. Validates inputs (E-1)
        2. Delegates to AgentPatternPipeline.run_design()
        3. Maps RefinedAgentSystemDesign to output dict
        4. Handles E-9 errors appropriately

        Args:
            requirements: Agent system requirements description
            domain: Target agent domain
            override_topology: Optional agent topology override
            ctx: FastMCP context for logging and progress reporting

        Returns:
            dict with complete design and evaluation

        Error Responses:
            E-1: Requirements validation fails (raised as ToolError)
            E-9: LLM provider returned error (raised as ToolError)
        """
        if ctx is not None:
            await ctx.info(f"design_agent_system: domain={domain}, req_len={len(requirements)}, override_topology={override_topology}")

        try:
            requirements = ensure_printable_text(requirements, field="requirements")
        except ValueError as e:
            raise ToolError(f"{ERROR_REQUIREMENTS_VALIDATION}: {e}") from e

        try:
            domain = ensure_printable_text(domain, field="domain", allow_line_breaks=False)
        except ValueError as e:
            raise ToolError(f"{ERROR_REQUIREMENTS_VALIDATION}: {e}") from e

        try:
            if override_topology is not None:
                override_topology = ensure_printable_text(override_topology, field="override_topology")
                try:
                    override_topology = validate_topology_value(override_topology)
                except ValueError as e:
                    raise ToolError(f"{ERROR_REQUIREMENTS_VALIDATION}: {e}") from e

            hb = self._start_heartbeat(ctx, "design_agent_system")
            try:
                refined = await self._pipeline.run_design(
                    requirements=requirements,
                    domain=domain,
                    topology=override_topology
                )
            finally:
                if hb is not None:
                    hb.cancel()

            output = self._map_to_output(refined)

            if ctx is not None:
                await ctx.info(
                    f"design_agent_system completed: attempts={output.attempts}, "
                    f"score={output.final_quality_score}, agents={len(output.design.get('agents', []))}"
                )

            return output.model_dump()

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

            if self._is_llm_error(e):
                if ctx is not None:
                    await ctx.error(f"LLM provider error during design: {error_msg}")
                raise ToolError(f"{ERROR_LLM_PROVIDER}: LLM provider returned error: {error_msg}") from e

            if ctx is not None:
                await ctx.error(f"Unexpected error during design: {error_msg}")
            raise

    def _start_heartbeat(
        self, ctx: Context | None, label: str
    ) -> asyncio.Task[None] | None:
        """Start a parallel heartbeat that emits progress notifications.

        Keeps client HTTP/stdio idle timers alive during long synchronous calls.
        Cancelled automatically via task.cancel() in the outer finally block.
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
                        await ctx.report_progress(
                            progress=step,
                            message=f"{label} in progress",
                        )
            except asyncio.CancelledError:
                pass

        return asyncio.create_task(_hb())

    def _map_to_output(self, refined: PipelineResult) -> DesignAgentSystemOutput:
        """Delegate to the module-level function for shared serialization."""
        return pipeline_result_to_output(refined)

    def _is_llm_error(self, error: Exception) -> bool:
        """
        Check if error is an LLM provider error.

        E-9: ERR_009 - LLM provider returned error

        Args:
            error: Exception to check

        Returns:
            True if error is LLM-related
        """
        return isinstance(error, LLMError)


def pipeline_result_to_output(refined: PipelineResult) -> DesignAgentSystemOutput:
    """
    Map PipelineResult from pipeline to DesignAgentSystemOutput.

    Single source of truth for the design_agent_system output schema.
    Used by both the blocking DesignAgentSystemTool and the async
    submit_agent_design_job background task.

    Args:
        refined: PipelineResult from AgentPatternPipeline.run_design()

    Returns:
        DesignAgentSystemOutput mapped from refined design
    """
    from src.tools._adapters import design_to_pydantic
    pd_design = design_to_pydantic(refined.design)
    design_dict = pd_design.model_dump()
    eval_dict = refined.evaluation.model_dump() if hasattr(refined.evaluation, "model_dump") else dict(refined.evaluation)
    qm_dict = refined.quality_metrics.model_dump() if refined.quality_metrics else None
    return DesignAgentSystemOutput(
        design=design_dict,
        evaluation=eval_dict,
        attempts=refined.attempts,
        final_topology=refined.final_topology,
        final_pattern_name=refined.final_pattern_name,
        quality_metrics=qm_dict,
        final_quality_score=refined.final_quality_score,
        matched_domains=[m.model_dump() for m in refined.matched_domains],
        is_fallback=refined.is_fallback,
        alternative_topologies=[c.model_dump() for c in refined.alternative_topologies],
    )


# MCP Tool definition function
# ADR-3: MCP Tool-Based API - FastMCP @tool decorator
def design_agent_system_tool(
    agent: AgentSystemArchitect,
    pipeline: AgentPatternPipeline,
    tasks_config: TasksConfig | None = None,
) -> DesignAgentSystemTool:
    """
    Factory function to create DesignAgentSystemTool instance.

    DP-4: Factory Pattern - Consistent tool initialization with proper dependencies

    Args:
        agent: AgentSystemArchitect instance for LLM interactions
        pipeline: AgentPatternPipeline instance for orchestrating design pipeline
        tasks_config: TasksConfig for heartbeat settings (None = defaults applied)

    Returns:
        DesignAgentSystemTool instance ready for MCP tool registration
    """
    return DesignAgentSystemTool(agent=agent, pipeline=pipeline, tasks_config=tasks_config)
