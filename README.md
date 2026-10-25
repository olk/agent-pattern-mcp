<!-- mcp-name: io.github.olk/agent-pattern-mcp -->

# agent-pattern-mcp

[![CI](https://img.shields.io/github/actions/workflow/status/olk/agent-pattern-mcp/ci.yml?branch=main)](https://github.com/olk/agent-pattern-mcp/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![M8ven Score](https://m8ven.ai/badge/mcp/olk/agent-pattern-mcp)](https://m8ven.ai/mcp/olk/agent-pattern-mcp)


An MCP (Model Context Protocol) server that provides agent system design expertise to AI coding agents. Given a requirements string and a domain, it analyses the problem, selects matching agent patterns (from 68 built-in patterns), generates a concrete agent system design with agents, relationships, tool contracts, state models, and message contracts, and evaluates it against quality attributes (reliability, cost efficiency, latency, output quality, observability, safety, simplicity). Coding agents that write the implementation themselves can call `analyze_agent_system` for topology and scored-pattern guidance **without** generating a design.

---

## Table of Contents

- [⚡ Quickstart](#-quickstart)
- [Install via AI Agent](#install-via-ai-agent)
- [🔌 Connect Your Agent](#-connect-your-agent)
  - [Claude Code](#claude-code)
  - [OpenCode](#opencode)
  - [Codex CLI](#codex-cli)
- [🧑‍🏫 SKILL for AI Agents](#-skill-for-ai-agents)
- [🧪 Use the Tools](#-use-the-tools)
  - [Design your first agent system](#design-your-first-agent-system)
  - [Explore the pattern catalog](#explore-the-pattern-catalog)
- [🛠️ Tools at a Glance](#️-tools-at-a-glance)
- [📖 Pattern Catalog](#-pattern-catalog)
- [Install Alternatives](#install-alternatives)
  - [Docker (manual)](#docker-manual)
  - [Local Development (uv)](#local-development-uv)
- [Configuration](#configuration)
- [Structured Reasoning (shannonthinking / code-reasoning)](#structured-reasoning-shannonthinking--code-reasoning)
- [Extending with Custom Patterns](#extending-with-custom-patterns)
- [Long-running tools & timeouts](#long-running-tools--timeouts)
- [Troubleshooting](#troubleshooting)
- [Building & Development](#building--development)
- [Publishing](#publishing)
- [systemd Service (Linux)](#systemd-service-linux)
- [License](#license)

## ⚡ Quickstart

```bash
# 1. Clone
git clone https://github.com/olk/agent-pattern-mcp.git && cd agent-pattern-mcp

# 2. Add your API key (the dev compose reads MINIMAXAI_API_KEY and pins
#    GENERATOR_PROVIDER=minimax)
export MINIMAXAI_API_KEY=sk-...

# 3. Start (needs images: `make docker-build-all` once, or prebuilt pulls
#    per INSTALL.md Path A)
docker compose -f docker/docker-compose.yml up -d

# 4. Demo
make client
```

Server starts on **streamable-http** at `http://localhost:8821/mcp` (dev compose host port; systemd uses 8811). Then connect your agent below.

---

## Install via AI Agent

To have an AI coding agent install the Docker stack from prebuilt images (no local build), point it at **[INSTALL.md](INSTALL.md)** — the non-interactive agent runbook (copy-paste commands, expected outputs, verification probes).

```text
Clone this repo, then follow INSTALL.md Path A (compose stack, port 8821).
My generator API key is: sk-...
```

Pick one path in `INSTALL.md`:

- **Path A — Compose stack** (`:8821`): evaluating / developing, no sudo needed. Own TEI sidecar copies.
- **Path B — systemd stack** (`:8811`): persistent host service, starts at boot, needs `sudo`. Uses the shared `pattern-tei-infra` TEI stack.

The agent needs a repo clone, Docker ≥ v2.20 with group membership, ~5 GB free, a `MINIMAXAI_API_KEY` (or another provider per `INSTALL.md#switching-the-generator-llm`), and linux/amd64 (on arm64 it builds locally via `make docker-build-all`). After install, continue with [Connect Your Agent](#-connect-your-agent) below.

---

## 🔌 Connect Your Agent

### Claude Code

```bash
# Install (one-time)
uv pip install -e .

# Run as stdio subprocess — pass API key via env
claude mcp add agent-pattern \
  -e GENERATOR_API_KEY=your_key \
  -e GENERATOR_PROVIDER=openai \
  -- agent-pattern-mcp --transport stdio
```

Or add to your project for the whole team:

```bash
claude mcp add --scope project agent-pattern \
  -e GENERATOR_API_KEY=your_key \
  -- agent-pattern-mcp --transport stdio
```

### OpenCode

OpenCode uses HTTP transport. Start the server first, then configure opencode:

```bash
# Terminal 1: start the server
docker compose -f docker/docker-compose.yml up --build   # serves :8821
# or locally on the same port:
uv run python -m src.main --port 8821

# Terminal 2: add to ~/.config/opencode/opencode.json
```

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "agent-pattern": {
      "type": "remote",
      "url": "http://localhost:8821/mcp"
    }
  }
}
```

> **Note:** `GENERATOR_API_KEY` is read from the server's config file (`~/.config/agent-pattern-mcp/config.json`), not from opencode's environment.

### Codex CLI

```bash
# Install (one-time)
uv pip install -e .
```

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.agent-pattern]
command = "agent-pattern-mcp"
args = ["--transport", "stdio"]

[mcp_servers.agent-pattern.env]
GENERATOR_API_KEY = "your_key"
GENERATOR_PROVIDER = "openai"
```

Or via CLI:

```bash
codex mcp add agent-pattern \
  -e GENERATOR_API_KEY=your_key \
  -- agent-pattern-mcp --transport stdio
```

---

## 🧑‍🏫 SKILL for AI Agents

The SKILL in `skills/agent-pattern-mcp/` is written for **Oh My Pi (OMP)**, where this server's tools are reached as `xd://mcp__agent_pattern_*` devices and every MCP request is bounded by a deadline (`OMP_MCP_TIMEOUT_MS` → per-server `timeout` → 30 s). It teaches the agent which entry point fits that deadline, how to read the results, and the full workflow recipes.

```
skills/agent-pattern-mcp/
├── SKILL.md                 # OMP constraints, entry-point decision guide, device quick reference
└── references/
    ├── tools.md             # 9 tool signatures, output schemas, error codes, design-dict shape
    └── workflows.md         # recipes, result interpretation, OMP troubleshooting
```

**Install for OMP** — copy the skill directory into the user skills root, or point `skills.customDirectories` at this repository's `skills/` directory in OMP's config:

```bash
cp -r skills/agent-pattern-mcp ~/.omp/agent/skills/
```

The skill then tells the agent:

- Which entry point fits OMP's deadline: the async job trio by default, one-shot `design_agent_system` only after raising the server's `timeout` (every LLM tool aborts under the 30 s default — `submit_agent_design_job` answers in ~0.05 s)
- That `analyze_agent_system` is the analysis-only path for coding agents that write the code themselves — topology, scored patterns, quality metrics, no design generated — while `design_agent_system` is for callers that want the design artifact
- How to phrase `requirements`, `domain`, and `topology` as separate structured arguments
- How to interpret `final_quality_score`, `attempts > 1`, and `evaluation.recommendations`
- That `read mcp://pattern://…` is ambiguous while the sibling `architecture-pattern` server is connected, so the tool route (`get_agent_pattern`) is authoritative

The tool schemas, error codes and design-dict shape in `references/` are client-agnostic; only the deadline/device guidance is OMP-specific.

---

## 🧪 Use the Tools

All tools accept `requirements` (free text) and `domain` (e.g. `tool-use-tasks`, `data-processing`, `customer-support`) as arguments. The examples below show the exact tool call shape so you can use them in any MCP client or API consumer.

### Design your first agent system

In Claude Code (or any MCP client), paste the natural-language instruction:

```
Build a research assistant agent that answers multi-hop questions by combining
web search results with sandboxed Python computation, iterating until it can
synthesise a final cited answer.
```

Your agent calls `design_agent_system` internally. The server returns a full agent system design: agents (planner, searcher, coder, synthesizer), quality attribute scores (reliability: 8.0, output_quality: 8.5, …), and specific recommendations.

That is the **design path**: the server's LLM generates the design artifact for you, which is why a call takes minutes. If your agent writes the implementation itself and only needs the pattern expertise, call `analyze_agent_system` instead — it returns the recommended topology, the selected patterns with scores, `quality_metrics` (per-attribute 0–10), and matched domains **without** generating a design, so the generate and evaluate phases never run. Measured basis: a single live `analyze_agent_system` call on this host returned in 23.3 s, while the committed full-pipeline corpus measured p50 ≈ 304 s and p95 ≈ 375 s over 20 scenarios (`benchmarks/base/summary.json`).

**Or call tools directly** from your agent:

```
Call analyze_agent_system with:
  requirements: "Research assistant combining web search with sandboxed code execution for multi-hop questions"
  domain: "tool-use-tasks"

Call generate_agent_system with:
  requirements: "Research assistant: decompose into sub-questions, search or code per sub-question, synthesise cited answer"
  domain: "tool-use-tasks"
  selected_patterns: ["react"]

Call evaluate_agent_system with:
  agent_system: { ... paste a design dict here ... }
  criteria: "reliability, safety"

Call list_agent_patterns()  # all 68 patterns
Call list_agent_patterns(category="multi_agent")  # filter by category
Call get_agent_pattern(name="supervisor-worker")   # full pattern JSON
```

### Async job pattern: `submit_agent_design_job` + `get_agent_design_status`

ONLY for clients with short request timeouts (Cursor, Claude Desktop, TS-SDK). The default design path is `design_agent_system` with heartbeat defence. `submit_agent_design_job` returns a `job_id` immediately; poll `get_agent_design_status` until done:

```
# Step 1: start the job
Call submit_agent_design_job with:
  requirements: "Research assistant combining web search with sandboxed code execution for multi-hop questions"
  domain: "tool-use-tasks"

# Step 2: poll every 10-30 seconds
Call get_agent_design_status with:
  job_id: "<job_id from step 1>"

# → status is "pending" | "running" | "completed" | "failed" | "cancelled"
# When status is "completed", the full design is in result.design
# When status is "failed", the error is in result.error
```

In Python (via the MCP HTTP API directly — see `examples/agent_client_async.py`):

```python
import asyncio
from fastmcp import Client

SERVER = "http://localhost:8821/mcp"
POLL_EVERY = 15  # seconds

async def main():
    async with Client(SERVER) as client:
        # Start
        started = await client.call_tool("submit_agent_design_job", {
            "requirements": "Research assistant: web search + sandboxed code for multi-hop questions",
            "domain": "tool-use-tasks",
        })
        job_id = started.data["job_id"]
        print(f"Job started: {job_id}")

        # Poll
        while True:
            await asyncio.sleep(POLL_EVERY)
            status = await client.call_tool("get_agent_design_status", {"job_id": job_id})
            data = status.data
            print(f"  status={data['status']}  message={data['message']}")
            if data["status"] in ("completed", "failed", "cancelled"):
                break

        print(data.get("result", data))  # full design when completed
```

See `examples/agent_client_async.py` for the complete runnable example. Run it with:

```bash
docker compose -f docker/docker-compose.yml up --build   # Terminal 1
make client-async                                      # Terminal 2
```

### Explore the pattern catalog

```
Call list_agent_patterns() with no filters to see all patterns.
```

Or get details on a specific pattern:

```
Show me details about the react agent pattern.
```

---

## 🛠️ Tools at a Glance

| Tool | Description |
|---|---|
| `analyze_agent_system` | **Analysis-only path for agents that write the code themselves**: requirements + domain → recommended topology, selected patterns with scores, quality metrics (per-attribute 0–10), matched domains. Generates no design. *One LLM call (23 s measured). Not idempotent.* |
| `generate_agent_system` | Generate an agent system design from requirements and selected patterns. *Long-running (LLM call). Not idempotent.* |
| `evaluate_agent_system` | Score an existing design against quality attributes. *Long-running (LLM call). Not idempotent.* |
| `design_agent_system` | **Design path**: full pipeline (analyse → generate → evaluate → refine, up to 3 attempts) → agents, relationships, tool contracts, state models, plus evaluation. *Long-running (5–10 min); use this when the caller wants the design artifact, or the job trio if the client has a short request timeout.* |
| `submit_agent_design_job` | Start a background design job and return a `job_id` immediately. **ONLY for clients with short request timeouts** (Cursor, Claude Desktop, TS-SDK). For other clients use `design_agent_system`. Poll `get_agent_design_status` every 10–30 s. |
| `get_agent_design_status` | Poll job status. Returns the current status, progress message, and the full design output when `completed`. |
| `cancel_agent_design` | Cancel a running job (best-effort; takes effect at the next pipeline stage boundary; may take up to one LLM call). |
| `list_agent_patterns` | List all 68 patterns; filter by `category` and/or `domain` |
| `get_agent_pattern` | Get full JSON for a specific pattern by name |


**Domain and Topology are structured parameters** — pass them as separate tool arguments, not embedded in the requirements text.

Example prompts:

```
Build a research assistant that answers multi-hop questions by combining
web search with sandboxed code execution, with full audit logging.
```

```
Design an agent system for customer-support automation handling 1M
conversations/day. Domain: customer-support. Topology: hierarchical.
```

```
Show me details about the reflexion pattern.
```

```
Call design_agent_system with:
  requirements: "Research assistant combining web search with sandboxed code execution for multi-hop questions"
  domain: "tool-use-tasks"
```

---

## 💬 Prompts

This server also exposes four user-invoked workflow prompts (slash commands
in MCP clients). Unlike tools, the LLM does not autonomously invoke prompts —
the user selects one and fills in its arguments. Each prompt encodes a tested
tool-orchestration recipe.

| Prompt | Args | What it does |
|---|---|---|
| `/design_agent_system_workflow` | requirements\* | Full analyze → generate → evaluate pipeline |
| `/explore_pattern_catalog` | `domain`, `category` | Live catalog discovery with embedded pattern names |
| `/evaluate_my_agent_system` | `focus` | Guide evaluation criteria + finding prioritisation |
| `/compare_agent_topologies` | topology_a\*, topology_b\*, requirements\* | Two designs side-by-side; ~2× token cost |

\* = required argument

### Tool-only clients

Clients that only support the tools protocol (no native `prompts/list` or `prompts/get`) can access all four workflow prompts via the generated `list_prompts` and `get_prompt` tools, which route through the server's middleware chain exactly as native prompt calls do.

---

## 📖 Pattern Catalog

### Via MCP tools (recommended — works in all clients)

```
list_agent_patterns()                                  # all 68 patterns
list_agent_patterns(category="multi_agent")            # filter by category
list_agent_patterns(domain="tool-use-tasks")           # filter by domain
get_agent_pattern(name="supervisor-worker")            # full pattern JSON
```

Valid `category` values: `reasoning`, `tool_use`, `planning`, `reflection`, `research_synthesis`, `multi_agent`, `memory`, `retrieval`, `safety_control`, `observability`.

### Via MCP resources

```
pattern://                    → list of all patterns
pattern://{name}              → full pattern JSON
template://{name}             → curated design templates (react, supervisor-worker, multi-agent-debate, agentic-rag)
component://{type}            → component blueprints derived from pattern data
```

> **Note:** on hosts where the sibling `architecture-pattern-mcp` server is also connected, `pattern://{name}` is ambiguous (both servers register the scheme) — the tool route (`get_agent_pattern`) is authoritative.

### Pattern JSON structure

Each pattern includes: `name`, `category`, `topology`, `context`, `benefits`, `tradeoffs`, `quality_attributes` (reliability/cost_efficiency/latency/output_quality/observability/safety/simplicity, numeric scores), `suitable_domains`, `component_types`, `technology_stack`, `design_principles`, `best_practices`.

Required fields: `name`, `context`, `category`, `topology`, `suitable_domains`, `quality_attributes` (all 7 keys).

---

## Install Alternatives

### Docker (manual)

```bash
# Build the image
make docker-build

# Run with your API key
MINIMAXAI_API_KEY=your_key docker compose -f docker/docker-compose.yml up -d
```

### Local Development (uv)

**Prerequisites:** Python 3.12+, [uv](https://github.com/astral-sh/uv)

```bash
# Install
make install

# Configure
cp config/config.json ~/.config/agent-pattern-mcp/config.json
# Edit ~/.config/agent-pattern-mcp/config.json and set your GENERATOR_API_KEY

# Run the server
uv run python -m src.main --transport stdio              # for Claude Code / Codex
uv run python -m src.main --port 8050                    # for OpenCode (HTTP, default)
```

Or use the installed console script (after `make install`):

```bash
agent-pattern-mcp --transport stdio
```

The TEI embedder (Qwen3-Embedding-0.6B) is required for domain-scoped pattern retrieval. Without it, the server falls back to the default pattern. Docker compose starts it automatically; local users must run it separately on port 8080.

The retrieval legs are built at server startup: BM25 always, the FAISS dense leg from the [embedding-index cache](#embedding-index-cache-dense-retrieval-snapshot) when a valid snapshot exists (otherwise embedded from scratch). Startup stays fail-fast — every start makes one probe embedding call, so a misconfigured or unreachable TEI sidecar aborts warmup rather than breaking the user's first design request. Docker compose's `service_healthy` dependency ordering guarantees TEI is ready before the app starts.

> **TEI startup:** both sidecar images (`docker/Dockerfile.tei-embed`, `docker/Dockerfile.tei-rerank`) ship a self-built TEI router (v1.9.4 + unmerged [PR #884](https://github.com/huggingface/text-embeddings-inference/pull/884)) with `WARMUP_TOKENS=0` by default — this skips the synthetic warmup pass (measured ~131 s embed / ~78 s rerank) so containers become ready after weight load only. Override per sidecar via `TEI_WARMUP_TOKENS` / `TEI_RERANK_WARMUP_TOKENS` (positive N warms with N tokens instead; values > `MAX_BATCH_TOKENS` are rejected at startup).

**GPU TEI:** the shipped sidecars are CPU images (`FROM ghcr.io/huggingface/text-embeddings-inference:cpu-1.9`, ORT backend — batch cap 8 for this model) and the Stage-0 router is built CPU-only (`--features ort,http`). This repo ships **no GPU build path** — running on CUDA would require changing the runtime base image to `:cuda-1.9` *and* rebuilding the router with the CUDA feature set, which is not a supported recipe here (only `design-pattern-mcp-local` ships one: `make docker-build-tei-embed-gpu`). A stock upstream TEI image without [PR #884](https://github.com/huggingface/text-embeddings-inference/pull/884) silently ignores `WARMUP_TOKENS`.

**Already-running embedder/reranker:** when embedding and reranking endpoints already run on other servers, point the MCP server at them and skip the sidecars (`docker/docker-compose.hub.yml` starts the MCP server only and wires exactly this). The remote embedder must be TEI serving the same model — keep `EMBEDDER_PROVIDER=tei` and set `EMBEDDER_BASE_URL` to its OpenAI-compatible route (`http://<host>:8080/v1`, the `config.json` default). This server's embedder config has **no `model` field** (`src/patterns/embedder.py::build_embedder` sends an empty model name for the non-`tei` providers), so `openai` / `ollama` / `vllm` / `hosted_vllm` cannot address an arbitrary remote model without a code change. The reranker is **not** a LiteLLM client — it POSTs `{RERANKER_BASE_URL}/rerank` directly (default `http://pattern-tei-rerank:8080`, no `/v1`); provider/model syntax in the [LiteLLM embedding docs](https://docs.litellm.ai/docs/embedding/supported_embedding) applies to the embedder only. `EMBEDDER_API_KEY` is forwarded as the LiteLLM `api_key` (any non-empty string satisfies a no-auth TEI).

---

## Configuration

### config.json

The server reads `~/.config/agent-pattern-mcp/config.json` (override with `--config-path`):

```json
{
  "generator": {
    "provider": "openai",
    "config": {
      "model": "gpt-4o-mini",
      "base_url": "https://api.openai.com/v1",
      "api_key": "{env:GENERATOR_API_KEY}",
      "temperature": 0.1,
      "top_p": 1.0,
      "top_k": 20
    }
  },
  "embedder": {
    "provider": "tei",
    "config": {
      "base_url": "http://pattern-tei-embed:8080/v1"
    }
  },
  "retrieval": {
    "bm25_top_k": 0,
    "dense_top_k": 0,
    "top_k_patterns": 5,
    "min_quality_score": 50.0
  },
  "pattern_directory": "~/.config/agent-pattern-mcp/pattern",
  "transport": "streamable-http",
  "host": "0.0.0.0",
  "port": 8050,
  "logging_level": "INFO",
  "logging_format": "json"
}
```

`{env:VAR:-default}` syntax expands environment variables at load time.

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

| Variable | Default | Description |
|---|---|---|
| `GENERATOR_API_KEY` | *(required)* | API key for your LLM provider (passed to LiteLLM as `api_key`) |
| `GENERATOR_PROVIDER` | `openai` | LiteLLM provider prefix: `openai`, `anthropic`, `openrouter`, … — see [LiteLLM Providers](https://docs.litellm.ai/docs/providers) |
| `GENERATOR_BASE_URL` | `https://api.openai.com/v1` | API base URL (passed to LiteLLM as `api_base`) |
| `GENERATOR_MODEL` | `gpt-4o-mini` | Model name; final model string is `<GENERATOR_PROVIDER>/<GENERATOR_MODEL>` (LiteLLM syntax) |
| `GENERATOR_TEMPERATURE` | `0.1` | Sampling temperature |
| `GENERATOR_TOP_P` | `1.0` | Top-p sampling |
| `GENERATOR_TOP_K` | `20` | Top-k sampling |
| `GENERATOR_STREAM` | `false` | Enable streaming responses |
| `EMBEDDER_PROVIDER` | `tei` | Embedder provider |
| `EMBEDDER_BASE_URL` | `http://pattern-tei-embed:8080/v1` | TEI embedder URL |
| `EMBEDDER_BATCH_SIZE` | `16` | Embedding batch size |
| `EMBEDDER_QUERY_INSTRUCTION` | *(empty)* | Query instruction prefix |
| `EMBEDDER_TEXT_INSTRUCTION` | *(empty)* | Text instruction prefix |
| `EMBEDDING_CACHE` | image: `/var/cache/agent-pattern-mcp/embedding-index` · host: `~/.config/agent-pattern-mcp/embedding-index` | Dense-leg snapshot path: reloaded on restart (zero corpus re-embedding), rebuilt on any embedder/corpus/probe change. `0`/`false`/`off`/`no` disables. See [Embedding-index cache](#embedding-index-cache-dense-retrieval-snapshot) |
| `RETRIEVAL_BM25_TOP_K` | `0` | BM25 stage-1 recall cap (0=full corpus) |
| `RETRIEVAL_DENSE_TOP_K` | `0` | Dense stage-1 recall cap (0=full corpus) |
| `RETRIEVAL_DENSE_WEIGHT` | `0.7` | Stage-1 fusion leg weight on the dense leg. Pairs with `RETRIEVAL_BM25_WEIGHT`; both must be > 0 and sum to 1.0. |
| `RETRIEVAL_BM25_WEIGHT` | `0.3` | Stage-1 fusion leg weight on the BM25 leg. See `RETRIEVAL_DENSE_WEIGHT`. |
| `RETRIEVAL_TOP_K_PATTERNS` | `5` | Number of patterns to select |
| `RETRIEVAL_MIN_FUSION_SCORE` | `0.0` | Relevance floor on the rank_fusion blend value. Default 0.0 (gate disabled). |
| `RETRIEVAL_RERANK_TOP_N` | `10` | Rerank top N (slug-cut after CE) |
| `RETRIEVAL_USE_LEAN_WIRE_SCHEMA` | `false` | Use lean response schema (omits free-form contract lists; the dev/systemd compose files default this to `true` for the MiniMax generator) |
| `RETRIEVAL_TOPOLOGY_SCORE_THRESHOLD` | `50.0` | Min analysis score for topology recommendation |
| `REASONING_ENABLED` | `true` | Server-side reasoning MCP integration — **on by default** (see [Structured Reasoning](#structured-reasoning-shannonthinking--code-reasoning)) |
| `REASONING_SPAWN_TIMEOUT_SECONDS` | `10` | Subprocess spawn timeout per reasoning tool |
| `REASONING_STEP_TIMEOUT_SECONDS` | `20` | Per-thought tool-call timeout |
| `REASONING_MAX_TOTAL_STEPS` | `8` | Hard cap on reasoning steps per phase |
| `REASONING_QUIET_STDERR` | `true` | Silence reasoning-subprocess stderr (ASCII progress boxes, `[info]` banners); set `false` to debug spawn failures |
| `REASONING_FAIL_FAST` | `true` | Fail server startup when a reasoning tool is unreachable |
| `REASONING_SHANNONTHINKING_CMD` | *(embedded)* | JSON list command for shannonthinking (e.g. `["npx","-y","server-shannon-thinking@latest"]`) |
| `REASONING_CODE_REASONING_CMD` | *(embedded)* | JSON list command for code-reasoning |
| `RETRIEVAL_ANALYSIS_BLEND_WEIGHT` | `0.7` | Weight on analysis score in blend |
| `RETRIEVAL_FUSION_BLEND_WEIGHT` | `0.3` | Weight on fusion score in blend |
| `RETRIEVAL_WEIGHT_SMOOTHING_ALPHA` | `0.7` | Weight smoothing alpha |
| `PIPELINE_TIMEOUT_SECONDS` | `1200` | Wall-clock budget (seconds) for one complete design run — all phases (analyze → generate → evaluate → refine) and every retry attempt. On expiry the run is cancelled and the tool call fails with `WorkflowTimeoutError`; the partial design is discarded. Raise it when `REASONING_ENABLED=true` on a slow provider, lower it to fail fast. Config key: `pipeline.timeout_seconds`. |
| `RETRIEVAL_VERBOSE_TIMING` | `false` | Log phase timings at INFO level |
| `RETRIEVAL_MAX_TRIES` | `2` | Max design loop attempts |
| `RETRIEVAL_MIN_QUALITY_SCORE` | `50.0` | Early-stop quality threshold |
| `RERANKER_BASE_URL` | `http://pattern-tei-rerank:8080` | TEI reranker endpoint |
| `RERANKER_TIMEOUT` | `30.0` | Reranker timeout (seconds) |
| `RERANKER_MAX_BATCH_SIZE` | `48` | Max texts per TEI /rerank request; must be ≤ min(MAX_CLIENT_BATCH_SIZE, MAX_CONCURRENT_REQUESTS) of the reranker sidecar. HybridPatternRetriever chunks large pools automatically. |
| `PATTERN_DIRECTORY` | `~/.config/agent-pattern-mcp/pattern` | Pattern files directory |
| `VALIDATION_MAX_RETRIES` | `2` | Max self-healing retry attempts |
| `VALIDATION_RETRY_ON_FAIL` | `true` | Retry on validation failure |
| `AGENT_PATTERN_JOBS_DB` | `~/.config/agent-pattern-mcp/jobs.db` | SQLite path for async job trio. Override for test isolation |
| `TASKS_HEARTBEAT_ENABLED` | `true` | Emit progress notifications during long tool calls |
| `TASKS_HEARTBEAT_INTERVAL_SECONDS` | `30` | Heartbeat interval in seconds (keep below client idle timeout) |
| `TRANSPORT` | `streamable-http` | Transport mode: `stdio`, `streamable-http` |
| `HOST` | `0.0.0.0` | HTTP bind host |
| `PORT` | `8050` | HTTP bind port (in-container; the dev compose publishes host port 8821, systemd publishes 8811) |
| `LOGGING_LEVEL` | `INFO` | Logging level |
| `LOGGING_FORMAT` | `json` | Logging format: `json`, `text` |
| `CONFIG_PATH` | `~/.config/agent-pattern-mcp/config.json` | Config file path |

> **Note:** the dev and systemd compose files set `RETRIEVAL_BM25_TOP_K=20` / `RETRIEVAL_DENSE_TOP_K=20` (per-leg stage-1 caps) and `RETRIEVAL_MIN_FUSION_SCORE=0.015`, overriding the config defaults above. The deployed MiniMax generator block (`GENERATOR_PROVIDER=minimax`, `GENERATOR_MODEL=minimax/MiniMax-M2.7`, `GENERATOR_BASE_URL=https://api.minimax.io/v1`, `RETRIEVAL_USE_LEAN_WIRE_SCHEMA=true`) also differs from the OpenAI config defaults.

### Embedding-index cache (dense retrieval snapshot)

The dense retrieval leg is one FAISS index over every catalogue domain slug
(36 on the shipped 68-pattern catalogue). Its embeddings are snapshotted to
disk after a cold build and reloaded on the next start, so a warm start costs
one probe embedding instead of a full corpus pass (measured on a dev TEI
sidecar container, 36 slugs: 3.3 s → 0.28 s). BM25 is cheap and rebuilt every
start.

- **Path**: `EMBEDDING_CACHE`. The image bakes
  `/var/cache/agent-pattern-mcp/embedding-index`; host runs (`uv`) use
  `~/.config/agent-pattern-mcp/embedding-index`.
- **Where the files live**: the logged path is the *in-container* view. Docker
  stores the named volume at `/var/lib/docker/volumes/<volume-name>/_data`
  (root-owned), so `/var/cache` on the host stays empty by design. Inspect
  without sudo: `docker exec <container> ls
  /var/cache/agent-pattern-mcp/embedding-index`, or
  `docker volume inspect -f '{{.Mountpoint}}' <volume-name>` for the host side.
- **Containers persist it in a named volume**
  (`agent-pattern-mcp-dev-embedding-index` /
  `agent-pattern-mcp-systemd-embedding-index`), so the snapshot survives
  image rebuilds, container recreation and `docker compose down`. Reset it with
  `docker compose down -v` or `docker volume rm <name>`; a bare `docker run`
  needs `-v agent-pattern-mcp-embedding-index:/var/cache/agent-pattern-mcp/embedding-index`.
- **Rebuilt automatically** when the embedding function changes (provider,
  `base_url`, resolved model name, query/text instruction prefixes), when the slug
  corpus changes, or when a probe vector shows a *different model behind an
  unchanged config* (e.g. a redeployed TEI sidecar). Log lines:
  `Embedding index cache hit: N slugs, 0 corpus embed calls (snapshot
  <cache-dir>)` / `Embedding index cache miss (<reason>); embedding corpus` /
  `Embedding index snapshot written: N slugs (path <cache-dir>)` — emitted
  immediately after the embedding pass, before any other startup step — and,
  with the cache switched off, `Embedding index cache disabled; embedding corpus`
  (never reported as a miss).
- **Single writer**: no locking — run one server process per cache directory.
  A failed snapshot write only logs a warning; the server runs cacheless and
  never fails the start.
- Operations notes (volumes, permissions, disable switch): [INSTALL.md](INSTALL.md#embedding-index-cache).

### CLI flags

| Flag | Description |
|---|---|
| `--transport {stdio,streamable-http}` | Override transport mode |
| `--host` | Override HTTP bind host (default: 0.0.0.0) |
| `--port` | Override HTTP port (default: 8050) |
| `--config-path` | Path to config file |
| `--health` | Run health check and exit |

---

## Structured Reasoning (shannonthinking / code-reasoning)

Before each LLM phase call (ANALYZE / GENERATE / EVALUATE / RETRY), the server
optionally runs a bounded **ThoughtGenerator loop**: it authors each reasoning
step with the generator's own LLM (LlamaIndex LiteLLM; one completion per
step) and submits it to the
[shannonthinking](https://github.com/olaservo/shannon-thinking) and/or
[code-reasoning](https://github.com/mettamatt/code-reasoning) MCP servers —
structured thinking scratchpads that validate, number, and record each step.
The resulting trace is injected into the phase prompt as a
`<reasoning_context>` block. Contract: **each thought = 1 LLM completion + 1
MCP tool call**, capped by `REASONING_MAX_TOTAL_STEPS` (default 8).

Key properties:

- **Embedded in Docker** — the `build-mcps` stage bakes both npm packages
  (`server-shannon-thinking@0.1.1`, `@mettamatt/code-reasoning@0.8.1`) into
  the image at `/usr/local/lib/node_modules/...`; the runtime invokes them
  directly via `node` (no network, no npx).
- **Auto-fallback to npx** outside Docker — when the embedded entry points
  are missing, the client falls back to `npx -y <pkg>` (first call downloads).
- **Process-per-call isolation** — each tool call runs in a fresh subprocess
  (`keep_alive=False`); nothing persists between calls.
- **Silent per-call degradation** — any spawn/timeout/tool failure logs a
  WARNING and the phase proceeds with a degraded in-prompt thinking scaffold
  (decompose → classify → calibrate → resolve → verify); it never raises.
- **Loud startup** — the lifespan health-check probes both tools and logs an
  ERROR (with resolution hints) if one is unreachable; set
  `REASONING_FAIL_FAST=true` to make startup fail instead.
- **Trace caching** — ANALYZE and GENERATE traces are computed once per
  design request and reused across design-loop attempts.

### Opting in / tuning

Reasoning is **enabled by default** in this repo's deployed stacks (both compose files set `REASONING_ENABLED=true`):

```bash
export REASONING_ENABLED=true           # enable the reasoning MCP integration
export REASONING_FAIL_FAST=true         # refuse to start with broken MCPs
```

Per-phase tool selection (defaults in `src/reasoning/config.py::_default_per_phase`):
analyze `["code", "shannon"]` × 4 thoughts, generate `["code"]` × 3,
evaluate `["shannon"]` × 3, refine `["code", "shannon"]` × 2.
A full design run issues up to 24 reasoning tool calls as serial subprocesses —
minutes, not seconds.

Local (non-Docker) development needs Node.js; either install the packages
globally (`npm install -g server-shannon-thinking @mettamatt/code-reasoning`)
or let the npx fallback download them on first use.

Set `LOGGING_LEVEL=DEBUG` to capture the authored `thought` and tool response
for every per-step reasoning call. Docker/systemd stacks default to INFO;
export `LOGGING_LEVEL=DEBUG` before `make docker-up`.

---

## Extending with Custom Patterns

Pattern files are loaded from `~/.config/agent-pattern-mcp/pattern/` (configurable via `PATTERN_DIRECTORY`). Drop a JSON file alongside the 68 built-in patterns.

**Minimal pattern structure:**

```json
{
  "category": "tool_use",
  "name": "my-custom-pattern",
  "topology": "single-agent-loop",
  "context": "Describe when this pattern applies.",
  "benefits": ["Benefit 1", "Benefit 2"],
  "tradeoffs": ["Tradeoff 1"],
  "quality_attributes": {
    "reliability": 7,
    "cost_efficiency": 6,
    "latency": 7,
    "output_quality": 7,
    "observability": 6,
    "safety": 7,
    "simplicity": 5
  },
  "suitable_domains": ["tool-use-tasks"]
}
```

Required fields: `name`, `context`, `category`, `topology`, `suitable_domains`, `quality_attributes` (all 7 keys).

Valid `category` values: `reasoning`, `tool_use`, `planning`, `reflection`, `research_synthesis`, `multi_agent`, `memory`, `retrieval`, `safety_control`, `observability`.

Full JSON Schema with all enums: `docs/pattern-schema.json`

---

## Long-running tools & timeouts

`design_agent_system` runs a multi-stage LLM pipeline that **can take 5–10 minutes per call**. The single-phase tools are much cheaper: `analyze_agent_system` is one analysis LLM call (23.3 s measured on this host) that returns topology and scored patterns without generating a design, while `generate_agent_system` and `evaluate_agent_system` are one large completion each. The long design call is inherent to the workload, not a bug: the generator LLM must process a large input payload — the selected pattern definitions from the 68-pattern catalog, your requirements, and the full output of every previous stage — and produce a large, strictly structured JSON document (agents, relationships, tool contracts, state models, message contracts, quality scores) one token at a time. The `design_agent_system` pipeline repeats generate → evaluate up to three times, so a single call can comprise 9+ LLM round trips.

### The timeout problem

MCP clients (AI coding agents, MCP SDKs) sit between the server and the LLM. Many of them implement a **client-side idle timeout**: if no data is received on the HTTP connection for some period (typically 30–120 seconds), the client aborts the request. The server is still working — the LLM is still generating — but the client closes the connection and reports a timeout error to the agent.

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
get_agent_design_status(job_id)                                     → {status, result, error}
cancel_agent_design(job_id)                                         → {cancelled, status}
```

`submit_agent_design_job` returns a `job_id` in milliseconds. The pipeline runs in a background task. Poll `get_agent_design_status(job_id)` every 10–30 seconds. When status is `completed`, the full design is in the `result` field. Cancellation is best-effort — the job exits at the next pipeline stage boundary.

**This is the only fix that works for TS-SDK clients (Claude Desktop, Cursor).**

The job store is SQLite at `~/.config/agent-pattern-mcp/jobs.db` (configurable via `AGENT_PATTERN_JOBS_DB`).

### Bypassing client timeouts entirely: `make client`

The example client in `examples/agent_client.py` is a **direct Python HTTP client** — it is not an MCP agent. It calls the server over HTTP without any MCP SDK, and therefore has **no client-side idle timeout**. It makes a single blocking request and waits for the full response, regardless of how long it takes.

```bash
# Start the server (from project root)
docker compose -f docker/docker-compose.yml up --build

# In another terminal, run the example client
make client
```

`make client` is a development/demo tool. It demonstrates that the server **correctly completes** long requests — the timeout issue is purely a client-side problem. For production use with MCP agents, the heartbeat defence covers the majority of clients; the async job trio is the universal fallback.

---

## Troubleshooting

### Server starts but tools are not visible

1. Check the agent's MCP connection: Claude Code `/mcp`, OpenCode `opencode mcp list`, Codex `codex mcp list`
2. Verify the server process started: compose logs should show `MCPAgentPatternServer initialized`
3. Confirm the TEI embedder is healthy: `docker exec agent-pattern-mcp python -c "import urllib.request; print(urllib.request.urlopen('http://pattern-tei-embed:8080/health').status)"`

### "Connection refused" or timeout errors

The server waits for the TEI embedder to become healthy:

```bash
docker compose -f docker/docker-compose.yml logs agent-pattern-mcp
```

### LLM provider errors (502 / 401)

- Confirm `GENERATOR_API_KEY` is set and not expired
- Verify `GENERATOR_BASE_URL` matches your provider's endpoint
- If using a proxy, check reachability from inside the container

### Pattern JSON files not loading

- Files must have `.json` extension and match `*-pattern.json`
- Required fields: `name`, `context`, `category`, `topology`, `suitable_domains`, `quality_attributes` (all 7 keys)
- Check the startup log for `Pattern validation failed` warnings

---

## Building & Development

**Common make targets** (full reference: [docs/make_rules.md](docs/make_rules.md)):

| Target | Description |
|---|---|
| `make install` | Install package in editable mode with dev dependencies |
| `make check-lint` | Run ruff linting |
| `make check-static-typing` | Run mypy --strict type checking on src/ |
| `make check-all` | Run every check-* quality gate (lint, types, dead code, deps) |
| `make test-unit` | Run unit tests with uv (tests/unit/) |
| `make test-oracles` | Run executable verification oracles (tests/verification/) |
| `make client` | Run the example MCP client demo (requires server running) |
| `make client-async` | Run the async job trio demo (requires server running) |
| `make docker-build` | Build the MCP server Docker image |
| `make docker-build-all` | Build MCP server + TEI embedder + reranker images |
| `make docker-publish` | Push image to Docker Hub + GHCR (version + latest) |
| `make docker-up` | Build and start all services |
| `make docker-down` | Stop all services |

**Development workflow:**

```bash
make install                      # First-time setup
uv run pre-commit install         # First-time setup: commit hook
make check-all                    # Before pushing (lint + types + dead code + deps)
make docker-build-all             # Build both images (first time and after code changes)
make docker-up                    # Start services
make docker-logs-follow           # Watch logs
make docker-down                  # Stop
```

---

## Publishing

All three images are published to two registries simultaneously:

| Image | Docker Hub | GHCR | Tags |
|---|---|---|---|
| MCP server | `olkowa/agent-pattern-mcp` | `ghcr.io/olk/agent-pattern-mcp` | `$(DOCKER_TAG)`, `latest` |
| TEI embedder | `olkowa/pattern-tei-embed` | `ghcr.io/olk/pattern-tei-embed` | `$(DOCKER_TAG)`, `latest` |
| TEI reranker | `olkowa/pattern-tei-rerank` | `ghcr.io/olk/pattern-tei-rerank` | `$(DOCKER_TAG)`, `latest` |

All three images share the same `$(DOCKER_TAG)` (the version from `pyproject.toml`), so `tei:1.0.3` always ships with `mcp:1.0.3`. Blob deduplication keeps re-tagging unchanged TEI images cheap.

> **Bandwidth note:** the TEI embedder image is ~5 GB (ONNX fp32 weights baked in). First push to each registry is ~5 GB upload. Subsequent pushes are incremental — only changed layers are transferred.

### Prerequisites

**Docker Hub** — already authenticated locally (`docker login`).

**GitHub Container Registry** — requires a [classic PAT](https://github.com/settings/tokens/new?scopes=write:packages) with `write:packages` scope. 2FA is not an issue — PATs bypass it. After login the token is discarded; the credential persists in `~/.docker/config.json` until you log out.

### Publish (one-time setup + per-session)

```bash
# 1. Login to GHCR (interactive — paste token at the password prompt)
docker login ghcr.io -u olk

# 2. Build and push all three images (MCP + TEI embedder + TEI reranker)
#    The umbrella target builds the MCP image, tags it, pushes it, creates the git tag,
#    then builds and pushes each TEI image in sequence.
make docker-publish-all

# 3. Logout from GHCR immediately after publishing
#    (removes the ghcr.io credential from ~/.docker/config.json)
docker logout ghcr.io
```

On subsequent publishes repeat steps 1–3. If your PAT has expired, generate a new one at the link above.

### First push — set packages public (GHCR only)

GHCR packages default to **private**. After the first `make docker-publish-all`, flip all three packages to public:

| Package | Settings URL |
|---|---|
| MCP server | `https://github.com/users/olk/packages/container/agent-pattern-mcp/settings` |
| TEI embedder | `https://github.com/users/olk/packages/container/pattern-tei-embed/settings` |
| TEI reranker | `https://github.com/users/olk/packages/container/pattern-tei-rerank/settings` |

Set each to **Public** and save.

### Partial failure recovery

If the push fails mid-way (e.g., GHCR auth was not configured), Docker Hub layers are already uploaded. After fixing auth, re-running `make docker-publish-all` is safe — each registry reports a cache hit for already-uploaded layers and completes the remaining push. For targeted retries, individual images can be pushed with `make docker-publish-tei` or `make docker-publish-tei-rerank`.

---

## systemd Service (Linux)

The server can run as a systemd service on any systemd-based Linux host. It
starts the Docker Compose stack automatically at boot.

### File layout

The `systemd/` directory contains three files:

| File | Purpose |
|---|---|
| `systemd/agent-pattern-mcp.service` | The systemd unit |
| `systemd/docker-compose.yml` | Production compose variant (no `build:`, absolute paths) |
| `systemd/README.md` | Full runbook with install, verify, and troubleshooting |

The production compose file is a deployment variant of `docker/docker-compose.yml`:
it has no `build:` sections (images must be pre-built), uses absolute paths, and
lives under `/etc/agent-pattern-mcp/` on the host. The systemd-managed
project uses the distinct name `agpmcp-systemd` — distinct from both the dev
compose and the sibling `architecture-pattern-mcp` systemd stack
(`apmcp-systemd`), so neither stack's `up -d --remove-orphans` treats the
other's container as an orphan.

> **TEI sidecars are NOT defined in this stack** — the `pattern-tei-embed` embedder
> and `pattern-tei-rerank` reranker containers live in the shared
> [`pattern-tei-infra`](https://github.com/olk/pattern-tei-infra) stack.  This
> stack owns the `pattern-tei-shared` Docker network and exposes the sidecars at
> `http://pattern-tei-embed:8080/v1` (embedder) and `http://pattern-tei-rerank:8080`
> (reranker).  The systemd MCP stack joins that network and reaches them by
> those DNS names.
>
> **Prerequisite — one-time TEI infra setup:**
>
> ```bash
> # Clone the infra stack (if not already on the host)
> git clone https://github.com/olk/pattern-tei-infra.git ~/pattern-tei-infra
>
> # Install and enable the pattern-tei-infra systemd unit
> sudo install -m 644 ~/pattern-tei-infra/pattern-tei-infra.service \
>                 /etc/systemd/system/
> sudo systemctl daemon-reload
> sudo systemctl enable --now pattern-tei-infra.service
> # Wait ~2 min for the TEI sidecars to become healthy
> ```
>
> **Start `agent-pattern-mcp.service` only AFTER** `pattern-tei-infra.service`
> is `active (running)`. See
> [`pattern-tei-infra/README.md`](https://github.com/olk/pattern-tei-infra/README.md)
> for full details.

### Prerequisites

- systemd-based Linux host with Docker (`docker compose version`).
- `<user>` is in the `docker` group.
- Both images pre-built locally (`make docker-build-all` from the repo).
- **Shared TEI infra stack installed and enabled** (see tei-infra README).

### Install

```bash
# 0. Install + enable shared TEI infra (once)
sudo install -m 644 {HOME}/pattern-tei-infra/pattern-tei-infra.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pattern-tei-infra.service

# 1. Build images (once)
make docker-build-all

# 2. Deploy /etc/agent-pattern-mcp/
sudo install -d /etc/agent-pattern-mcp/config
sudo install -m 644 systemd/docker-compose.yml /etc/agent-pattern-mcp/
sudo install -m 644 ~/.config/agent-pattern-mcp/config.json /etc/agent-pattern-mcp/config/

# 3. Create the .env file (root:docker 640) and edit it.
#     640 root:docker — not 600 root:root — so the systemd service
#     running as User=graemer (a member of the `docker` group) can read this
#     file when docker compose auto-loads it.  The `docker` group is
#     effectively privileged; this is the standard trade-off for non-root
#     systemd services that manage Docker containers.
sudo install -o root -g docker -m 640 /dev/null /etc/agent-pattern-mcp/.env
sudo $EDITOR /etc/agent-pattern-mcp/.env
# Contents:
#   MINIMAXAI_API_KEY=sk-...
#   COMPOSE_PROJECT_NAME=agpmcp-systemd

# 4. Install and enable the service.
sudo install -m 644 systemd/agent-pattern-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now agent-pattern-mcp.service
```

> **Prebuilt-image shortcut:** for the no-build install from Docker Hub
> (pull + retag, JSON-RPC probe, day-2 operations), see
> [INSTALL.md](INSTALL.md) Path B instead.

### Verify

`systemctl status` shows `active (exited)` within seconds, but the containers
take **up to ~40 s** to become healthy (MCP `start_period: 40s`; TEI readiness
is owned by `pattern-tei-infra` with `start_period: 120s`).
The unit does not wait for healthchecks.

```bash
systemctl status agent-pattern-mcp
journalctl -u agent-pattern-mcp -n 50
docker compose -p agpmcp-systemd -f /etc/agent-pattern-mcp/docker-compose.yml ps
docker inspect -f '{{.State.Health.Status}}' agent-pattern-mcp  # "healthy"
# Probe the MCP endpoint — must print 200 (GET /health is 404 by design).
curl -s -o /dev/null -w '%{http_code}\n' -X POST "http://localhost:8811/mcp" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"probe","version":"0.0.0"}},"id":1}'
```

### Day-to-day

```bash
sudo systemctl start|stop|restart|reload agent-pattern-mcp
journalctl -u agent-pattern-mcp -n 200 -f
docker compose -p agpmcp-systemd -f /etc/agent-pattern-mcp/docker-compose.yml logs -f
```

### Updating the stack

```bash
make docker-build-all                     # rebuild both images
sudo systemctl reload agent-pattern-mcp   # recreate containers
```

### Uninstall

```bash
sudo systemctl disable --now agent-pattern-mcp.service
sudo rm /etc/systemd/system/agent-pattern-mcp.service
sudo systemctl daemon-reload
sudo rm -rf /etc/agent-pattern-mcp
```

For full troubleshooting, networking details, and the coexistence guide, see
`systemd/README.md`.

---

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

---

## License

MIT License. See [LICENSE](LICENSE).
