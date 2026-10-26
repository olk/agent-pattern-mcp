# Agent Pattern MCP — Client Demo

A standalone Python script that connects to a running MCP server over HTTP,
calls one tool with a tool-use agent requirements string, and pretty-prints
the JSON result to stdout. One script, two modes:

- `analyze_agent_system` (default) — ANALYZE phase only: recommended
  topology, selected patterns with scores, matched domains. Fast; no
  design generated.
- `design_agent_system` (`--tool design`) — full design artifact: analyze →
  generate → evaluate → refine. Long-running (minutes).

## Quick Start

**Terminal 1 — start the server:**

```bash
python -m src.main
# Server listens on http://0.0.0.0:8050/mcp
```

**Terminal 2 — run the client:**

```bash
uv run python examples/agent_client.py                  # analyze (fast)
uv run python examples/agent_client.py --tool design    # full design

# or via make (server on http://localhost:8821/mcp):
make client-analyze
make client-design
```

## Output

### analyze (default)

| Key | Description |
|---|---|
| `recommended_topology` | Topology derived from the top-scoring pattern (e.g. `single-agent-loop`, `hierarchical`) |
| `recommended_pattern_name` | Name of the top-scored pattern that drove the topology recommendation |
| `selected_patterns` | Ranked catalogue patterns with `analysis_score`, `fusion_score`, `fusion_score_normalized` and `blended_score` |
| `quality_metrics` | Aggregated quality metrics from the analysis |
| `strengths` / `weaknesses` / `recommendations` | Deterministic narrative for this selection |
| `matched_domains` | Top retrieved domain slugs with fusion/rerank scores |
| `is_fallback` | `true` when no real domain match was found and the fallback `react` pattern was used |

The exact ranking depends on the requirement weights the server extracts, but the research-assistant text above targets the tool-use family (e.g. `react`, `plan-and-solve`); no agents, relationships or tool contracts are generated.

### design (`--tool design`)

The full `PipelineResult`:

| Key | Description |
|---|---|
| `design` | `AgentSystemDesign`: overview, agents, relationships, tool/state/message contracts, quality attributes |
| `evaluation` | `AgentSystemEvaluation`: summary, metrics, risks, recommendations |
| `attempts` | Generate attempts performed (initial + retries) |
| `final_topology` | Final agent topology |
| `final_pattern_name` | Top-scored pattern matching the final topology |
| `quality_metrics` | Aggregated quality metrics from the analysis |
| `final_quality_score` | Best-attempt quality score |
| `alternative_topologies` | Runner-up topologies from the analyze phase |
| `matched_domains` / `is_fallback` | Retrieval provenance and fallback flag |

The `design.overview.topology` will typically be `"single-agent-loop"` (react) or
`"hierarchical"` (supervisor-worker) for tool-use requirements, and the agents
will decompose into planner → searcher/executor → synthesiser roles.

## Customising

Edit these constants at the top of `examples/agent_client.py`:

```python
SERVER_URL = "http://localhost:8821/mcp"
TOOL_USE_AGENT_REQUIREMENTS = "..."     # your own requirements text
DOMAIN = "tool-use-tasks"                # a catalogue suitable_domains slug
```

`domain` must be a slug the catalogue indexes (e.g. `tool-use-tasks`, `rag-applications`, `code-generation`); an unknown slug yields weak matches.

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
# analyze (default)
uv run python examples/agent_client.py 2>/dev/null | jq '.recommended_topology'
uv run python examples/agent_client.py 2>/dev/null | jq '.selected_patterns[].name'
uv run python examples/agent_client.py 2>/dev/null | jq '.matched_domains'

# design
uv run python examples/agent_client.py --tool design 2>/dev/null | jq '.design.overview'
uv run python examples/agent_client.py --tool design 2>/dev/null | jq '.design.agents[].id'
uv run python examples/agent_client.py --tool design 2>/dev/null | jq '.evaluation.summary'
```
