# Agent Pattern MCP — Client Demo

A standalone Python script that connects to a running MCP server over HTTP,
calls `design_agent_system` with a tool-use agent requirements string,
and pretty-prints the full JSON result to stdout.

## Quick Start

**Terminal 1 — start the server:**

```bash
python -m src.main
# Server listens on http://0.0.0.0:8051/mcp
```

**Terminal 2 — run the client:**

```bash
uv run python examples/agent_client.py
```

## Output

The script prints a single JSON object to stdout containing:

| Key | Description |
|---|---|
| `design` | Full `AgentSystemDesign` (overview, agents, relationships, tool_contracts, shared_state_models, message_contracts, quality_attributes) |
| `evaluation` | `AgentSystemEvaluation` (summary, metrics, risks, recommendations) |
| `attempts` | Number of refine cycles performed |
| `final_topology` | Resolved agent topology |
| `final_quality_score` | Quality score after refinement |
| `quality_metrics` | Aggregated quality metrics from analysis |

The `design.overview.topology` will typically be `"single-agent-loop"` (react) or
`"hierarchical"` (supervisor-worker) for tool-use requirements, and the agents
will decompose into planner → searcher/executor → synthesiser roles.

## Customising

Edit these constants at the top of `examples/agent_client.py`:

```python
SERVER_URL = "http://localhost:8051/mcp"
TOOL_USE_AGENT_REQUIREMENTS = "..."     # your own requirements text
DOMAIN = "tool-use-tasks"                # e.g. "rag-applications", "code-generation"
```

## Server LLM configuration

The demo requires a running server whose generator LLM is configured in the
**LlamaIndex LiteLLM** format — a LiteLLM model string of the form
`<provider>/<model>` (e.g. `openai/gpt-4o-mini`), set via `GENERATOR_PROVIDER`
and `GENERATOR_MODEL`. For the provider/model syntax reference see the
[LiteLLM Providers documentation](https://docs.litellm.ai/docs/providers);
for full configuration options see the main README's
[Generator LLM section](../README.md#generator-llm-llamaindex-litellm).

## Tips

Pipe the output to `jq` to inspect parts of the result:

```bash
uv run python examples/agent_client.py 2>/dev/null | jq '.design.overview'
uv run python examples/agent_client.py 2>/dev/null | jq '.design.agents[].id'
uv run python examples/agent_client.py 2>/dev/null | jq '.evaluation.summary'
```
