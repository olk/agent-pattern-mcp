---
name: agent-pattern-mcp
description: Designs AI agent systems via the agent-pattern MCP server (OMP server name `agent-pattern`). Analyses requirements and domain, selects from 61 patterns (ReAct, reflexion, plan-and-solve, multi-agent debate, supervisor-worker, agentic-RAG and 55 more), generates designs with agents, relationships, tool contracts and state models, and evaluates them across reliability, cost efficiency, latency, output quality, observability and safety. Use when designing a new agent system, comparing agent topologies, evaluating an existing agent design, or exploring the pattern catalog. Triggers on design an agent system for X, compare supervisor-worker vs swarm, evaluate this agent design, choose an agent pattern for X. Do NOT use for implementing individual features, prompt engineering for a single LLM call, or framework selection. Requires the agent-pattern MCP server connected; its synchronous pipeline takes 5-10 minutes, so under OMP's default 30 s MCP deadline use the submit / status / cancel job trio.
---

# agent-pattern MCP

Agent system design pipeline exposed by the `agent-pattern` MCP server:

1. **Analyse** requirements + domain → recommended topology, top-k patterns, quality-attribute weights
2. **Generate** the design: agents (roles, tools, memory), relationships, tool contracts, state models, message contracts
3. **Evaluate** against reliability, cost efficiency, latency, output quality, observability, safety
4. **Refine** — retries generation while `final_quality_score < 50`, up to 3 generate attempts

61 built-in patterns; extra ones can be dropped in as JSON in the server's pattern directory.

## OMP constraints (read first)

### 1. Default entry point is the async job trio, not `design_agent_system`

OMP applies one MCP request deadline, resolved in this order: `OMP_MCP_TIMEOUT_MS` env → the server's `timeout` field (milliseconds) in `~/.omp/agent/mcp.json` → **30 000 ms default**. It is a single timer per request (`src/mcp/timeout.ts`, transports); server progress notifications do **not** extend it. The server's own heartbeat ("emits progress notifications every 30 s so clients stay connected") therefore buys nothing here.

`design_agent_system` runs 5–10 minutes → it aborts under the default deadline. So does every other LLM tool: a single `analyze_agent_system` call was aborted at 30.04 s (OMP reports `MCP failure … failure: timeout … Request timeout after 30000ms`; the outcome is unknown). Those tools have no job variant — they need the raised timeout; only the job trio fits the default deadline. Measured on this host with the default config:

| Call | Device | Latency |
|------|--------|---------|
| `submit_agent_design_job` | `xd://mcp__agent_pattern_submit_agent_design_job` | 0.05 s |
| `get_agent_design_status` | `xd://mcp__agent_pattern_get_agent_design_status` | 0.04 s |
| `cancel_agent_design` | `xd://mcp__agent_pattern_cancel_agent_design` | 0.03 s |

To run the one-shot pipeline instead, raise the deadline for this server — edit `~/.omp/agent/mcp.json`:

```json
"agent-pattern": { "type": "http", "url": "http://localhost:8051/mcp", "timeout": 900000 }
```

`"timeout": 0` disables client-side MCP timeouts for the server. Then `/mcp reload`. A project `.omp/mcp.json` entry shadows the user entry; the user file's `disabledServers`/`enabledServers` win over both.

### 2. Tools are `xd://` devices

```text
write  xd://mcp__agent_pattern_<tool>   JSON args object → tool result
read   xd://mcp__agent_pattern_<tool>   device doc + current input schema
```

Device prefix = server name lowercased with `-` → `_` (`agent-pattern` → `mcp__agent_pattern`). Invalid args echo the schema — fix the JSON and retry, do not switch tools.

### 3. `domain` and `topology` are separate arguments — never embed them in `requirements`

- `requirements` — free text of what the system must do
- `domain` — problem-space tag (`code-generation`, `research-reports`, `customer-support`, …); drives BM25 + dense + cross-encoder pattern retrieval
- `topology` / `override_topology` — orchestration name; `override_topology` (design pipeline) takes precedence over the derived topology. Valid values: `evaluator-loop`, `graph-orchestrated`, `hierarchical`, `parallel-fan-out`, `pipeline`, `plan-execute`, `single-agent-loop`, `swarm`

Retrieval score below the threshold falls back to `single-agent-loop` (the `react` topology) — expected behaviour, not an error.

### 4. Do not read agent patterns through `mcp://pattern://…` on this host

The server advertises `pattern://`, `pattern://{name}`, `template://{name}`, `component://{type}`, and OMP reads MCP resources with `read mcp://<resource-uri>`. But the sibling `architecture-pattern` server registers the same `pattern://{name}` scheme; OMP resolves a resource URI by matching against connected servers and here picked that sibling, so `read mcp://pattern://react` fails (`Pattern not found: react`) while `get_agent_pattern` on the same server succeeds. Use the tool route below for agent patterns.

### 5. Large device results are truncated

`list_agent_patterns` with no filter returns all 61 patterns and is cut off around 10 KB of tool output. Filter by `category` or `domain`, or page with repeated narrow calls — do not assume an unfiltered listing is complete.

## Entry-point decision guide

```text
Existing design to score?
├── YES → evaluate_agent_system (device mcp__agent_pattern_evaluate_agent_system)
└── NO
    ├── Explore the catalog first           → list_agent_patterns (category?/domain?) → get_agent_pattern(name)
    ├── Full design + evaluation              → job trio: submit_agent_design_job → get_agent_design_status
    │                                           (use design_agent_system directly only when the server timeout
    │                                            in ~/.omp/agent/mcp.json is >= 600000 or 0)
    └── Known topology + patterns             → generate_agent_system (skips the analyse leg)
```

## Device quick reference

| Device suffix | Purpose | Latency | Notes |
|---------------|---------|---------|-------|
| `analyze_agent_system` | Topology + pattern recommendations | LLM call | not idempotent |
| `generate_agent_system` | Design from explicit `topology` + `selected_patterns` | LLM call | not idempotent |
| `evaluate_agent_system` | Score an existing design dict | LLM call | read-only server state |
| `design_agent_system` | Full pipeline, one call | 5–10 min | needs a raised MCP timeout |
| `submit_agent_design_job` | Start pipeline, returns `job_id` | < 100 ms | default entry point |
| `get_agent_design_status` | Poll job; `result` when `completed` | < 100 ms | idempotent |
| `cancel_agent_design` | Best-effort cancel at stage boundary | < 100 ms | not idempotent |
| `list_agent_patterns` | Minimal pattern view | fast | idempotent; filter to avoid truncation |
| `get_agent_pattern` | Full pattern JSON by exact name | fast | idempotent |
| `list_prompts`, `get_prompt` | Workflow prompt templates | fast | tool route for prompt clients |

Pattern names carry no `-pattern` suffix: `react`, `chain-of-thought`, `supervisor-worker`, `agentic-rag`. The files on disk are `<name>-pattern.json`. Valid `category` values: `reasoning`, `tool_use`, `planning`, `reflection`, `research_synthesis`, `multi_agent`, `memory`, `retrieval`, `safety_control`, `observability`.

## Job trio recipe

1. **Submit** — `write xd://mcp__agent_pattern_submit_agent_design_job` with `{"requirements": "...", "domain": "...", "override_topology": null}` → `{"job_id": "<uuid>", "status": "pending", "message": "..."}`
2. **Persist the `job_id`.** There is no job list on the server and OMP has no handle registry for it; if the poll loop may outlive the turn, write the id to a scratch file (e.g. `.omp/agent-pattern-job.txt`) before polling.
3. **Poll** — `write xd://mcp__agent_pattern_get_agent_design_status` with `{"job_id": "..."}` every 10–30 s (interleave other work or `bash sleep 15`); branch on `status`:

| Status | Action |
|--------|--------|
| `pending` / `running` | poll again after 10–30 s |
| `completed` | take `result.design` and `result.evaluation` |
| `failed` | report the `error` field |
| `cancelled` | report; offer to resubmit |

4. **Cancel** — `write xd://mcp__agent_pattern_cancel_agent_design` with `{"job_id": "..."}` → `{cancelled, status, task_was_running, message}`. Takes effect at the next cancellation checkpoint; already-terminal jobs cannot be cancelled.

## Interpreting results

- `final_quality_score` (0–100): ≥ 75 strong, 50–74 notable tradeoffs, < 50 triggered automatic regeneration
- `attempts` (1–3): > 1 means the pipeline self-healed — read `evaluation.recommendations` to see what changed
- `evaluation.metrics` per attribute (1–10) plus `evaluation.risks`; treat scores < 70 as findings to fix
- `matched_domains`: retrieval scores; a low top score explains a fallback topology
- `alternative_topologies`: `{pattern_name, topology, score}` runner-ups, deduplicated per topology
- `final_pattern_name` is `""` when the topology was overridden or nothing scored; `is_fallback` marks the `react` fallback

## Prompts (workflow templates)

Interactive OMP sessions expose each server prompt as a slash command named `<server>:<prompt>`, with `key=value` arguments:

```text
/agent-pattern:design_agent_system_workflow requirements="..." domain="research-reports" topology="hierarchical"
/agent-pattern:explore_pattern_catalog domain="exploratory-research" category="research_synthesis"
/agent-pattern:evaluate_my_agent_system focus="safety"
/agent-pattern:compare_agent_topologies topology_a="hierarchical" topology_b="swarm" requirements="..."
```

`/mcp prompts` lists what is connected. Outside the interactive TUI, call the tool route instead: `write xd://mcp__agent_pattern_get_prompt` with `{"name": "design_agent_system_workflow", "arguments": {"requirements": "...", "domain": "..."}}` (arguments: `requirements*`, `domain`, `topology` for the design workflow; `topology_a*`, `topology_b*`, `requirements*` for the comparison — that one costs two `generate_agent_system` calls).

## Reference files

- `skill://agent-pattern-mcp/references/tools.md` — per-tool schemas, exact output fields, error codes, the deadline-failure format, tool annotations, and the design-dict shape
- `skill://agent-pattern-mcp/references/workflows.md` — recipes (job trio, raised-timeout one-shot, catalog → generate, evaluate, prompts), result interpretation, and OMP troubleshooting
