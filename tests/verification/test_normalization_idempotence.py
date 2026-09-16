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
L2 Hypothesis oracle pinning the design-normalization decision boundary
(docs/verification.md: ``model_copy`` semantics are pinned by executable
property at the adapter).

Properties (Tier A):
  N-1  idempotence: denormalize(denormalize(d)) == denormalize(d)
  N-2  tool-contract dedup: (tool_name, agent_id) unique among
       top-level tool_contracts
  N-3  message dedup: message_contracts unique by message_name,
       order preserved
  N-4  shared-model dedup: (name, is_shared) unique among
       shared_state_models

Collision-prone small ID/name pools force the dedup branches; generated
designs explore shapes unit tests chose by hand.
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import BaseModel

from src.design_normalization import denormalize_contracts
from src.schemas import (
    Agent,
    AgentSystemDesign,
    AgentSystemOverview,
    MessageContract,
    StateModel,
    ToolContract,
)
from src.schemas.enums import AgentTopology, PatternCategory

AGENT_IDS = ["planner", "executor", "critic"]
TOOL_NAMES = ["web_search", "code_runner"]
MODEL_NAMES = ["TaskPlan", "ConversationState"]
MESSAGE_NAMES = ["task.assigned", "result.ready"]


def _fixed_agent() -> Agent:
    return Agent(
        id="planner",
        name="Planner",
        role="planner",
        description="d",
        responsibilities=["r"],
    )


def _design_builder(
    tools: list[ToolContract],
    models: list[StateModel],
    messages: list[MessageContract],
) -> AgentSystemDesign:
    return AgentSystemDesign(
        overview=AgentSystemOverview(
            topology=AgentTopology.HIERARCHICAL,
            category=PatternCategory.MULTI_AGENT,
            principles=["p"],
        ),
        agents=[_fixed_agent()],
        relationships=[],
        quality_attributes={"reliability": 8.0},
        tool_contracts=tools,
        shared_state_models=models,
        message_contracts=messages,
    )


class _DesignBuilder(BaseModel):
    @staticmethod
    def build(
        tools: list[ToolContract],
        models: list[StateModel],
        messages: list[MessageContract],
    ) -> AgentSystemDesign:
        return _design_builder(tools, models, messages)


class TestDesignNormalizationProperties:
    @given(
        tools=st.lists(
            st.builds(
                ToolContract,
                tool_name=st.sampled_from(TOOL_NAMES),
                agent_id=st.sampled_from(AGENT_IDS),
            ),
            max_size=4,
        ),
        models=st.lists(
            st.builds(
                StateModel, name=st.sampled_from(MODEL_NAMES), is_shared=st.booleans()
            ),
            max_size=4,
        ),
        messages=st.lists(
            st.builds(
                MessageContract,
                message_name=st.sampled_from(MESSAGE_NAMES),
                payload_schema=st.just({}),
                published_by=st.sampled_from(AGENT_IDS),
            ),
            max_size=4,
        ),
    )
    @settings(max_examples=50, deadline=None)
    def test_normalization_properties(
        self,
        tools: list[ToolContract],
        models: list[StateModel],
        messages: list[MessageContract],
    ) -> None:
        design = _DesignBuilder.build(tools, models, messages)

        once = denormalize_contracts(design)
        twice = denormalize_contracts(once)

        assert twice.model_dump() == once.model_dump(), "N-1: idempotence"
        tool_keys = [(tc.tool_name, tc.agent_id) for tc in once.tool_contracts]
        assert len(tool_keys) == len(set(tool_keys)), "N-2: unique (tool_name, agent_id)"
        names = [mc.message_name for mc in once.message_contracts]
        assert names == list(dict.fromkeys(names)), "N-3: messages deduped, order kept"
        model_keys = [(m.name, m.is_shared) for m in once.shared_state_models]
        assert len(model_keys) == len(set(model_keys)), "N-4: shared models deduped"

    def test_idempotence_on_unit_style_design(self) -> None:
        """Deterministic sanity pin: a design with duplicated contracts
        normalizes to the same shape as the unit-suite fixtures."""
        design = _design_builder(
            tools=[
                ToolContract(tool_name="web_search", agent_id="planner"),
                ToolContract(tool_name="web_search", agent_id="planner"),
            ],
            models=[
                StateModel(name="TaskPlan", is_shared=True),
                StateModel(name="TaskPlan", is_shared=True),
            ],
            messages=[
                MessageContract(
                    message_name="task.assigned",
                    payload_schema={},
                    published_by="planner",
                ),
                MessageContract(
                    message_name="task.assigned",
                    payload_schema={},
                    published_by="planner",
                ),
            ],
        )
        result = denormalize_contracts(denormalize_contracts(design))
        assert len(result.tool_contracts) == 1
        assert len(result.shared_state_models) == 1
        assert len(result.message_contracts) == 1
