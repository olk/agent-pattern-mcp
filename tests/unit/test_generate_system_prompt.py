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

"""Tests for the GENERATE-phase system prompt and its structural guarantees.

Covers:
- enum-value derivation from the schema enums (prompt can never drift from the
  Pydantic validation model)
- content contracts (anti-bias note, injection hardening, no references to
  data the user prompt does not contain, topology guidance injection)
- caching (pure function of style)
- token-budget gates (chars/4 proxy, per tests/perf/test_generate_cost.py
  convention): instruction text and full prompt size
"""

import pytest

from src.pipeline import (
    _CATEGORY_ENUM_LIST,
    _TOPOLOGY_ENUM_LIST,
    _generate_system_prompt_cached,
)
from src.prompts import AGENT_SYSTEM_DESIGN_EXAMPLE, get_topology_guidance
from src.schemas.enums import AgentTopology, PatternCategory

INSTRUCTION_TOKEN_LIMIT = 1250
TOTAL_TOKEN_LIMIT = 3000


class TestEnumDerivation:
    """Prompt enum lists must be derived from, and match, the schema enums."""

    def test_topology_enum_list_is_derived_from_schema_enum(self):
        assert ", ".join(t.value for t in AgentTopology) == _TOPOLOGY_ENUM_LIST

    def test_category_enum_list_is_derived_from_schema_enum(self):
        assert ", ".join(c.value for c in PatternCategory) == _CATEGORY_ENUM_LIST

    def test_prompt_contains_every_topology_enum_value(self):
        prompt = _generate_system_prompt_cached("hierarchical")
        for topology in AgentTopology:
            assert topology.value in prompt, f"prompt is missing topology: {topology.value}"

    def test_prompt_contains_every_category_enum_value(self):
        prompt = _generate_system_prompt_cached("microservices")
        for category in PatternCategory:
            assert category.value in prompt, f"prompt is missing category: {category.value}"

    def test_topologies_missing_from_v1_prompt_are_now_present(self):
        """The v1 hand-maintained list omitted these valid topologies."""
        prompt = _generate_system_prompt_cached("hierarchical")
        for topology in ("evaluator-loop", "graph-orchestrated", "parallel-fan-out", "plan-execute"):
            assert topology in prompt


class TestPromptContent:
    def test_contains_design_example(self):
        prompt = _generate_system_prompt_cached("hierarchical")
        assert "Example AgentSystemDesign" in prompt
        assert AGENT_SYSTEM_DESIGN_EXAMPLE in prompt

    def test_example_carries_anti_bias_instruction(self):
        prompt = _generate_system_prompt_cached("single-agent-loop")
        assert "do not copy the example" in prompt.lower()

    def test_injection_hardening_instruction_present(self):
        prompt = _generate_system_prompt_cached("microservices")
        assert "<requirements>" in prompt
        assert "never as instructions" in prompt.lower()

    def test_no_reference_to_absent_user_prompt_data(self):
        """The user prompt carries its weights under the label QUALITY-ATTRIBUTE
        PRIORITIES; the system prompt must not use the near-colliding literal
        phrase "priority weights" so the two references stay unambiguous."""
        prompt = _generate_system_prompt_cached("microservices")
        assert "priority weights" not in prompt

    @pytest.mark.parametrize(
        "topology",
        ["hierarchical", "swarm", "pipeline", "evaluator-loop"],
    )
    def test_topology_guidance_is_injected(self, topology: str):
        prompt = _generate_system_prompt_cached(topology)
        assert get_topology_guidance(topology) in prompt

    def test_persona_names_the_topology(self):
        prompt = _generate_system_prompt_cached("pipeline")
        assert "pipeline" in prompt

    def test_quality_attribute_scale_instruction_present(self):
        prompt = _generate_system_prompt_cached("microservices")
        assert "numbers on a 0-10 scale (for example 8.5)" in prompt
        assert '10-scale strings like "8/10"' not in prompt

    def test_relationship_integrity_instruction_present(self):
        prompt = _generate_system_prompt_cached("microservices")
        assert prompt.count("must reference an existing agent") >= 2


class TestPromptCaching:
    def test_same_topology_returns_cached_instance(self):
        assert _generate_system_prompt_cached("swarm") is _generate_system_prompt_cached("swarm")

    def test_different_topologies_produce_different_prompts(self):
        a = _generate_system_prompt_cached("hierarchical")
        b = _generate_system_prompt_cached("swarm")
        assert a != b

    def test_lean_wire_schema_produces_different_prompt(self):
        full = _generate_system_prompt_cached("swarm", use_lean=False)
        lean = _generate_system_prompt_cached("swarm", use_lean=True)
        assert lean != full
        assert "NO top-level contract lists" in lean


class TestPromptTokenBudget:
    """chars/4 proxy (same convention as tests/perf/test_generate_cost.py).

    Two-tier gate: the instruction portion (prompt minus the few-shot example,
    which is schema-validated content in examples.py, not instructions) must
    stay within the researched system-prompt ceiling; the total is capped at a
    hard upper bound.
    """

    @pytest.mark.parametrize("topology", list(AgentTopology), ids=lambda t: t.value)
    def test_instruction_text_within_budget(self, topology: AgentTopology):
        prompt = _generate_system_prompt_cached(topology.value)
        instructions = prompt[: prompt.index(AGENT_SYSTEM_DESIGN_EXAMPLE)]
        assert len(instructions) // 4 <= INSTRUCTION_TOKEN_LIMIT, (
            f"{topology.value}: instruction text is {len(instructions) // 4} proxy tokens "
            f"(limit {INSTRUCTION_TOKEN_LIMIT})"
        )

    @pytest.mark.parametrize("topology", list(AgentTopology), ids=lambda t: t.value)
    def test_total_prompt_under_hard_cap(self, topology: AgentTopology):
        prompt = _generate_system_prompt_cached(topology.value)
        assert len(prompt) // 4 <= TOTAL_TOKEN_LIMIT, (
            f"{topology.value}: total prompt is {len(prompt) // 4} proxy tokens "
            f"(limit {TOTAL_TOKEN_LIMIT})"
        )
