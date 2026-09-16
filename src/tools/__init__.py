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
Tool factory functions for MCP tools.

DP-4: Factory Pattern - Consistent tool creation with proper initialization
DP-5: Dependency Injection - Constructor injection of dependencies

Each factory function creates a tool instance with the appropriate dependencies.
"""

import asyncio

from src.agent import AgentSystemArchitect
from src.config import TasksConfig
from src.patterns.loader import PatternLoader
from src.pipeline import AgentPatternPipeline, CancellationToken
from src.tools.analyze import AnalyzeAgentSystemTool, analyze_agent_system_tool
from src.tools.cancel_agent_design import CancelAgentDesignTool, cancel_agent_design_tool
from src.tools.design import DesignAgentSystemTool, design_agent_system_tool
from src.tools.evaluate import EvaluateAgentSystemTool, evaluate_agent_system_tool
from src.tools.generate import GenerateAgentSystemTool, generate_agent_system_tool
from src.tools.get_agent_design_status import GetAgentDesignStatusTool, get_agent_design_status_tool
from src.tools.patterns import (
    GetAgentPatternTool,
    ListAgentPatternsTool,
    get_agent_pattern_tool,
    list_agent_patterns_tool,
)
from src.tools.submit_agent_design import SubmitAgentDesignJobTool, submit_agent_design_job_tool

__all__ = [
    "AnalyzeAgentSystemTool",
    "CancelAgentDesignTool",
    "DesignAgentSystemTool",
    "EvaluateAgentSystemTool",
    "GenerateAgentSystemTool",
    "GetAgentDesignStatusTool",
    "GetAgentPatternTool",
    "ListAgentPatternsTool",
    "SubmitAgentDesignJobTool",
    "analyze_agent_system_tool",
    "cancel_agent_design_tool",
    "design_agent_system_tool",
    "evaluate_agent_system_tool",
    "generate_agent_system_tool",
    "get_agent_design_status_tool",
    "get_agent_pattern_tool",
    "list_agent_patterns_tool",
    "submit_agent_design_job_tool",
]


def create_all_tools(
    agent: AgentSystemArchitect,
    pipeline: AgentPatternPipeline,
    pattern_loader: PatternLoader,
    tasks_config: TasksConfig | None = None,
    *,
    job_tasks: dict[str, tuple[asyncio.Task[None], CancellationToken]] | None = None,
) -> dict[str, object]:
    """
    Factory function to create all MCP tool instances.

    DP-4: Factory Pattern - Consistent tool creation with proper dependencies

    Args:
        agent: AgentSystemArchitect instance for LLM interactions.
        pipeline: AgentPatternPipeline instance for orchestrating design pipeline.
        pattern_loader: PatternLoader instance for direct pattern catalog access.
        tasks_config: TasksConfig instance for heartbeat settings (None = defaults applied).
        job_tasks: Shared {job_id: (task, cancellation_token)} registry for
                   the submit/get_status/cancel tool trio.

    Returns:
        dict: Dictionary mapping tool names to tool instances.
    """
    jt = job_tasks if job_tasks is not None else {}
    return {
        "design_agent_system": design_agent_system_tool(agent, pipeline, tasks_config=tasks_config),
        "analyze_agent_system": analyze_agent_system_tool(agent, pipeline, tasks_config=tasks_config),
        "generate_agent_system": generate_agent_system_tool(agent, pipeline, tasks_config=tasks_config),
        "evaluate_agent_system": evaluate_agent_system_tool(agent, pipeline, tasks_config=tasks_config),
        "list_agent_patterns": list_agent_patterns_tool(pattern_loader),
        "get_agent_pattern": get_agent_pattern_tool(pattern_loader),
        "submit_agent_design_job": submit_agent_design_job_tool(agent, pipeline, job_tasks=jt),
        "get_agent_design_status": get_agent_design_status_tool(),
        "cancel_agent_design": cancel_agent_design_tool(job_tasks=jt),
    }
