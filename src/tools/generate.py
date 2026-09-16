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
GenerateAgentSystemTool - MCP tool for generating agent system designs based on requirements.

FR-222: The system SHALL provide a GenerateAgentSystemTool class
API-3: /tools/generate_agent_system endpoint (POST) for generating agent system designs
CF-3: generate_agent_system function with requirements, topology, domain, and selected_patterns
DF-3: Generate with pattern metadata flow

Error Handling:
- E-3: ERR_003 - Failed to generate agent system design (HTTP 500, severity: error)
- E-9: ERR_009 - LLM provider returned error (HTTP 502, severity: error)
- E-12: ERR_012 - Malformed agent system overview at I/O boundary (HTTP 400, severity: warn)

Implementation Notes:
- Uses FastMCP @tool decorator for MCP protocol
- Pydantic v2 for input validation
- Delegates to AgentPatternPipeline for LLM-based generation
- Factory Pattern (DP-4) for consistent tool initialization
- Builder Pattern (DP-9) for constructing AgentSystemDesign

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
from src.errors import ERROR_INVALID_AGENT_SYSTEM, ERROR_REQUIREMENTS_VALIDATION, MalformedAgentSystemOverviewError
from src.pipeline import AgentPatternPipeline
from src.schemas.design import AgentSystemDesign
from src.text_validation import DomainName, PrintableText, ensure_printable_text
from src.schemas.enums import validate_topology_value

logger = logging.getLogger(__name__)


# Error codes for E-3, E-9, and E-12
ERROR_GENERATION_FAILED = "ERR_003"


class GenerateAgentSystemOutput(BaseModel):
    """
    Output schema for GenerateAgentSystemTool.

    ENT-12: AgentSystemDesign with overview, agents, relationships,
            quality_attributes, tool_contracts, shared_state_models,
            message_contracts

    Attributes:
        overview: Overview of the agent system design
        agents: List of agents in the system
        relationships: List of agent relationships
        quality_attributes: Quality attribute annotations
        tool_contracts: API contract definitions
        shared_state_models: Shared data model definitions
        message_contracts: Event contract definitions
    """

    # ENT-12: AgentSystemDesign overview attribute
    overview: dict[str, Any] = Field(
        default_factory=dict,
        description="Overview of the agent system design"
    )

    # ENT-12: AgentSystemDesign agents attribute
    agents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of agent system agents"
    )

    # ENT-12: AgentSystemDesign relationships attribute
    relationships: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of agent relationships"
    )

    # ENT-12: AgentSystemDesign quality_attributes attribute
    quality_attributes: dict[str, float] = Field(
        default_factory=dict,
        description="Quality attribute scores"
    )

    # ENT-12: AgentSystemDesign tool_contracts attribute
    tool_contracts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="API contract definitions"
    )

    # ENT-12: AgentSystemDesign shared_state_models attribute
    shared_state_models: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Shared data model definitions"
    )

    # ENT-12: AgentSystemDesign message_contracts attribute
    message_contracts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Event contract definitions"
    )


class GenerateAgentSystemTool:
    """
    MCP tool for generating agent system designs based on requirements.

    FR-222: The system SHALL provide a GenerateAgentSystemTool class
    AC-222: Verify GenerateAgentSystemTool class exists, accepts AgentSystemArchitect

    This tool generates agent system designs based on requirements, topology, domain,
    and selected patterns. It uses AgentSystemArchitect for LLM interactions and
    delegates to AgentPatternPipeline for generation.

    Attributes:
        _agent: AgentSystemArchitect instance for LLM interactions
        _pipeline: AgentPatternPipeline instance for orchestrating generation
        _tasks_config: TasksConfig for heartbeat settings

    Error Handling:
        E-3 (ERR_003): Failed to generate agent system design - logged with provider_message
        E-9 (ERR_009): LLM provider returned error - logged with provider context

    DP-4: Factory Pattern - Tool creation with consistent initialization
    DP-7: Adapter Pattern - Adapts FastMCP protocol to internal implementation
    DP-9: Builder Pattern - AgentSystemDesign construction with multiple agents
    """

    def __init__(
        self,
        agent: AgentSystemArchitect,
        pipeline: AgentPatternPipeline,
        tasks_config: TasksConfig | None = None,
    ) -> None:
        """
        Initialize GenerateAgentSystemTool.

        AC-222: Verify GenerateAgentSystemTool class exists, accepts AgentSystemArchitect

        Args:
            agent: AgentSystemArchitect instance for LLM interactions
            pipeline: AgentPatternPipeline instance for orchestrating generation
            tasks_config: Heartbeat configuration for long-running tool defence
        """
        self._agent = agent
        self._pipeline = pipeline
        self._tasks_config = tasks_config

        logger.debug(
            "GenerateAgentSystemTool initialized",
            extra={
                "agent_type": type(agent).__name__,
                "pipeline_type": type(pipeline).__name__
            }
        )

    @tool(
        name="generate_agent_system",
        description="Generate an agent system design from requirements, topology, domain, and selected patterns.",
        tags={"agent", "generation"},
        annotations=ToolAnnotations(
            title="Generate Agent System",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )
    async def generate(  # noqa: PLR0912, PLR0915
        self,
        requirements: Annotated[PrintableText, Field(description="Agent system requirements description (1-100000 chars, must contain visible text)")],
        topology: Annotated[PrintableText, Field(description="Agent topology to use (1-100000 chars, must contain visible text)")],
        domain: Annotated[DomainName, Field(description="Target agent domain (1-200 chars, must contain visible text)")],
        selected_patterns: Annotated[list[str] | None, Field(description="Pattern names to incorporate in the agent system")] = None,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """
        Generate a new agent system design based on requirements.

        FR-222: GenerateAgentSystemTool class generates agent system designs
        CF-3: generate_agent_system function with requirements, topology, domain, selected_patterns
        API-3: /tools/generate_agent_system endpoint

        DF-3: Flow - MCP Client -> MCPAgentPatternServer -> GenerateAgentSystemTool.generate()
              -> AgentPatternPipeline.generate() -> AgentSystemArchitect

        This method:
        1. Validates inputs
        2. Resolves pattern names to full pattern dicts via PatternLoader
        3. Delegates to AgentPatternPipeline.generate() with selected patterns
        4. Maps AgentSystemDesign to output dict
        5. Handles E-3 and E-9 errors appropriately

        Args:
            requirements: Agent system requirements description
            topology: Agent topology to use
            domain: Target agent domain
            selected_patterns: Pattern names to incorporate
            ctx: FastMCP context for logging and progress reporting

        Returns:
            dict with generated agent system design

        Error Responses:
            E-3: Failed to generate agent system design (raised as ToolError)
            E-9: LLM provider returned error (raised as ToolError)
        """
        if selected_patterns is None:
            selected_patterns = []

        if ctx is not None:
            await ctx.info(
                f"generate_agent_system: domain={domain}, topology={topology}, "
                f"req_len={len(requirements)}, patterns={len(selected_patterns)}"
            )

        try:
            requirements = ensure_printable_text(requirements, field="requirements")
        except ValueError as e:
            raise ToolError(f"{ERROR_REQUIREMENTS_VALIDATION}: {e}") from e

        try:
            topology = ensure_printable_text(topology, field="topology")
            topology = validate_topology_value(topology)
        except ValueError as e:
            raise ToolError(f"{ERROR_REQUIREMENTS_VALIDATION}: {e}") from e

        try:
            domain = ensure_printable_text(domain, field="domain", allow_line_breaks=False)
        except ValueError as e:
            raise ToolError(f"{ERROR_REQUIREMENTS_VALIDATION}: {e}") from e

        resolved: list[dict[str, Any]] = []
        pattern_loader = getattr(self._pipeline, "_pattern_loader", None)
        for name in selected_patterns:
            if pattern_loader is None:
                logger.warning(
                    "generate_agent_system: pattern_loader unavailable, skipping '%s'",
                    name,
                )
                continue
            p = pattern_loader.get_by_name(name)
            if p is None:
                logger.warning(
                    "generate_agent_system: pattern '%s' not found in catalogue, skipped",
                    name,
                )
                continue
            resolved.append(p)

        try:
            hb = self._start_heartbeat(ctx, "generate_agent_system")
            try:
                agent_system_design = await self._pipeline.generate(
                    requirements=requirements,
                    topology=topology,
                    domain=domain,
                    selected_patterns=resolved,
                )
            finally:
                if hb is not None:
                    hb.cancel()

            output = self._map_to_output(agent_system_design)

            if ctx is not None:
                await ctx.info(
                    f"generate_agent_system completed: agents={len(output.agents)}, "
                    f"relationships={len(output.relationships)}"
                )

            return output.model_dump()

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
                    await ctx.error(f"LLM provider error during generation: {error_msg}")
                raise ToolError(
                    f"{ERROR_LLM_PROVIDER}: LLM provider returned error: {error_msg}"
                ) from e

            if ctx is not None:
                await ctx.error(f"Failed to generate agent system design: {error_msg}")
            raise ToolError(
                f"{ERROR_GENERATION_FAILED}: Failed to generate agent system design: {error_msg}"
            ) from e

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

    def _map_to_output(self, agent_system_design: AgentSystemDesign) -> GenerateAgentSystemOutput:
        """
        Map AgentSystemDesign from pipeline to GenerateAgentSystemOutput.

        DP-9: Builder Pattern - AgentSystemDesign has many optional fields and nested objects

        Args:
            agent_system_design: AgentSystemDesign from AgentPatternPipeline.generate()

        Returns:
            GenerateAgentSystemOutput mapped from agent_system_design
        """
        from src.tools._adapters import design_to_pydantic
        pd_design = design_to_pydantic(agent_system_design)
        return GenerateAgentSystemOutput(
            overview=pd_design.overview.model_dump(),
            agents=[c.model_dump() for c in pd_design.agents],
            relationships=[r.model_dump() for r in pd_design.relationships],
            quality_attributes=pd_design.quality_attributes,
            tool_contracts=[a.model_dump() for a in pd_design.tool_contracts],
            shared_state_models=[m.model_dump() for m in pd_design.shared_state_models],
            message_contracts=[e.model_dump() for e in pd_design.message_contracts],
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


# MCP Tool definition function
# ADR-3: MCP Tool-Based API - FastMCP @tool decorator
def generate_agent_system_tool(
    agent: AgentSystemArchitect,
    pipeline: AgentPatternPipeline,
    tasks_config: TasksConfig | None = None,
) -> GenerateAgentSystemTool:
    """
    Factory function to create GenerateAgentSystemTool instance.

    DP-4: Factory Pattern - Consistent tool initialization with proper dependencies

    Args:
        agent: AgentSystemArchitect instance for LLM interactions
        pipeline: AgentPatternPipeline instance for orchestrating generation
        tasks_config: Heartbeat configuration for long-running tool defence (None = defaults applied)

    Returns:
        GenerateAgentSystemTool instance ready for MCP tool registration
    """
    return GenerateAgentSystemTool(agent=agent, pipeline=pipeline, tasks_config=tasks_config)
