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
Agent Pattern MCP — Client Demo

Connects to a running MCP server over HTTP, calls design_agent_system
with a tool-use agent requirements string, and pretty-prints the
returned JSON to stdout.

Usage:
    # Terminal 1: start the server
    $ python -m src.main

    # Terminal 2: run the client
    $ uv run python examples/agent_client.py

Or pipe the JSON output:
    $ uv run python examples/agent_client.py 2>/dev/null | jq '.design.overview'

Requires:
    - MCP server running on http://localhost:8051/mcp (default)
    - Valid LLM credentials in the server's config
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from fastmcp import Client  # type: ignore[attr-defined]

SERVER_URL = os.environ.get("AGENT_CLIENT_URL", "http://localhost:8051/mcp")

TOOL_USE_AGENT_REQUIREMENTS = """
Build a research assistant agent that answers multi-hop questions by combining
web search results with sandboxed Python computation. The agent must decompose
each question into sub-questions, decide for each sub-question whether to search
the web (fetching and ranking results) or run code (executing Python in a
sandbox to compute answers), observe the results, and iterate until it can
synthesise a final cited answer. Tool calls must be grounded in observations,
and every intermediate step must be logged for auditability. Target: under 30
seconds per question with a hard step budget of 10 iterations.
""".strip()

DOMAIN = "tool-use-tasks"


async def call_design_agent_system(server_url: str) -> dict[str, Any]:
    """Connect to the MCP server and call the design_agent_system tool."""
    client = Client(server_url)

    async with client:
        tools = await client.list_tools()
        print(f"Connected to {server_url}", file=sys.stderr)
        print(f"Available tools: {[t.name for t in tools]}", file=sys.stderr)

        print(f"Calling design_agent_system(domain='{DOMAIN}')...", file=sys.stderr)
        result = await client.call_tool(
            "design_agent_system",
            {
                "requirements": TOOL_USE_AGENT_REQUIREMENTS,
                "domain": DOMAIN,
            },
        )
        return result.data


def print_json(result: dict[str, Any]) -> None:
    """Pretty-print the tool result to stdout as JSON."""
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def amain() -> int:
    try:
        result = await call_design_agent_system(SERVER_URL)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(
            "Hint: is the MCP server running? Start it with: python -m src.main",
            file=sys.stderr,
        )
        return 1

    print_json(result)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(amain()))
