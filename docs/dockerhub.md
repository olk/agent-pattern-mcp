# Agent-Pattern MCP server

An MCP server that provides AI agent pattern expertise to AI coding agents. Analyses requirements, selects from a curated catalog of **61 agent patterns** (ReAct, supervisor-worker, reflexion, self-RAG, LLMCompiler, …), generates concrete agent system designs with agents, relationships, and tool contracts, and evaluates them against quality attributes.

## What is this?

This Docker image contains a complete MCP (Model Context Protocol) server that brings agent design expertise to your AI coding agents. Given a requirements string and a domain, it:

- Analyzes the problem and selects matching agent patterns (hybrid BM25 + dense retrieval, TEI cross-encoder reranked)
- Generates concrete agent system designs with agents, relationships, tool contracts, and data models
- Evaluates designs against quality attributes (reliability, cost efficiency, latency, output quality, observability, safety, simplicity)
- Drives structured reasoning inside the analyze / generate / evaluate / refine phases with two embedded reasoning-MCP scratchpads (shannonthinking, code-reasoning)

## Key Features

- **61 Built-in Patterns** across 10 categories (reasoning, tool_use, planning, reflection, research_synthesis, multi_agent, memory, retrieval, safety_control, observability) and 8 topologies (single-agent-loop, hierarchical, pipeline, plan-execute, parallel-fan-out, evaluator-loop, graph-orchestrated, swarm)
- **Full Design Pipeline**: Analyze → Generate → Evaluate → Refine (up to 3 automatic refinement attempts)
- **Quality Attribute Scoring**: `final_quality_score` (0–100) plus per-attribute scores (1–10)
- **Hybrid Retrieval + Reranking**: BM25 + dense (FAISS) fusion, then a TEI cross-encoder rerank
- **Embedded Structured Reasoning**: two Node-based reasoning MCPs are baked into the image — no runtime `npx` fetch; the server refuses to start when they are unreachable
- **Dual Transport Support**: Stdio for local agents, StreamableHTTP for remote deployments
- **Extensible**: add custom patterns via JSON files — no rebuild required

```
┌───────────────────────────────────────────────────────────────────┐
│  OpenCode / Claude Code / VS Code / any MCP client                │
│        ────────── HTTP ──────────► :8061/mcp                      │
│                                                                   │
│        ┌──────────────────────────────┐                           │
│        │      agent-pattern-mcp       │                           │
│        └───────────────┬──────────────┘                           │
│                        │                                          │
│    ┌───────────────────┼────────────────────┐                     │
│    │ pattern-tei-embed │ pattern-tei-rerank │ ← pattern-tei-infra │
│    │    :8080 (TEI)    │   :8080 (TEI)      │                     │
│    └───────────────────┴────────────────────┘                     │
└───────────────────────────────────────────────────────────────────┘
```

## Architecture

This image is the **MCP server only**. The TEI embedder and TEI reranker are
separate infrastructure (published from the
[pattern-tei-infra project](https://github.com/olk/pattern-tei-infra)) as
[olkowa/pattern-tei-embed](https://hub.docker.com/r/olkowa/pattern-tei-embed) and
[olkowa/pattern-tei-rerank](https://hub.docker.com/r/olkowa/pattern-tei-rerank).

They connect via Docker DNS using the hostnames `pattern-tei-embed` and
`pattern-tei-rerank` on a shared Docker network — those are the defaults baked
into this image (`EMBEDDER_BASE_URL=http://pattern-tei-embed:8080/v1`,
`RERANKER_BASE_URL=http://pattern-tei-rerank:8080`), so the compose file below
needs no URL overrides.

The MCP server itself runs as a non-root user and serves StreamableHTTP on
container port `8051` (path `/mcp`). Startup takes **up to ~40 s**: retrieval
indexes (FAISS + BM25) are built at startup, and the server refuses to start
when the TEI sidecars are unreachable or the embedded reasoning MCPs cannot be
spawned.

## Tools at a Glance

| Tool | Description |
|------|-------------|
| `design_agent_system` | Full pipeline (analyze → generate → evaluate → refine, up to 3 attempts). **5–10 min** — use this unless your client has a short request timeout |
| `analyze_agent_system` | Analyse requirements → recommended topology, patterns, quality metrics. *Long-running (LLM call)* |
| `generate_agent_system` | Generate an agent system design from requirements, topology, domain, and selected patterns. *Long-running (LLM call)* |
| `evaluate_agent_system` | Score an existing design against quality attributes. *Long-running (LLM call)* |
| `submit_agent_design_job` | Start a background job, get `job_id` immediately — for clients with short request timeouts |
| `get_agent_design_status` | Poll job status; returns the full design when `completed` |
| `cancel_agent_design` | Cancel a running job (best-effort; takes effect at the next pipeline stage boundary) |
| `list_agent_patterns` | List all 61 patterns; filter by `category` and/or `domain` |
| `get_agent_pattern` | Get full JSON for a specific pattern by name |

**Example call:**
```
Call design_agent_system with:
  requirements: "Research assistant combining web search with sandboxed code execution for multi-hop questions"
  domain: "tool-use-tasks"
```

Patterns are also exposed as MCP resources: `pattern://` (catalog list),
`pattern://{name}` (full pattern JSON), `template://{name}` (curated design
templates) and `component://{type}` (component blueprints).

## Prompts (Slash Commands)

| Prompt | Args | What it does |
|--------|------|--------------|
| `/design_agent_system_workflow` | requirements* | Full analyze → generate → evaluate pipeline |
| `/explore_pattern_catalog` | domain, category | Live catalog discovery with embedded pattern names |
| `/evaluate_my_agent_system` | focus | Guide evaluation criteria + prioritisation |
| `/compare_agent_topologies` | topology_a*, topology_b*, requirements* | Two designs side-by-side (~2× token cost) |

\* = required

In tool-only clients the prompts are also callable as tools via FastMCP's
`PromptsAsTools` transform — the server then exposes `list_prompts` and
`get_prompt` alongside the nine tools above.

## Prerequisites

- **Docker** 24+ with compose plugin (`docker compose version`)
- **An LLM API key** for any LiteLLM-compatible provider (OpenAI, Anthropic, MiniMax, DeepSeek, Ollama, vLLM, OpenRouter, or any OpenAI-compatible endpoint)
- **Disk**: ~5 GB for the three images (MCP server + embedder + reranker)
- **CPU only** — no GPU required

## Long-running Tools & Timeouts

`design_agent_system` runs multi-stage LLM pipelines that **can take 5–10 minutes** — the generator LLM processes the selected pattern definitions, your requirements, and the full output of every previous stage across 9+ round trips.

### The Timeout Problem

MCP clients implement **client-side idle timeouts** (typically 30–120 s). If no data is received, the client aborts — even though the server is still working correctly.

| Client | Timeout | Notes |
|--------|---------|-------|
| Claude Desktop (TS-SDK) | 60 s | Hardcoded; does not reset on progress |
| Cursor (TS-SDK) | 60 s | Same as Claude Desktop |
| Claude Code | ~300 s | Heartbeat every 30 s resets idle timer |
| OpenCode | ~300 s | Heartbeat every 30 s resets idle timer |
| Codex CLI | ~300 s | Heartbeat every 30 s resets idle timer |

### Solutions

1. **Heartbeat defence (default)** — The server emits `progress` notifications every 30 s, resetting idle timers for most HTTP clients.

2. **Async job trio** — For timeout-constrained clients (Claude Desktop, Cursor), use `submit_agent_design_job` + `get_agent_design_status` + `cancel_agent_design`. Returns a `job_id` immediately; poll every 10–30 s.

3. **Direct HTTP client** — The repo's example client (`examples/agent_client.py`, `make client`) bypasses the MCP SDK entirely with no idle timeout.

## Quick start

All images from Docker Hub — no git clone, no GitHub fetches. Config is baked into the image.

```bash
mkdir agent-pattern-mcp && cd agent-pattern-mcp

cat > docker-compose.yml <<'EOF'
services:
  pattern-tei-embed:
    image: olkowa/pattern-tei-embed:${TEI_TAG:-latest}
    restart: unless-stopped
    environment: [HF_HUB_OFFLINE=1]
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8080/health || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 120s
  pattern-tei-rerank:
    image: olkowa/pattern-tei-rerank:${TEI_TAG:-latest}
    restart: unless-stopped
    environment: [HF_HUB_OFFLINE=1]
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8080/health || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 60s
  agent-pattern-mcp:
    image: olkowa/agent-pattern-mcp:${TAG:-latest}
    ports: ["${MCP_HOST_PORT:-8061}:8051"]
    environment:
      - GENERATOR_API_KEY=${GENERATOR_API_KEY:?Set GENERATOR_API_KEY in .env}
      # The TEI sidecar needs no key, but the client library requires one.
      - EMBEDDER_API_KEY=not-needed
      - PATTERN_DIRECTORY=./pattern
    depends_on:
      pattern-tei-embed:
        condition: service_healthy
      pattern-tei-rerank:
        condition: service_healthy
    restart: on-failure
    healthcheck:
      test: ["CMD", "python", "-m", "src.main", "--health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
EOF

echo 'GENERATOR_API_KEY=sk-...' > .env
docker compose up -d
docker compose ps
```

The server starts on **streamable-http** at `http://localhost:8061/mcp`. First
run pulls ~2.2 GB of image layers (~5 GB on disk); the TEI embedder needs
**~1–2 minutes** to become healthy (healthcheck `start_period: 120s`) and the
MCP server **up to ~40 s** after that. `docker compose ps` shows all three
services `Up` / `healthy`.

> **Reproducibility tip:** pin versions with `TAG=1.0.2` (MCP server) and
> `TEI_TAG=1.1.1` (sidecars). The heredoc reads `${TAG:-latest}` and
> `${TEI_TAG:-latest}` so any tag on Docker Hub is honored.

> **Standalone stack:** this compose starts its own TEI sidecars. If you already
> run the shared `pattern-tei-infra` stack, drop the two sidecar services and
> point `EMBEDDER_BASE_URL` / `RERANKER_BASE_URL` at those containers instead.

> **Network topology:** the compose creates an isolated default network. The MCP
> container reaches the sidecars by their service names (`pattern-tei-embed`,
> `pattern-tei-rerank`) — these match the `EMBEDDER_BASE_URL` and
> `RERANKER_BASE_URL` defaults baked into the image, so no URL overrides are
> required.

## Bringing your own LLM

Override with any `.env` combination:

| Provider | `.env` additions |
|---|---|
| **OpenAI** (default) | `GENERATOR_PROVIDER=openai` · `GENERATOR_MODEL=gpt-4o-mini` · `GENERATOR_BASE_URL=https://api.openai.com/v1` · `GENERATOR_API_KEY=sk-...` |
| **Anthropic** | `GENERATOR_PROVIDER=anthropic` · `GENERATOR_MODEL=claude-sonnet-4-5` · `GENERATOR_API_KEY=sk-ant-...` |
| **MiniMax** | `GENERATOR_PROVIDER=minimax` · `GENERATOR_MODEL=minimax/MiniMax-M2.7` · `GENERATOR_BASE_URL=https://api.minimax.io/v1` · `GENERATOR_API_KEY=...` |
| **DeepSeek** | `GENERATOR_PROVIDER=deepseek` · `GENERATOR_MODEL=deepseek-chat` · `GENERATOR_BASE_URL=https://api.deepseek.com/v1` · `GENERATOR_API_KEY=sk-...` |
| **Ollama / vLLM / OpenRouter / any OpenAI-compatible** | `GENERATOR_BASE_URL=http://host:11434/v1` · `GENERATOR_MODEL=...` · `GENERATOR_API_KEY=...` |

### Generator LLM (LlamaIndex LiteLLM)

The generator LLM is accessed through the **LlamaIndex LiteLLM integration**
([`llama-index-llms-litellm`](https://docs.llamaindex.ai/en/stable/examples/llm/litellm/)).
All provider settings follow **LiteLLM's model syntax**: `<provider>/<model>`
(e.g. `openai/gpt-4o-mini`, `anthropic/claude-sonnet-4-5`,
`openrouter/minimax/minimax-m2`).

The server composes the LiteLLM model string from your configuration as
`generator.provider` + `generator.config.model`:

| Config / env | Example | Resulting LiteLLM model string |
|---|---|---|
| `provider: "openai"`, `model: "gpt-4o-mini"` | `GENERATOR_PROVIDER=openai`, `GENERATOR_MODEL=gpt-4o-mini` | `openai/gpt-4o-mini` |
| `provider: "anthropic"`, `model: "claude-sonnet-4-5"` | `GENERATOR_PROVIDER=anthropic`, `GENERATOR_MODEL=claude-sonnet-4-5` | `anthropic/claude-sonnet-4-5` |
| `provider: "openrouter"`, `model: "minimax/minimax-m2"` | `GENERATOR_PROVIDER=openrouter`, `GENERATOR_MODEL=minimax/minimax-m2` | `openrouter/minimax/minimax-m2` |

If the configured model already contains a provider prefix (e.g. `openai/gpt-4o-mini`), that prefix is stripped and replaced by the configured `provider`.

- **Provider list, model names, and the exact `<provider>/<model>` syntax:** [LiteLLM Providers documentation](https://docs.litellm.ai/docs/providers)
- Custom/OpenAI-compatible endpoints (proxies, vLLM, Ollama, …): set `GENERATOR_BASE_URL` — it is passed as the LiteLLM `api_base`
- `GENERATOR_API_KEY` is passed as the LiteLLM `api_key`; `GENERATOR_TEMPERATURE`, `GENERATOR_TOP_P`, `GENERATOR_TOP_K`, and `GENERATOR_STREAM` map to the corresponding LiteLLM parameters

## TEI sidecar configuration

The MCP server connects to the TEI embedder at
`http://pattern-tei-embed:8080/v1` and the TEI reranker at
`http://pattern-tei-rerank:8080` by default (Docker DNS names). Override if
your setup differs:

| Variable | Default | Description |
|---|---|---|
| `EMBEDDER_BASE_URL` | `http://pattern-tei-embed:8080/v1` | TEI embedder URL |
| `RERANKER_BASE_URL` | `http://pattern-tei-rerank:8080` | TEI reranker URL |
| `RERANKER_TIMEOUT` | `30` | Reranker request timeout (seconds) |

The embedder (`olkowa/pattern-tei-embed`) carries
`Qwen3-Embedding-0.6B` (ONNX fp32) and the reranker
(`olkowa/pattern-tei-rerank`) carries `gte-reranker-modernbert-base` — both
baked into their images, fully offline (`HF_HUB_OFFLINE=1`, no downloads, no
API keys at runtime).

Full env var reference: [GitHub README → Configuration](https://github.com/olk/agent-pattern-mcp#configuration)

## Embedded reasoning MCPs

The image bakes two Node-based reasoning MCP servers — `shannonthinking` and
`code-reasoning` — into `/usr/local/lib/node_modules`. The pipeline invokes
them directly via `node` (no runtime `npx` fetch); they act as structured
scratchpads that validate and number the thoughts the pipeline's own LLM
authors.

| Variable | Default | Description |
|---|---|---|
| `REASONING_ENABLED` | `true` | Enable the embedded reasoning MCPs |
| `REASONING_FAIL_FAST` | `true` | Exit at startup if the reasoning tools are unreachable, instead of continuing degraded |
| `REASONING_SPAWN_TIMEOUT_SECONDS` | `10` | Process spawn timeout |
| `REASONING_STEP_TIMEOUT_SECONDS` | `20` | Per-thought tool-call timeout |
| `REASONING_MAX_TOTAL_STEPS` | `8` | Max thoughts per phase |

Set `REASONING_ENABLED=false` to opt out (loses the structured-reasoning
cross-validation; pipeline output stays valid).

## Connect your agent

### OpenCode

Add to `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "agent-pattern-mcp": {
      "type": "remote",
      "url": "http://localhost:8061/mcp",
      "enabled": true
    }
  }
}
```

### VS Code (MCP extension)

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "agent-pattern-mcp": {
      "url": "http://localhost:8061/mcp",
      "type": "http"
    }
  }
}
```

### Codex CLI

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.agent-pattern-mcp]
url = "http://localhost:8061/mcp"
```

### Claude Code (stdio transport)

> **Stdio transport** — this section is for Claude Code subprocess mode.
> It requires a local `git clone` (one-time setup). If you want HTTP transport
> (recommended for Docker Hub users), use the Quick start above instead.

```bash
# Install (one-time)
git clone https://github.com/olk/agent-pattern-mcp.git && cd agent-pattern-mcp
uv pip install -e .

# Add to your agent
GENERATOR_API_KEY=sk-... claude mcp add agent-pattern-mcp -- python -m src.main --transport stdio
```

## Try it

Ask your agent:

> Use design_agent_system to design a research assistant that combines web search with sandboxed code execution for multi-hop questions. Domain: tool-use-tasks.

This should call `design_agent_system` with:
- `requirements`: "Research assistant combining web search with sandboxed code execution for multi-hop questions"
- `domain`: "tool-use-tasks"

The tool runs the full pipeline — analyze (pattern retrieval + requirements-weighted scoring) → generate (LLM structured output) → evaluate (metric scoring) → refine (bounded retry loop) — and returns a complete design with agents, relationships, tool contracts, and quality scores.

## Operations

```bash
# Upgrade to latest images
docker compose pull && docker compose up -d

# View logs
docker compose logs -f agent-pattern-mcp

# Stop
docker compose down

# Pin a specific version
TAG=1.0.2 docker compose up -d
```

On Linux with a shared host, restrict your `.env` file:
```bash
chmod 600 .env
```

> **Async jobs are ephemeral in Docker.** The jobs store lives at
> `~/.config/agent-pattern-mcp/jobs.db` inside the container and is lost on
> restart. To persist it, mount a volume and set `AGENT_PATTERN_JOBS_DB` to a
> path inside it.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `401 Unauthorized` from LLM | Check `GENERATOR_API_KEY` in `.env`; verify the key is active |
| Tools not visible in the client | Verify the client URL matches `http://localhost:8061/mcp` (note the `/mcp` path); check `docker compose logs agent-pattern-mcp` |
| TEI connection errors / startup fails fast | Ensure both sidecar containers are healthy (`docker compose ps`); verify `pattern-tei-embed` and `pattern-tei-rerank` resolve on the shared network; override `EMBEDDER_BASE_URL` / `RERANKER_BASE_URL` if your network differs |
| Startup exits with reasoning errors | The embedded reasoning MCPs could not be spawned; check `docker compose logs`, or set `REASONING_ENABLED=false` to run degraded |
| Port 8061 already in use | `MCP_HOST_PORT=8062 docker compose up -d`, then update your client URL |
| `design_agent_system` times out in the client | Expected for 60 s TS-SDK clients — use the async job trio (`submit_agent_design_job` + `get_agent_design_status`) |

## Links

- **GitHub** (source, docs, issue tracker): [olk/agent-pattern-mcp](https://github.com/olk/agent-pattern-mcp)
- **GHCR mirror**: [ghcr.io/olk/agent-pattern-mcp](https://github.com/olk/agent-pattern-mcp/pkgs/container/agent-pattern-mcp)
- **TEI infrastructure** (embedder + reranker): [olk/pattern-tei-infra](https://github.com/olk/pattern-tei-infra) · [olkowa/pattern-tei-embed](https://hub.docker.com/r/olkowa/pattern-tei-embed) · [olkowa/pattern-tei-rerank](https://hub.docker.com/r/olkowa/pattern-tei-rerank)
- **Sister project** (architecture design rather than agent design): [olk/architecture-pattern-mcp](https://github.com/olk/architecture-pattern-mcp)
- **License**: [MIT](https://github.com/olk/agent-pattern-mcp/blob/main/LICENSE)
