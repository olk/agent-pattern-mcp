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
State, tool, and message contract schemas for agent system designs.

These models define the structure of contracts between agents:
- StateField / StateModel: shared state entity definitions
- ToolContract: tool interface contracts bound to specific agents
- MessageContract: async message/event interfaces between agents
"""

from typing import Any

from pydantic import BaseModel, Field


class StateField(BaseModel):
    """
    Single field within a StateModel.
    """

    name: str = Field(
        ...,
        description="Field name"
    )
    type: str = Field(
        ...,
        description="Field type (str, int, float, bool, datetime, list, dict)"
    )
    required: bool = Field(
        default=True,
        description="Whether field is required"
    )
    description: str = Field(
        default="",
        description="Field description"
    )
    default: Any | None = Field(
        default=None,
        description="Default value if any"
    )


class StateModel(BaseModel):
    """
    State entity definition shared across agents.
    """

    name: str = Field(
        ...,
        min_length=1,
        description="Model name, e.g. 'TaskPlan', 'ConversationState'"
    )
    fields: list[StateField] = Field(
        default_factory=list,
        description="Model fields"
    )
    description: str = Field(
        default="",
        description="Model description"
    )
    is_shared: bool = Field(
        default=False,
        description="Whether this model is shared across agents"
    )


class ToolContract(BaseModel):
    """
    Tool contract bound to a specific agent.

    Defines the interface for a tool that an agent can invoke.
    """

    tool_name: str = Field(
        ...,
        min_length=1,
        description="Tool name, e.g. 'web_search', 'code_runner'"
    )
    agent_id: str = Field(
        ...,
        min_length=1,
        description="Reference to agent that owns this tool"
    )
    description: str = Field(
        default="",
        description="Tool description"
    )
    input_schema: dict[str, Any] | None = Field(
        default=None,
        description="JSON Schema for tool input"
    )
    output_schema: dict[str, Any] | None = Field(
        default=None,
        description="JSON Schema for tool output"
    )
    auth_required: bool = Field(
        default=False,
        description="Whether authentication is required for this tool"
    )


class MessageContract(BaseModel):
    """
    Async message/event contract between agents.

    Published by one agent, consumed by one or more others.
    """

    message_name: str = Field(
        ...,
        min_length=1,
        description="Message name, e.g. 'task.assigned', 'result.ready'"
    )
    payload_schema: dict[str, Any] = Field(
        ...,
        description="JSON Schema for message payload"
    )
    published_by: str = Field(
        ...,
        min_length=1,
        description="Agent ID that publishes this message"
    )
    consumed_by: list[str] = Field(
        default_factory=list,
        description="Agent IDs that consume this message"
    )
    description: str = Field(
        default="",
        description="Message description"
    )
