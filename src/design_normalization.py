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
Pure transformations on AgentSystemDesign for contract deduplication.

Agent system contracts (tool_contracts, shared_state_models, message_contracts)
are defined at the top level of AgentSystemDesign, not per-agent. This module
deduplicates them by their natural keys.
"""

from src.schemas import (
    AgentSystemDesign,
    MessageContract,
    StateModel,
    ToolContract,
)


def denormalize_contracts(design: AgentSystemDesign) -> AgentSystemDesign:
    """Deduplicate top-level contract lists by their natural keys.

    Precedence rules:
      1. tool_contracts deduped by (tool_name, agent_id); first occurrence wins.
      2. shared_state_models deduped by (name, is_shared); first occurrence wins.
      3. message_contracts deduped by message_name; first occurrence wins.

    Idempotent. Uses model_copy(update=..., deep=True). Caller must treat
    the returned design as immutable — list fields are references to trusted
    input.
    """
    seen_tools: set[tuple[str, str]] = set()
    promoted_tools: list[ToolContract] = []
    for tc in design.tool_contracts:
        key = (tc.tool_name, tc.agent_id)
        if key not in seen_tools:
            promoted_tools.append(tc)
            seen_tools.add(key)

    seen_models: set[tuple[str, str]] = set()
    promoted_models: list[StateModel] = []
    for m in design.shared_state_models:
        key = (m.name, str(m.is_shared))
        if key not in seen_models:
            promoted_models.append(m)
            seen_models.add(key)

    seen_messages: set[str] = set()
    promoted_messages: list[MessageContract] = []
    for mc in design.message_contracts:
        if mc.message_name not in seen_messages:
            promoted_messages.append(mc)
            seen_messages.add(mc.message_name)

    return design.model_copy(
        update={
            "tool_contracts": promoted_tools,
            "shared_state_models": promoted_models,
            "message_contracts": promoted_messages,
        },
        deep=True,
    )
