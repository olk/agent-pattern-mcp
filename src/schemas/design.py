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
Agent system design schemas.

Defines the complete agent system design output including overview, agents,
relationships, and contracts.
"""

from pydantic import BaseModel, Field

from src.schemas.components import Agent, Relationship
from src.schemas.contracts import MessageContract, StateModel, ToolContract
from src.schemas.enums import AgentTopology, PatternCategory


class AgentSystemOverview(BaseModel):
    """
    Top-level agent system overview.

    Summarises the topology, category, guiding principles, and constraints.

    The ``reasoning`` field captures the designer's structured thinking before
    committing to agents and relationships, ensuring traceable rationale.
    It is optional in this base schema (for external tool callers) but REQUIRED
    on the wire schema used for LLM structured generation.
    """

    reasoning: str | None = Field(
        default=None,
        description=(
            "Design rationale written BEFORE defining agents: which requirements "
            "drive which agent responsibilities, which selected patterns apply, "
            "which anti-patterns were avoided, and the key trade-offs accepted. "
            "Must be a non-empty concrete plan, not a platitude."
        ),
    )
    topology: AgentTopology = Field(
        ...,
        description="Agent topology from AgentTopology enum"
    )
    category: PatternCategory = Field(
        ...,
        description="Pattern category (reasoning, tool_use, planning, reflection, research_synthesis, multi_agent, memory, retrieval, safety_control, observability)"
    )
    principles: list[str] = Field(
        ...,
        min_length=1,
        description="Guiding design principles"
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Design constraints and requirements"
    )
    score: float | None = Field(
        default=None,
        description=(
            "Analyze-phase selection score (analysis_score); same metric as "
            "alternative_topologies[].score. None when the topology was not scored "
            "by analyze (override_topology without a match, or fallback)."
        ),
    )


class AgentSystemDesign(BaseModel):
    """
    Complete agent system design output.

    Contains all structural, contractual, and deployment information for
    a generated agent system.
    """

    overview: AgentSystemOverview = Field(
        ...,
        description="Agent system overview"
    )
    agents: list[Agent] = Field(
        ...,
        min_length=1,
        description="Agents in the system"
    )
    relationships: list[Relationship] = Field(
        default_factory=list,
        description="Agent relationships"
    )
    quality_attributes: dict[str, float] = Field(
        default_factory=dict,
        description="Quality attribute scores"
    )
    tool_contracts: list[ToolContract] = Field(
        default_factory=list,
        description="Tool contracts for agent tools"
    )
    shared_state_models: list[StateModel] = Field(
        default_factory=list,
        description="State models shared across agents"
    )
    message_contracts: list[MessageContract] = Field(
        default_factory=list,
        description="Message contracts for async agent communication"
    )
