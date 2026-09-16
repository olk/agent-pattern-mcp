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
Unit tests for src/design_normalization.py.
"""

from src.design_normalization import denormalize_contracts
from src.schemas import AgentSystemDesign
from src.schemas.components import Agent, Relationship
from src.schemas.contracts import (
    ToolContract,
    StateModel,
    MessageContract,
)
from src.schemas.design import AgentSystemOverview
from src.schemas.enums import AgentTopology, PatternCategory


def _make_design(
    *,
    tool_contracts: list[ToolContract] | None = None,
    shared_state_models: list[StateModel] | None = None,
    message_contracts: list[MessageContract] | None = None,
    agents: list[Agent] | None = None,
    relationships: list[Relationship] | None = None,
) -> AgentSystemDesign:
    """Helper: build a minimal AgentSystemDesign for testing."""
    return AgentSystemDesign(
        overview=AgentSystemOverview(
            topology=AgentTopology.HIERARCHICAL,
            category=PatternCategory.PLANNING,
            principles=["single responsibility"],
        ),
        agents=agents or [
            Agent(
                id="svc",
                name="Service",
                role="service",
                description="A service",
                responsibilities=["process"],
            )
        ],
        relationships=relationships or [],
        quality_attributes={},
        tool_contracts=tool_contracts or [],
        shared_state_models=shared_state_models or [],
        message_contracts=message_contracts or [],
    )


class TestDenormalizeToolContracts:
    def test_promotes_tool_contract(self):
        """Tool contracts are deduplicated by (tool_name, agent_id)."""
        tc1 = ToolContract(
            tool_name="web_search",
            agent_id="user-service",
            description="Web search tool",
        )
        tc2 = ToolContract(
            tool_name="web_search",
            agent_id="user-service",
            description="Duplicate tool",
        )
        design = _make_design(tool_contracts=[tc1, tc2])
        result = denormalize_contracts(design)

        assert len(result.tool_contracts) == 1
        assert result.tool_contracts[0].tool_name == "web_search"

    def test_different_agents_keep_separate_tools(self):
        """Same tool_name but different agent_id are kept separate."""
        tc1 = ToolContract(tool_name="web_search", agent_id="service-a", description="")
        tc2 = ToolContract(tool_name="web_search", agent_id="service-b", description="")
        design = _make_design(tool_contracts=[tc1, tc2])
        result = denormalize_contracts(design)

        assert len(result.tool_contracts) == 2


class TestDenormalizeSharedStateModels:
    def test_dedupes_shared_models_by_name_and_is_shared(self):
        """Same name with different is_shared → both kept as separate entries."""
        m1 = StateModel(name="User", is_shared=False, fields=[])
        m2 = StateModel(name="User", is_shared=True, fields=[])
        design = _make_design(shared_state_models=[m1, m2])
        result = denormalize_contracts(design)

        assert len(result.shared_state_models) == 2

    def test_same_name_same_is_shared_deduplicated(self):
        """Same name and is_shared → deduplicated."""
        m1 = StateModel(name="User", is_shared=True, fields=[])
        m2 = StateModel(name="User", is_shared=True, fields=[])
        design = _make_design(shared_state_models=[m1, m2])
        result = denormalize_contracts(design)

        assert len(result.shared_state_models) == 1


class TestDenormalizeMessageContracts:
    def test_dedupes_message_contracts_by_name(self):
        """Duplicate message_name → one kept."""
        ec = MessageContract(
            message_name="user.created",
            payload_schema={"type": "object"},
            published_by="user-service",
        )
        design = _make_design(message_contracts=[ec, ec])
        result = denormalize_contracts(design)

        assert len(result.message_contracts) == 1
        assert result.message_contracts[0].message_name == "user.created"


class TestDenormalizeIdempotency:
    def test_idempotent_under_repeated_application(self):
        """Two consecutive calls yield the same result."""
        tc = ToolContract(tool_name="web_search", agent_id="user-service", description="")
        design = _make_design(tool_contracts=[tc])
        first = denormalize_contracts(design)
        second = denormalize_contracts(first)

        assert first.tool_contracts == second.tool_contracts
        assert first.shared_state_models == second.shared_state_models
        assert first.message_contracts == second.message_contracts

    def test_round_trip_through_model_dump_and_validate(self):
        """model_dump → model_validate preserves contract lists."""
        tc = ToolContract(tool_name="web_search", agent_id="user-service", description="")
        design = _make_design(tool_contracts=[tc])
        result = denormalize_contracts(design)

        dumped = result.model_dump()
        revalidated = AgentSystemDesign.model_validate(dumped)

        assert len(revalidated.tool_contracts) == len(result.tool_contracts)


class TestDenormalizeNoOp:
    def test_no_op_when_no_contracts(self):
        """Empty tool_contracts, shared_state_models, message_contracts → unchanged."""
        design = _make_design(
            tool_contracts=[],
            shared_state_models=[],
            message_contracts=[],
        )
        result = denormalize_contracts(design)

        assert result.tool_contracts == []
        assert result.shared_state_models == []
        assert result.message_contracts == []


class TestDenormalizePreservesOtherFields:
    def test_preserves_other_fields_unchanged(self):
        """overview, agents, relationships untouched."""
        rel = Relationship(
            source="api-gateway",
            target="user-service",
            type="http",
            description="Proxies to user service",
        )
        design = _make_design(relationships=[rel])
        result = denormalize_contracts(design)

        assert result.overview.topology == AgentTopology.HIERARCHICAL
        assert len(result.agents) == 1
        assert len(result.relationships) == 1
        assert result.relationships[0].source == "api-gateway"


class TestDenormalizeMultipleAgents:
    def test_multiple_tool_contracts_promoted(self):
        """Two agents with distinct tool_contracts → two top-level entries."""
        tc1 = ToolContract(tool_name="web_search", agent_id="user-service", description="")
        tc2 = ToolContract(tool_name="code_runner", agent_id="order-service", description="")
        design = _make_design(tool_contracts=[tc1, tc2])
        result = denormalize_contracts(design)

        assert len(result.tool_contracts) == 2
        tool_names = {tc.tool_name for tc in result.tool_contracts}
        assert tool_names == {"web_search", "code_runner"}
