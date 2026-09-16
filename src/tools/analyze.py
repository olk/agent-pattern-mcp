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
AnalyzeAgentSystemTool - MCP tool for analyzing requirements and deriving agent system recommendations.

FR-221: The system SHALL provide an AnalyzeAgentSystemTool class
API-2: /tools/analyze_agent_system endpoint (POST) for analyzing requirements
CF-2: analyze_agent_system function with requirements and domain parameters
DF-2: Analyze with PatternLoader filtering flow

Error Handling:
- E-2: ERR_002 - No patterns found for domain (HTTP 404, severity: info)
- E-9: ERR_009 - LLM provider returned error (HTTP 502, severity: error)

Implementation Notes:
- Uses FastMCP @tool decorator for MCP protocol
- Pydantic v2 for input validation
- Delegates to AgentPatternPipeline for pattern selection and LLM analysis
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
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from mcp.types import ToolAnnotations

from src.agent import ERROR_LLM_PROVIDER, AgentSystemArchitect
from src.config import TasksConfig
from src.errors import ERROR_REQUIREMENTS_VALIDATION
from src.patterns.retriever import DEFAULT_FALLBACK_PATTERN_NAME, DEFAULT_FALLBACK_TOPOLOGY
from src.pipeline import AnalysisResult, AgentPatternPipeline
from src.text_validation import DomainName, PrintableText, ensure_printable_text

logger = logging.getLogger(__name__)


class AnalyzeAgentSystemOutput(BaseModel):
    """
    Output schema for AnalyzeAgentSystemTool.

    ENT-4: AnalysisResult with strengths, weaknesses, recommendations,
           quality_metrics, recommended_topology, selected_patterns,
           matched_domains, is_fallback

    Attributes:
        strengths: List of identified agent system strengths
        weaknesses: List of identified agent system weaknesses
        recommendations: List of agent system recommendations
        recommended_topology: Recommended agent topology
        selected_patterns: List of selected agent patterns
        quality_metrics: Quality assessment metrics
        matched_domains: Top matched AgentDomain slugs with fusion scores
        is_fallback: True when the fallback pattern was used
    """

    strengths: list[str] = Field(
        default_factory=list,
        description="Identified agent system strengths"
    )

    weaknesses: list[str] = Field(
        default_factory=list,
        description="Identified agent system weaknesses"
    )

    recommendations: list[str] = Field(
        default_factory=list,
        description="Agent system recommendations"
    )

    recommended_topology: str = Field(
        default="",
        description="Recommended agent topology (an AgentTopology value)"
    )

    recommended_pattern_name: str = Field(
        default="",
        description="Name of the top-scored pattern that drove the topology recommendation ('' when no patterns were scored)"
    )

    selected_patterns: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Selected agent patterns"
    )

    quality_metrics: dict[str, Any] | None = Field(
        default=None,
        description="Quality assessment metrics"
    )
    matched_domains: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Top matched AgentDomain slugs from BM25+FAISS retrieval with fusion scores"
    )
    is_fallback: bool = Field(
        default=False,
        description="True when no real domain match was found and the fallback 'react' pattern was used"
    )


class AnalyzeAgentSystemTool:
    """
    MCP tool for analyzing requirements and deriving agent system recommendations.

    FR-221: The system SHALL provide an AnalyzeAgentSystemTool class
    AC-221: Verify AnalyzeAgentSystemTool class exists, accepts AgentSystemArchitect

    This tool analyzes requirements and derives agent system recommendations with
    pattern filtering. It uses AgentSystemArchitect for LLM interactions and
    delegates to AgentPatternPipeline for pattern selection.

    Attributes:
        _agent: AgentSystemArchitect instance for LLM interactions
        _pipeline: AgentPatternPipeline instance for orchestrating analysis
        _tasks_config: TasksConfig for heartbeat settings

    Error Handling:
        E-2 (ERR_002): No patterns found for domain - logged with domain context
        E-9 (ERR_009): LLM provider returned error - logged with provider context

    # DP-4: Factory Pattern - Tool creation with consistent initialization
    # DP-7: Adapter Pattern - Adapts FastMCP protocol to internal implementation
    """

    def __init__(
        self,
        agent: AgentSystemArchitect,
        pipeline: AgentPatternPipeline,
        tasks_config: TasksConfig | None = None,
    ) -> None:
        """
        Initialize AnalyzeAgentSystemTool.

        AC-221: Verify AnalyzeAgentSystemTool class exists, accepts AgentSystemArchitect

        Args:
            agent: AgentSystemArchitect instance for LLM interactions
            pipeline: AgentPatternPipeline instance for orchestrating analysis
            tasks_config: Heartbeat configuration for long-running tool defence
        """
        self._agent = agent
        self._pipeline = pipeline
        self._tasks_config = tasks_config

        logger.debug(
            "AnalyzeAgentSystemTool initialized",
            extra={
                "agent_type": type(agent).__name__,
                "pipeline_type": type(pipeline).__name__
            }
        )

    @tool(
        name="analyze_agent_system",
        description="Analyze requirements and derive agent system recommendations using pattern matching and domain similarity.",
        tags={"agent", "analysis"},
        annotations=ToolAnnotations(
            title="Analyze Agent System",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )
    async def analyze(
        self,
        requirements: Annotated[PrintableText, Field(description="Agent system requirements description (1-100000 chars, must contain visible text)")],
        domain: Annotated[DomainName, Field(description="Target agent domain (1-200 chars, must contain visible text)")],
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """
        Analyze requirements and derive agent system recommendations.

        FR-221: AnalyzeAgentSystemTool class analyzes requirements
        CF-2: analyze_agent_system function with requirements and domain
        API-2: /tools/analyze_agent_system endpoint

        DF-2: Flow - MCP Client -> MCPAgentPatternServer -> AnalyzeAgentSystemTool.analyze()
              -> AgentPatternPipeline.analyze() -> PatternLoader.filter_by_domain()

        This method:
        1. Validates inputs
        2. Delegates to AgentPatternPipeline.analyze()
        3. Maps AnalysisResult to output dict
        4. Handles E-2 and E-9 errors appropriately

        Args:
            requirements: Agent system requirements description
            domain: Target agent domain
            ctx: FastMCP context for logging and progress reporting

        Returns:
            dict with analysis results

        Error Responses:
            E-2: No patterns found for domain (returns empty result)
            E-9: LLM provider returned error (raised as ToolError)
        """
        if ctx is not None:
            await ctx.info(f"analyze_agent_system: domain={domain}, req_len={len(requirements)}")

        try:
            requirements = ensure_printable_text(requirements, field="requirements")
        except ValueError as e:
            raise ToolError(f"{ERROR_REQUIREMENTS_VALIDATION}: {e}") from e

        try:
            domain = ensure_printable_text(domain, field="domain", allow_line_breaks=False)
        except ValueError as e:
            raise ToolError(f"{ERROR_REQUIREMENTS_VALIDATION}: {e}") from e

        try:
            hb = self._start_heartbeat(ctx, "analyze_agent_system")
            try:
                analysis_result = await self._pipeline.analyze(
                    requirements=requirements,
                    domain=domain,
                )
            finally:
                if hb is not None:
                    hb.cancel()

            output = self._map_to_output(analysis_result)

            if ctx is not None:
                await ctx.info(
                    f"analyze_agent_system completed: strengths={len(output.strengths)}, "
                    f"patterns={len(output.selected_patterns)}"
                )

            return output.model_dump()

        except Exception as e:
            error_msg = str(e)

            if self._is_llm_error(e):
                if ctx is not None:
                    await ctx.error(f"LLM provider error during analysis: {error_msg}")
                raise ToolError(f"{ERROR_LLM_PROVIDER}: LLM provider returned error: {error_msg}") from e

            if self._is_no_patterns_error(e):
                if ctx is not None:
                    await ctx.info(f"No patterns found for domain: {domain}")
                return AnalyzeAgentSystemOutput(
                    strengths=[],
                    weaknesses=["No patterns found for specified domain"],
                    recommendations=[f"Consider alternative domain or expand pattern database for: {domain}"],
                    recommended_topology=DEFAULT_FALLBACK_TOPOLOGY,
                    recommended_pattern_name=DEFAULT_FALLBACK_PATTERN_NAME,
                    selected_patterns=[],
                    quality_metrics=None,
                    matched_domains=[],
                    is_fallback=True,
                ).model_dump()

            if ctx is not None:
                await ctx.error(f"Unexpected error during analysis: {error_msg}")
            raise

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

    def _map_to_output(self, analysis_result: AnalysisResult) -> AnalyzeAgentSystemOutput:
        """
        Map AnalysisResult from pipeline to AnalyzeAgentSystemOutput.

        Delegates to ``analysis_to_pydantic`` which validates into ``ScoredPattern``
        so that ``analysis_score`` and ``fusion_score`` survive the boundary.
        """
        from src.tools._adapters import analysis_to_pydantic
        pd_result = analysis_to_pydantic(analysis_result)
        return AnalyzeAgentSystemOutput(
            strengths=pd_result.strengths,
            weaknesses=pd_result.weaknesses,
            recommendations=pd_result.recommendations,
            recommended_topology=pd_result.recommended_topology,
            recommended_pattern_name=pd_result.recommended_pattern_name,
            selected_patterns=[p.model_dump() for p in pd_result.selected_patterns],
            quality_metrics=pd_result.quality_metrics.model_dump() if pd_result.quality_metrics else None,
            matched_domains=[m.model_dump() for m in pd_result.matched_domains],
            is_fallback=pd_result.is_fallback,
        )

    def _is_llm_error(self, error: Exception) -> bool:
        """
        Check if error is an LLM provider error.

        E-9: ERR_009 - LLM provider returned error

        Args:
            error: Exception to check

        Returns:
            True if error is LLM-related
        """
        from src.agent import LLMError
        return isinstance(error, LLMError)

    def _is_no_patterns_error(self, error: Exception) -> bool:
        """
        Check if error indicates no patterns found for domain.

        E-2: ERR_002 - No patterns found for domain

        This checks for common error messages indicating no patterns found.

        Args:
            error: Exception to check

        Returns:
            True if error indicates no patterns found
        """
        error_msg = str(error).lower()
        no_patterns_indicators = [
            "no patterns",
            "no pattern",
            "pattern not found",
            "empty result",
            "no matching"
        ]
        return any(indicator in error_msg for indicator in no_patterns_indicators)


# MCP Tool definition function
# ADR-3: MCP Tool-Based API - FastMCP @tool decorator
def analyze_agent_system_tool(
    agent: AgentSystemArchitect,
    pipeline: AgentPatternPipeline,
    tasks_config: TasksConfig | None = None,
) -> AnalyzeAgentSystemTool:
    """
    Factory function to create AnalyzeAgentSystemTool instance.

    DP-4: Factory Pattern - Consistent tool initialization with proper dependencies

    Args:
        agent: AgentSystemArchitect instance for LLM interactions
        pipeline: AgentPatternPipeline instance for orchestrating analysis
        tasks_config: Heartbeat configuration for long-running tool defence (None = defaults applied)

    Returns:
        AnalyzeAgentSystemTool instance ready for MCP tool registration
    """
    return AnalyzeAgentSystemTool(agent=agent, pipeline=pipeline, tasks_config=tasks_config)
