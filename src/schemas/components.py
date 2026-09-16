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
Agent and relationship schemas for agent system designs.

Defines the structural agents of an agent system and their interactions.
"""

from pydantic import BaseModel, Field


class Agent(BaseModel):
    """
    Agent definition within an agent system design.

    Represents an agent with a specific role, responsibilities, tools,
    memory, and LLM configuration.
    """

    id: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_-]*$",
        description="Unique agent identifier (kebab-case)"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable agent name"
    )
    role: str = Field(
        ...,
        min_length=1,
        description="Agent role (e.g. 'planner', 'executor', 'critic', 'retriever', 'router')"
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Agent description"
    )
    responsibilities: list[str] = Field(
        ...,
        min_length=1,
        description="Key responsibilities"
    )
    llm_role: str | None = Field(
        default=None,
        description="LLM role for this agent ('planning', 'generation', 'reflection', or None)"
    )
    tools: list[str] = Field(
        default_factory=list,
        description="Tools available to this agent"
    )
    memory: list[str] = Field(
        default_factory=list,
        description="Memory capabilities (e.g. ['conversation_history', 'task_state'])"
    )
    prompt_strategy: list[str] | None = Field(
        default=None,
        description="Prompt strategy steps for this agent"
    )
    technology_stack: list[str] = Field(
        default_factory=list,
        description="Technologies used (e.g. ['LangGraph', 'LiteLLM'])"
    )
    config_requirements: list[str] = Field(
        default_factory=list,
        description="Required environment variables (e.g. ['OPENAI_API_KEY', 'TAVILY_API_KEY'])"
    )


class Relationship(BaseModel):
    """
    Directed relationship between two agents.
    """

    source: str = Field(
        ...,
        description="Source agent ID"
    )
    target: str = Field(
        ...,
        description="Target agent ID"
    )
    type: str = Field(
        ...,
        description="Relationship type (e.g. 'delegates', 'critiques', 'feeds')"
    )
    description: str = Field(
        ...,
        description="Human-readable description of the interaction"
    )
