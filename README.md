<!-- mcp-name: io.github.olk/agent-pattern-mcp -->

# agent-pattern-mcp

[![CI](https://img.shields.io/github/actions/workflow/status/olk/agent-pattern-mcp/ci.yml?branch=main)](https://github.com/olk/agent-pattern-mcp/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![M8ven Score](https://m8ven.ai/badge/mcp/olk/agent-pattern-mcp)](https://m8ven.ai/mcp/olk/agent-pattern-mcp)


MCP server that provides AI agent pattern expertise: generate, analyze, and evaluate agent system designs against a curated catalog of 61 agent patterns (ReAct, supervisor-worker, reflexion, self-RAG, LLMCompiler, and more).

## Table of Contents

- [Quickstart](#-quickstart)
- [Connect Your Agent](#-connect-your-agent)
- [Use the Tools](#use-the-tools)
- [Tools at a Glance](#️-tools-at-a-glance)
- [Prompts](#-prompts)
- [Pattern Catalog](#-pattern-catalog)
- [SKILL for AI Agents](#-skill-for-ai-agents)
- [Install Alternatives](#install-alternatives)
- [Configuration](#configuration)
- [Extending with Custom Patterns](#extending-with-custom-patterns)
- [Troubleshooting](#troubleshooting)
- [Building & Development](#building--development)
- [Publishing](#publishing)
- [systemd Service (Linux)](#systemd-service-linux)
- [License](#license)

## ⚡ Quickstart

```bash
# 1. Clone
git clone https://github.com/olk/agent-pattern-mcp.git && cd agent-pattern-mcp

# 2. Add your API key (the dev compose pins GENERATOR_PROVIDER=minimax and
#    loads docker/.env — not the repo-root .env)
echo 'MINIMAXAI_API_KEY=sk-...' > docker/.env

# 3. Build the images once (TEI model weights are baked in at build time,
#    ~5 GB download on the first run), then start the stack
make docker-build-all
make docker-up

# 4. Demo
make client
```

## 🔌 Connect Your Agent

### Claude Code

```bash
# Install (one-time)
npm install -g @anthropic-ai/claude-code

# Run as stdio subprocess — pass API key via env
GENERATOR_API_KEY=sk-... claude mcp add agent-pattern-mcp -- python -m src.main --transport stdio
```

### OpenCode

```bash
# Terminal 1: start the server
make docker-up
# or locally:
uv run python -m src.main

# Terminal 2: add to ~/.config/opencode/opencode.json
```

```jsonc
{
  "mcp": {
    "agent-pattern-mcp": {
      "type": "remote",
      "url": "http://localhost:8061/mcp",
      "enabled": true
    }
  }
}
```

### Codex CLI

```bash
# Install (one-time)
brew install codex

# Add to ~/.codex/config.toml
```

```toml
[mcp_servers.agent-pattern-mcp]
url = "http://localhost:8061/mcp"
```

## Use the Tools

### Design your first agent system

Ask your agent (or call the tool directly):

> Use design_agent_system to design a research assistant that combines web search with sandboxed code execution for multi-hop questions. Domain: tool-use-tasks.

The tool runs the full pipeline — analyze (pattern retrieval + requirements-weighted scoring) → generate (LLM structured output) → evaluate (metric scoring) → refine (bounded retry loop) — and returns a complete `AgentSystemDesign` with agents, relationships, tool contracts, and quality scores.

### Explore the pattern catalog

> List all agent patterns in the tool_use category.

> Get the full JSON of the react pattern.

### Async job pattern: `submit_agent_design_job` + `get_agent_design_status`

ONLY for clients with short request timeouts (Cursor, Claude Desktop, TS-SDK). The default is `design_agent_system` with heartbeat defence. `submit_agent_design_job` returns a `job_id` immediately; poll `get_agent_design_status` until done:

```
submit_agent_design_job(requirements, domain, override_topology)  → job_id
get_agent_design_status(job_id)                                  → {status, result, error}
cancel_agent_design(job_id)                                    → {cancelled, status}
```

`submit_agent_design_job` returns a `job_id` in milliseconds. The pipeline runs in a background task. Poll `get_agent_design_status(job_id)` every 10–30 seconds. When status is `completed`, the full design is in the `result` field. Cancellation is best-effort — the job exits at the next pipeline stage boundary.

**This is the only fix that works for TS-SDK clients (Claude Desktop, Cursor).**

The job store is SQLite at `~/.config/agent-pattern-mcp/jobs.db` (configurable via `AGENT_PATTERN_JOBS_DB`).

## 🛠️ Tools at a Glance

| Tool | Description |
|---|---|
| `design_agent_system` | Full pipeline: analyze → generate → evaluate → refine. Returns complete design + evaluation + quality metrics. *Long-running (5–10 min); use this unless your client has a short request timeout.* |
| `analyze_agent_system` | Analyse requirements and derive agent pattern recommendations using pattern matching and domain similarity. *Long-running (LLM call). Not idempotent.* |
| `generate_agent_system` | Generate an agent system design from requirements, topology, domain, and selected patterns. *Long-running (LLM call). Not idempotent.* |
| `evaluate_agent_system` | Evaluate an agent system design against specified criteria and domain using pattern benchmarking. *Long-running (LLM call). Not idempotent.* |
| `list_agent_patterns` | List all 61 patterns; filter by `category` and/or `domain` |
| `get_agent_pattern` | Get full JSON for a specific pattern by name |
| `submit_agent_design_job` | Start a background design job and return a `job_id` immediately. **ONLY for clients with short request timeouts** (Cursor, Claude Desktop, TS-SDK). For other clients use `design_agent_system`. Poll `get_agent_design_status` every 10–30 s. |
| `get_agent_design_status` | Poll job status. Returns the current status, progress message, and the full design output when `completed`. |
| `cancel_agent_design` | Cancel a running job (best-effort; takes effect at the next pipeline stage boundary; may take up to one LLM call). |

## 💬 Prompts

The server also exposes four user-invoked workflow prompts (slash commands in clients that support them):

| Prompt | Args | What it does |
|---|---|---|
| `design_agent_system_workflow` | `requirements*` | Full analyze → generate → evaluate pipeline |
| `explore_pattern_catalog` | `domain`, `category` | Live catalog discovery with embedded pattern names |
| `evaluate_my_agent_system` | `focus` | Guide evaluation criteria + finding prioritisation |
| `compare_agent_topologies` | `topology_a*`, `topology_b*`, `requirements*` | Two designs side-by-side; ~2× token cost |

\* = required argument

### Tool-only clients

In tool-only clients, the prompts are also exposed as tools via FastMCP's `PromptsAsTools` transform — you can call them like any other tool.

## 🧑‍🏫 SKILL for AI Agents

AI coding agents (Claude Code, OpenCode, Codex CLI) can load a SKILL that teaches them how and when to use this server's tools — including timeout-aware entry-point selection, output interpretation, and the full workflow recipe.

The SKILL lives in `skills/agent-pattern-mcp/`:

```
skills/agent-pattern-mcp/
├── SKILL.md                 # Discovery, critical rules, decision guide
└── references/
    ├── tools.md             # All 9 tool signatures and output schemas
    └── workflows.md         # 4 worked examples, 4 prompts, best practices
```

**For agents that support file-based skills** (OpenCode, Claude Code): point the agent's skill loader at `skills/agent-pattern-mcp/SKILL.md`. The skill tells the agent:

- Which tool to use based on client type and timeout budget
- How to phrase `requirements`, `domain`, and `topology` as separate structured arguments
- How to interpret `final_quality_score`, `attempts > 1`, and `evaluation.recommendations`
- When to use the async job trio vs `design_agent_system` directly

---

## 📖 Pattern Catalog

61 agent patterns across 10 categories (reasoning, tool_use, planning, reflection, research_synthesis, multi_agent, memory, retrieval, safety_control, observability) and 8 topologies (single-agent-loop, hierarchical, pipeline, plan-execute, parallel-fan-out, evaluator-loop, graph-orchestrated, swarm).

### Via MCP tools (recommended — works in all clients)

```
list_agent_patterns(category="multi_agent")
get_agent_pattern(name="supervisor-worker")
```

### Via MCP resources

```
pattern://                    → list of all patterns
pattern://{name}              → full pattern JSON
template://{name}             → curated design templates (react, supervisor-worker, multi-agent-debate, agentic-rag)
component://{type}            → component blueprints derived from pattern data
```

### Pattern JSON structure

Each `pattern/*-pattern.json` file contains: `name`, `category`, `topology`, `context`, `benefits`, `tradeoffs`, `quality_attributes` (7 dims, 1-10), `suitable_domains`, `unsuitable_domains`, `use_cases`, `avoid_when`, `component_types`, `technology_stack`, `anti_patterns`, `migration_from`, `migration_to`, `design_principles`, `best_practices`, `references`.

## Install Alternatives

### Docker (manual)

```bash
# Build the image
docker build --target production -f docker/Dockerfile -t agent-pattern-mcp:latest .

# Run with your API key
docker run -p 8061:8051 --env-file .env agent-pattern-mcp:latest
```

### Docker Hub image (compose)

Pull `olkowa/agent-pattern-mcp` without building. The hub compose starts the
MCP server only; start the TEI sidecars (`olkowa/pattern-tei-embed`,
`olkowa/pattern-tei-rerank`) separately and wire them via `EMBEDDER_BASE_URL`
/ `RERANKER_BASE_URL`:

```bash
TAG=latest docker compose -f docker/docker-compose.hub.yml up -d
```

### Local Development (uv)

```bash
# Install
uv sync

# Configure
mkdir -p ~/.config/agent-pattern-mcp
cp config/config.json ~/.config/agent-pattern-mcp/
# Edit ~/.config/agent-pattern-mcp/config.json and set your GENERATOR_API_KEY

# Run the server
uv run python -m src.main
```

## Configuration

### config.json

See `config/config.json` for the full annotated example. Key sections:

- **generator** — single LLM configuration: provider, model, temperature. Serves all pipeline phases (planning, generation, reflection).
- **embedder** — TEI (default), OpenAI, or Ollama embeddings for dense retrieval.
- **retrieval** — hybrid BM25 + dense fusion tuning: top-k caps, fusion mode (`simple` / `reciprocal_rerank`), reranker settings, quality thresholds, blend weights, topology score threshold.
- **validation** — self-healing retry loop settings (max_retries, retry_on_fail).
- **tasks** — heartbeat settings for long-running tools: `heartbeat_enabled` and `heartbeat_interval_seconds`.
- **pattern_directory** — where `*-pattern.json` files are loaded from.

### Generator LLM (LlamaIndex LiteLLM)

The generator LLM is accessed through the **LlamaIndex LiteLLM integration** ([`llama-index-llms-litellm`](https://docs.llamaindex.ai/en/stable/examples/llm/litellm/)). All provider settings therefore follow **LiteLLM's model syntax**: `<provider>/<model>` (e.g. `openai/gpt-4o-mini`, `anthropic/claude-sonnet-4-5`, `openrouter/minimax/minimax-m2`).

The server composes the LiteLLM model string from your configuration as `generator.provider` + `generator.config.model`:

| Config / env | Example | Resulting LiteLLM model string |
|---|---|---|
| `provider: "openai"`, `model: "gpt-4o-mini"` | `GENERATOR_PROVIDER=openai`, `GENERATOR_MODEL=gpt-4o-mini` | `openai/gpt-4o-mini` |
| `provider: "anthropic"`, `model: "claude-sonnet-4-5"` | `GENERATOR_PROVIDER=anthropic`, `GENERATOR_MODEL=claude-sonnet-4-5` | `anthropic/claude-sonnet-4-5` |
| `provider: "openrouter"`, `model: "minimax/minimax-m2"` | `GENERATOR_PROVIDER=openrouter`, `GENERATOR_MODEL=minimax/minimax-m2` | `openrouter/minimax/minimax-m2` |

If the configured model already contains a provider prefix (e.g. `openai/gpt-4o-mini`), that prefix is stripped and replaced by the configured `provider`.

- **Provider list, model names, and the exact `<provider>/<model>` syntax:** [LiteLLM Providers documentation](https://docs.litellm.ai/docs/providers)
- Custom/OpenAI-compatible endpoints (proxies, vLLM, Ollama, …): set `GENERATOR_BASE_URL` (`generator.config.base_url`) — it is passed as the LiteLLM `api_base`
- `GENERATOR_API_KEY` is passed as the LiteLLM `api_key`; `temperature`, `top_p`, `top_k`, and `stream` map to the corresponding LiteLLM parameters

### Key environment variables

A single LLM configuration — `generator` — serves all pipeline phases (planning, generation, reflection). Legacy `PLANNER_*` / `REFLECTOR_*` variables and config sections were removed; configs containing them are rejected with an error.

| Variable | Default | Purpose |
|---|---|---|
| `GENERATOR_API_KEY` | (required) | LLM provider API key (passed to LiteLLM as `api_key`) |
| `GENERATOR_PROVIDER` | `openai` | LiteLLM provider prefix: `openai`, `anthropic`, `openrouter`, … — see [LiteLLM Providers](https://docs.litellm.ai/docs/providers) |
| `GENERATOR_MODEL` | `gpt-4o-mini` | Model name; final model string is `<GENERATOR_PROVIDER>/<GENERATOR_MODEL>` (LiteLLM syntax) |
| `GENERATOR_TEMPERATURE` | `0.1` | LLM temperature (all phases) |
| `EMBEDDER_PROVIDER` | `tei` | Embedder provider |
| `EMBEDDER_BASE_URL` | `http://127.0.0.1:8080` | TEI endpoint |
| `RETRIEVAL_MODE` | `reciprocal_rerank` | Fusion mode |
| `RETRIEVAL_ENABLE_RERANKING` | `false` | Enable TEI cross-encoder reranking |
| `RERANKER_BASE_URL` | `http://pattern-tei-rerank:8080` | Reranker endpoint |
| `TRANSPORT` | `streamable-http` | `stdio` or `streamable-http` |
| `PORT` | `8051` | HTTP port |
| `TASKS_HEARTBEAT_ENABLED` | `true` | Enable heartbeat progress notifications during long tool calls |
| `TASKS_HEARTBEAT_INTERVAL_SECONDS` | `30` | Heartbeat interval in seconds (keep below client idle timeout) |
| `AGENT_PATTERN_JOBS_DB` | `~/.config/agent-pattern-mcp/jobs.db` | SQLite path for async job state (job trio); ephemeral in Docker |

### CLI flags

```
python -m src.main --config-path /path/to/config.json \
                   --transport stdio \
                   --host 0.0.0.0 \
                   --port 8051 \
                   --health
```

## Extending with Custom Patterns

1. Create `~/.config/agent-pattern-mcp/pattern/my-pattern-pattern.json`:

```json
{
  "name": "my-pattern",
  "topology": "single-agent-loop",
  "category": "tool_use",
  "context": "When to use this pattern — problem context and forces",
  "benefits": ["..."],
  "tradeoffs": ["..."],
  "quality_attributes": {
    "reliability": 7, "cost_efficiency": 6, "latency": 7,
    "output_quality": 8, "observability": 6, "safety": 7, "simplicity": 8
  },
  "suitable_domains": ["tool-use-tasks"],
  "use_cases": ["..."],
  "avoid_when": ["..."],
  "component_types": ["Planner: decomposes tasks"],
  "technology_stack": ["LiteLLM"],
  "anti_patterns": ["..."],
  "design_principles": ["..."],
  "best_practices": ["..."]
}
```

2. Set `PATTERN_DIRECTORY` or `pattern_directory` in config to point at the directory (or place files in the repo's `pattern/` dir).

3. Restart the server. Invalid files are skipped with a warning (lenient loading); valid ones appear in `list_agent_patterns` immediately.

## Troubleshooting

### Server starts but tools are not visible
- Verify the client config URL matches `http://localhost:8061/mcp` (note the `/mcp` path; dev default port is 8061, systemd uses 8051).
- Check `docker compose logs agent-pattern-mcp` for startup errors.

### "Connection refused" or timeout errors
- The server binds `0.0.0.0:8051` by default (in-container). If Docker is used, the dev compose publishes on host port 8061 (`"${MCP_HOST_PORT:-8061}:8051"`); systemd uses 8051.

### LLM provider errors (502 / 401)
- `GENERATOR_API_KEY` must be set (via `.env`, environment, or config).
- For MiniMax: `GENERATOR_PROVIDER=minimax`, `GENERATOR_MODEL=minimax/MiniMax-M2.7`, `GENERATOR_BASE_URL=https://api.minimax.io/v1`.

### Pattern JSON files not loading
- Files must match `*-pattern.json` and contain all required fields (`name`, `context`, `category`, `topology`, `suitable_domains`, `quality_attributes` with all 7 keys).
- Check the startup log for `Pattern validation failed` warnings.

### Async jobs not persisting across container restarts
- `jobs.db` lives at `~/.config/agent-pattern-mcp/jobs.db` inside the container; it is **ephemeral** (lost on restart). Restarting a container discards in-flight and completed jobs. To persist jobs across restarts, mount a volume and set `AGENT_PATTERN_JOBS_DB` to point at it.

## Long-running tools & timeouts

`design_agent_system` (and to a lesser extent `analyze_agent_system`, `generate_agent_system`, `evaluate_agent_system`) run multi-stage LLM pipelines that **can take 5–10 minutes per call**. This is inherent to the workload, not a bug: the generator LLM must process a large input payload — the selected pattern definitions from the 61-pattern catalog, your requirements, and the full output of every previous stage — and produce a large, strictly structured JSON document (agents, relationships, tool contracts, quality scores) one token at a time. The `design_agent_system` pipeline repeats generate → evaluate up to three times, so a single call can comprise 9+ LLM round trips.

### The timeout problem

MCP clients (AI coding agents, MCP SDKs) sit between the server and the LLM. Many implement a **client-side idle timeout**: if no data is received on the HTTP connection for some period (typically 30–120 seconds), the client aborts the request. The server is still working — the LLM is still generating — but the client closes the connection and reports a timeout error to the agent.

This is a client-side behaviour, not a server-side one. The server processes the full request correctly; the client simply gives up before the response arrives.

**Affected clients (hardcoded short timeouts):**

| Client | Timeout | Notes |
|---|---|---|
| Claude Desktop (TS-SDK) | 60 s | Hardcoded; does not reset on progress notifications |
| Cursor (TS-SDK) | 60 s | Same as Claude Desktop |
| Other TS-SDK based agents | varies | Most cap at 60–120 s |

These clients cannot be reconfigured to accept longer timeouts — the timeout is baked into the SDK.

**Clients covered by the heartbeat defence:**

| Client | Timeout | Defence |
|---|---|---|
| Claude Code | ~300 s | Heartbeat every 30 s resets idle timer |
| OpenCode | ~300 s | Heartbeat every 30 s resets idle timer |
| Codex CLI | ~300 s | Heartbeat every 30 s resets idle timer |
| Other HTTP-transport agents | varies | Most reset on any received data |

Works for these because their idle timers are reset by any incoming data — the heartbeat `progress` notifications sent from a parallel async task on the server are received by the client, resetting its clock.

### The heartbeat defence (applied by default)

Every long-running tool emits `progress` notifications from a parallel coroutine every 30 seconds (configurable via `TASKS_HEARTBEAT_INTERVAL_SECONDS`). As long as the client resets its idle timer on any received data, the request stays alive for the full duration of the pipeline.

> **TS-SDK clients (Claude Desktop, Cursor, etc.) do not reset their timeout on progress notifications.**

### The async job trio (for timeout-constrained clients)

For full control and compatibility with timeout-limited clients, three tools provide a durable job handle:

```
submit_agent_design_job(requirements, domain, override_topology)  → job_id
get_agent_design_status(job_id)                                  → {status, result, error}
cancel_agent_design(job_id)                                      → {cancelled, status}
```

`submit_agent_design_job` returns a `job_id` in milliseconds. The pipeline runs in a background task. Poll `get_agent_design_status(job_id)` every 10–30 seconds. When status is `completed`, the full design is in the `result` field. Cancellation is best-effort — the job exits at the next pipeline stage boundary.

**This is the only fix that works for TS-SDK clients (Claude Desktop, Cursor).**

### Bypassing client timeouts entirely: `make client`

The example client in `examples/agent_client.py` is a **direct Python HTTP client** — it is not an MCP agent. It calls the server over HTTP without any MCP SDK, and therefore has **no client-side idle timeout**. It makes a single blocking request and waits for the full response, regardless of how long it takes.

```bash
# Start the server (from project root; builds first if images are missing)
make docker-build-all && make docker-up

# In another terminal, run the example client
make client
```

`make client` is a development/demo tool. It demonstrates that the server **correctly completes** long requests — the timeout issue is purely a client-side problem. For production use with MCP agents, the heartbeat defence covers the majority of clients; the async job trio is the universal fallback.

## Verification Program

The repo carries a layered verification program (see [docs/verification.md](docs/verification.md) and [docs/testing-strategies.md](docs/testing-strategies.md)):

| Layer | What it proves | Entry point |
|---|---|---|
| L1 | unit suite (behavioral oracle) + secret canary | `make test-unit` |
| L1b | MCP tool-surface boundary fuzz | `make test-oracles` |
| L2 | Hypothesis property oracles over the decision modules | `make test-oracles` |
| L3 | mutation testing (mutmut ratchet) + planted-bug garden | `make test-mutations` (nightly) |
| L4 | FizzBee exhaustive model checks + FG spec garden | `make verify-fizz`, `make verify-fizz-garden` |
| L6 | deterministic-simulation races over the jobs store | `make test-oracles` |
| L8 | property-ID ledger + NL-Doc cross-consistency | `make verify-ledger`, `make verify-cross-consistency` |
| L9 | structural invariants over LLM output (opt-in live pipeline) | `uv run pytest tests/eval/ -m llm` (AGENT_BENCH_LLM=1) |
| L10 | perf smoke canary (RUN_PERF=1) | nightly workflow |

Fast gates: `make check-all` (lint + types + dead code + deps) and
`make test-all` (unit + oracles). The nightly canary lives in
`.github/workflows/verification.yml`.

## Building & Development

```bash
make install       # uv sync (dev deps included)
make check-lint    # ruff check
make check-static-typing   # mypy --strict
make test-unit     # pytest tests/unit/ with coverage
make test-oracles  # executable verification oracles
make docker-build-all   # MCP + TEI + TEI-rerank images
```

```bash
make install       # uv sync (dev deps included)
make lint          # ruff check
make typecheck     # mypy --strict (alias for static-typing)
make unit-tests    # pytest tests/unit/
make docker-build-all   # MCP + TEI + TEI-rerank images
```

## Publishing

Images publish to Docker Hub (`olkowa/*`) and GHCR (`ghcr.io/olk/*`).

### Prerequisites

- Docker Hub and GHCR (`docker login`) access.

### Publish (one-time setup + per-session)

```bash
# 1. Login to GHCR (interactive — paste token at the password prompt)
docker login ghcr.io -u olk

# 2. Build and push all three images (MCP + TEI embedder + TEI reranker)
make docker-publish-all

# 3. Logout from GHCR immediately after publishing
docker logout ghcr.io
```

The `docker-publish` target also creates and pushes an annotated git tag `v$(VERSION)`.

### First push — set packages public (GHCR only)

New GHCR packages default to private. Visit `github.com/users/olk/packages`, open each package → Package settings → Change visibility → Public.

## systemd Service (Linux)

See [systemd/README.md](systemd/README.md) for the full guide: file layout, install steps, day-to-day commands, updating, and uninstall. Summary:

> **Prerequisite:** The shared TEI infra stack must be installed first — see [`~/Projekte/Python/tei-infra/README.md`](../tei-infra/README.md). The systemd MCP stack joins the `tei-shared` external network to reach the embedder/reranker.

```bash
# 0. Install + enable shared TEI infra (once)
sudo install -m 644 ~/Projekte/Python/tei-infra/pattern-tei-infra.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pattern-tei-infra.service

# 1. Build images (once)
make docker-build-all

# 2. Deploy /etc/agent-pattern-mcp/
sudo install -d /etc/agent-pattern-mcp/config
sudo install -m 644 systemd/docker-compose.yml /etc/agent-pattern-mcp/
sudo install -m 644 ~/.config/agent-pattern-mcp/config.json /etc/agent-pattern-mcp/config/

# 3. Create the .env file (root:docker 640) and edit it.
sudo install -o root -g docker -m 640 /dev/null /etc/agent-pattern-mcp/.env
sudo $EDITOR /etc/agent-pattern-mcp/.env
# Contents:
#   MINIMAXAI_API_KEY=sk-...
#   COMPOSE_PROJECT_NAME=apmcp-systemd
#   MCP_HOST_PORT=8051

# 4. Install and enable the service.
sudo install -m 644 systemd/agent-pattern-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now agent-pattern-mcp.service
```

## License

MIT — see [LICENSE](LICENSE).
