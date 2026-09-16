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
AgentSystemDesignResponse - Pydantic wire schema for LLM structured output.

This module provides a Pydantic model used as the response schema for LLM
structured generation. All subfields are typed so the LLM sees the full JSON-schema
field constraints (including Relationship.source, Agent.id regex, etc.) at
generation time — enabling self-healing retry on ValidationError for any field.

``AgentSystemOverviewWire`` requires a non-empty ``overview.reasoning`` so the
model emits its design rationale before committing to agents (reason-before-
commit). The base ``design.AgentSystemOverview`` keeps ``reasoning`` optional
for external tool callers.

For the fully-typed spec schema used at FastMCP tool I/O boundaries,
see design.AgentSystemDesign and design.AgentSystemOverview.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.contracts import (
    MessageContract,
    StateModel,
    ToolContract,
)
from src.schemas.design import AgentSystemOverview
from src.schemas.components import Agent, Relationship


class AgentSystemOverviewWire(AgentSystemOverview):
    """
    LLM-facing overview with ``reasoning`` REQUIRED.

    Overrides the base schema's optional ``reasoning`` with a required,
    non-empty field so structured generation always emits the design rationale
    first (reason-before-commit: reasoning tokens precede the committed
    agent/relationship fields). External tool callers keep validating
    against the base AgentSystemOverview, whose ``reasoning`` is optional.
    """

    reasoning: str = Field(
        ...,
        min_length=1,
        description=(
            "Design rationale written BEFORE defining agents: which requirements "
            "drive which agent responsibilities, which selected patterns apply, "
            "which anti-patterns were avoided, and the key trade-offs accepted. "
            "Must be a non-empty concrete plan, not a platitude."
        ),
    )


class AgentSystemDesignResponse(BaseModel):
    """
    Pydantic response schema for LLM structured generation.

    All subfields are typed Pydantic models so the JSON schema sent to the LLM
    includes field names and constraints.  Relationship items are validated against
    Relationship (requiring source/target/type/description), and Agent items
    are validated against Agent (including the id regex ^[a-z][a-z0-9_-]*$).
    """

    overview: AgentSystemOverviewWire = Field(
        description="Agent system overview with topology, category, principles, and REQUIRED reasoning"
    )
    agents: list[Agent] = Field(
        default_factory=list,
        description="List of agents in the system"
    )
    relationships: list[Relationship] = Field(
        default_factory=list,
        description="List of agent relationships"
    )
    quality_attributes: dict[str, float] = Field(
        default_factory=dict,
        description="Quality attribute scores"
    )
    tool_contracts: list[ToolContract] = Field(
        default_factory=list,
        description="Tool contract definitions"
    )
    shared_state_models: list[StateModel] = Field(
        default_factory=list,
        description="Shared state model definitions"
    )
    message_contracts: list[MessageContract] = Field(
        default_factory=list,
        description="Message contract definitions"
    )


class AgentSystemDesignResponseWire(BaseModel):
    """
    Lean wire schema for LLM structured generation.

    Omits patterns (overridden by pipeline) and top-level contract lists (prefers agent-level placement).
    Saves ~15KB schema + 1-3K output tokens per call when enabled via retrieval.use_lean_wire_schema.
    The pipeline converts omitted fields to [] when constructing AgentSystemDesign.

    Uses AgentSystemOverviewWire to enforce REQUIRED reasoning on the lean schema.
    """

    overview: AgentSystemOverviewWire = Field(
        description="Agent system overview with topology, category, principles, and REQUIRED reasoning"
    )
    agents: list[Agent] = Field(
        default_factory=list,
        description="List of agents in the system"
    )
    relationships: list[Relationship] = Field(
        default_factory=list,
        description="List of agent relationships"
    )
    quality_attributes: dict[str, float] = Field(
        default_factory=dict,
        description="Quality attribute scores"
    )
    # Note: tool_contracts, shared_state_models, message_contracts omitted;
    # pipeline defaults to [] when constructing AgentSystemDesign.
    # patterns omitted; pipeline injects selected_patterns instead.
