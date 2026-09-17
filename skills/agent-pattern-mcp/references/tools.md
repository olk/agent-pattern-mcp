# Tool reference — agent-pattern MCP server

OMP-native reference for the `agent-pattern` server. The deadline policy that decides
which entry point to use, and the domain/topology vocabulary, live in `SKILL.md`; this
file carries the per-tool parameter and output detail.

## How to call a tool

```text
write  xd://mcp__agent_pattern_<tool>     JSON args object → result
read   xd://mcp__agent_pattern_<tool>     device doc + live input schema
```

- Device names come from the server name lowercased with `-` → `_`; `agent-pattern` owns `mcp__agent_pattern_*`.
- Args and results are JSON. On a schema mismatch the error echoes the schema — fix the JSON and retry the same device.
- Server-side failures surface as `MCP error: <message>` tool text; the codes below identify the class.
- Every call is bounded by OMP's MCP deadline (`OMP_MCP_TIMEOUT_MS` → per-server `timeout` → 30 s). Measured against `http://localhost:8051/mcp` with the default deadline: the job-trio calls return in ≤ 50 ms, while a single LLM tool ran past the deadline and was aborted:

```text
MCP failure
server: agent-pattern
tool: analyze_agent_system
transport: http
stage: receive
failure: timeout
retryable: no
message: Request timeout after 30000ms
next: Check server health or increase the MCP timeout; the request outcome is unknown.
```

  A timeout does not prove the server stopped — the outcome is unknown, so raise `agent-pattern`'s `timeout` (or `OMP_MCP_TIMEOUT_MS`) before retrying any LLM tool.

### Error codes

| Code | Meaning | Tools |
|------|---------|-------|
| `ERR_001` | `requirements` / `criteria` / `domain` failed printable-text validation | analyze, generate, design, evaluate, submit |
| `ERR_004` | supplied design lacks `overview` or `agents` | evaluate |
| `ERR_009` | LLM provider error (credentials, quota, upstream failure) | analyze, generate, design, evaluate |
| `ERR_012` | supplied design failed strict schema validation | evaluate |
| `ERR_404` | unknown `job_id` | get_agent_design_status, cancel |

## Group 1 — LLM pipeline tools

### `analyze_agent_system`

Derives topology + pattern recommendations. Does not produce a design.

```ts
{
  requirements: string;  // 1-100000 chars, visible text
  domain: string;        // 1-200 chars
}
```

Latency: one LLM round trip; on this host it exceeded the default deadline (aborted at 30.04 s). Not idempotent.

Output (flat object):

| Field | Content |
|-------|---------|
| `strengths`, `weaknesses`, `recommendations` | LLM assessment of the requirement set |
| `recommended_topology` | `AgentTopology` value of the top-scored pattern |
| `recommended_pattern_name` | pattern that drove the recommendation (`""` when nothing scored) |
| `selected_patterns` | top-k patterns with their scores and metadata |
| `quality_metrics` | `{reliability, cost_efficiency, latency, output_quality, observability, safety}`, each 0–10 |
| `matched_domains` | top domain slugs with fusion scores |
| `is_fallback` | `true` when no real domain match was found and `react` was substituted |

### `generate_agent_system`

```ts
{
  requirements: string;
  topology: string;                 // AgentTopology value
  domain: string;
  selected_patterns?: string[] | null;  // exact pattern names, e.g. ["react", "human-in-the-loop"]
}
```

Skips the analyse leg: use it when topology and patterns are already known. Omit
`selected_patterns` to let domain retrieval pick them. Latency: one LLM round trip, with the
same abort risk under the default deadline as `analyze_agent_system`. Not idempotent.

Output: `design.overview.topology`, `design.agents[]`, `design.relationships[]`,
`design.quality_attributes`, and the contract lists — see [Design dict shape](#design-dict-shape).

### `evaluate_agent_system`

```ts
{
  agent_system: Record<string, unknown>;  // design dict (see below)
  criteria: string;                       // 1-100000 chars
  domain: string;                         // 1-200 chars
}
```

Read-only for server state, but still an LLM call — same abort risk under the default deadline
as `analyze_agent_system`. Not idempotent.

Output is **flattened**, unlike the `evaluation` object inside `design_agent_system`:

```ts
{
  summary: string;                 // "Overall score: 42.0/100"
  metrics: Record<string, number>; // per-attribute score / 10 → 0-10 scale
  recommendations: string[];       // flattened from the per-area map
}
```

Input requirements: the dict must pass strict validation — `overview` with a valid
`AgentTopology` value and at least one agent with a kebab-case `id`
(`^[a-z][a-z0-9_-]*$`); otherwise `ERR_012` / `ERR_004`.

Minimum viable input:

```json
{
  "overview": {"topology": "hierarchical", "category": "multi_agent", "principles": ["single-responsibility-agents"]},
  "agents": [
    {"id": "planner", "name": "PlannerAgent", "role": "planner",
     "description": "Decomposes the goal into a task plan",
     "responsibilities": ["task decomposition"], "tools": [], "memory": ["task_state"]},
    {"id": "executor", "name": "ExecutorAgent", "role": "executor",
     "description": "Executes plan steps with tool calls",
     "responsibilities": ["tool invocation"], "tools": ["web_search"], "memory": ["conversation_history"]}
  ],
  "relationships": [
    {"source": "planner", "target": "executor", "type": "handoff", "description": "Dispatches planned steps"}
  ]
}
```

### `design_agent_system`

Full pipeline in one call: analyse → generate → evaluate → refine.

```ts
{
  requirements: string;
  domain: string;
  override_topology?: string | null;  // must be an AgentTopology value, else ERR_001
}
```

Latency 5–10 minutes → it aborts under OMP's default 30 s deadline. Use the job trio,
or raise the server timeout first (see `SKILL.md`).

Output (same schema as the job's `result`):

| Field | Content |
|-------|---------|
| `design` | full design dict |
| `evaluation` | full `AgentSystemEvaluation` dict: `summary{reasoning, overall_score 0-100, strengths, weaknesses, critical_findings}`, `metrics[]{name, score 0-100, description, findings, recommendations}`, `risks`, `compliance`, `recommendations{area: [...]}`. |
| `attempts` | generate attempts performed (1–3) |
| `final_topology` | confirmed topology |
| `final_pattern_name` | pattern matching `final_topology`; `""` when overridden or nothing scored |
| `quality_metrics` | analysis-stage weights (0–10 per attribute) or `null` |
| `final_quality_score` | 0–100 score of the best attempt |
| `matched_domains` | retrieval slugs + fusion scores |
| `is_fallback` | `true` when the `react` fallback was used |
| `alternative_topologies` | `{pattern_name, topology, score}` runner-ups |

Refinement loop: retries while the best `overall_score` stays below `min_quality_score`
(default 50), up to `retrieval.max_tries` generate attempts (config default 2; the pipeline's
own fallback is `DEFAULT_MAX_TRIES = 3`, and the config accepts 1–10).

## Group 2 — async job trio

### `submit_agent_design_job`

```ts
{ requirements: string; domain: string; override_topology?: string | null; }
```

Returns in ~50 ms (measured 0.05 s):

```json
{"job_id": "<uuid>", "status": "pending", "message": "Job <uuid> created. Poll get_agent_design_status('<uuid>') until status is 'completed', 'failed', or 'cancelled'."}
```

Persist the `job_id`: the server has no job listing, so a lost id is unrecoverable.

### `get_agent_design_status`

```ts
{ job_id: string; }
```

Returns in ~40 ms (measured 0.04 s). Read-only and idempotent.

```json
{"job_id": "...", "status": "running", "message": "Job is actively running the design pipeline.", "created_at": "...", "updated_at": "..."}
```

| Status | Meaning |
|--------|---------|
| `pending` | queued, pipeline not started (`"Job is queued, not yet started."`) |
| `running` | pipeline active — poll again in 10–30 s |
| `completed` | full design output in `result` (schema above) |
| `failed` | `error` carries the failure message |
| `cancelled` | cancelled via `cancel_agent_design` |

### `cancel_agent_design`

```ts
{ job_id: string; }
```

Returns in ~30 ms (measured 0.03 s):

```json
{"job_id": "...", "status": "cancelled", "cancelled": true, "task_was_running": true, "message": "Job ... cancelled. The background task will exit at its next cancellation checkpoint."}
```

Best-effort: the pipeline checks the flag at stage boundaries, so up to one LLM call may
still complete. Jobs already `completed`, `failed`, or `cancelled` cannot be cancelled.

## Group 3 — read-only catalog

### `list_agent_patterns`

```ts
{ category?: string | null; domain?: string | null; }
```

Returns `[{name, description}]` — a minimal view. Read-only; no idempotence hint.

- `category`: `reasoning`, `tool_use`, `planning`, `reflection`, `research_synthesis`, `multi_agent`, `memory`, `retrieval`, `safety_control`, `observability` (unknown values return `[]`)
- `domain`: matched against `pattern.suitable_domains`

Caveat: the unfiltered list (61 patterns) exceeds OMP's device-output cap and is cut off
near 10 KB — filter by `category` or `domain`, or read patterns one at a time.

### `get_agent_pattern`

```ts
{ name: string; }   // exact JSON name — 'react', 'supervisor-worker', 'self-rag'
```

Full pattern JSON. Read-only; no idempotence hint. Unknown names raise `Pattern not found: <name>`.

Pattern names carry **no** `-pattern` suffix; on disk the files are `<name>-pattern.json`.
All 61: `agent-as-a-judge`, `agentic-rag`, `agent-resumption`, `agent-tracing-telemetry`,
`camel-role-play`, `chain-of-thought`, `chain-of-verification`, `code-agent`,
`context-compaction`, `control-flow-integrity`, `conversational-memory`, `corrective-rag`,
`cross-reflection`, `decision-log`, `dual-llm-quarantine`, `episodic-memory`,
`evaluator-optimizer`, `goal-creator-passive`, `goal-creator-proactive`,
`graph-orchestration`, `graph-rag`, `guardrails`, `handoff`, `human-in-the-loop`,
`hybrid-rerank`, `kill-switch`, `lats`, `least-privilege-tool-scoping`, `llm-compiler`,
`memoization`, `metagpt-sop-pipeline`, `multi-agent-debate`, `naive-rag`,
`orchestrator-workers`, `parallelization`, `plan-and-solve`, `procedural-memory`,
`prompt-chaining`, `prompt-response-optimizer`, `query-rewriting`, `react`, `reflection`,
`reflexion`, `rewoo`, `routing`, `scratchpad-note-taking`, `self-consistency`,
`self-discovery`, `self-heal-loop`, `self-rag`, `semantic-memory`, `step-budget`, `storm`,
`structured-output`, `subagent-isolation`, `supervisor-worker`, `swarm`, `tool-agent-registry`,
`tree-of-thoughts`, `verifier-critic`, `voting-based-cooperation`.

Pattern JSON keys: `name`, `category`, `topology`, `context`, `benefits`, `tradeoffs`,
`quality_attributes` (0–10 per attribute, includes `simplicity`), `suitable_domains`,
`unsuitable_domains`, `use_cases`, `avoid_when`, `component_types`, `technology_stack`,
`anti_patterns`, `migration_from`, `migration_to`, `design_principles`,
`best_practices`, `references`.

## MCP resources

The server advertises `pattern://`, `pattern://{name}`, `template://{name}`, `component://{type}`.
OMP reads them with `read mcp://<resource-uri>` (e.g. `read mcp://pattern://`).

On this host the sibling `architecture-pattern` server registers the same `pattern://{name}`
scheme and OMP matched that sibling, so `read mcp://pattern://react` fails with
`Pattern not found: react` while the tool route returns the pattern. Treat the tool route
(`get_agent_pattern`, `list_agent_patterns`) as authoritative and use `mcp://` resource reads
only when the target server is unambiguous.

## Prompts

Interactive OMP sessions expose each server prompt as a slash command
`/agent-pattern:<prompt-name>` with `key=value` arguments (quote multi-word values):

| Prompt | Arguments | Effect |
|--------|-----------|--------|
| `design_agent_system_workflow` | `requirements*`, `domain`, `topology` | drives the full design workflow |
| `explore_pattern_catalog` | `domain`, `category` | catalog discovery with live pattern names |
| `evaluate_my_agent_system` | `focus` | structures an existing design, then evaluates it |
| `compare_agent_topologies` | `topology_a*`, `topology_b*`, `requirements*` | two designs side by side (~2× cost) |

Non-interactive route: `write xd://mcp__agent_pattern_get_prompt` with
`{"name": "<prompt>", "arguments": {...}}` → `{"messages": [{"role": "user", "content": "..."}]}`;
`list_prompts` (no args) enumerates them. Inspect with `/mcp prompts` in the TUI.

## Tool annotations

| Tool | readOnlyHint | destructiveHint | idempotentHint |
|------|--------------|-----------------|----------------|
| `analyze_agent_system` | true | false | false |
| `generate_agent_system` | true | false | false |
| `evaluate_agent_system` | true | false | false |
| `design_agent_system` | true | false | false |
| `submit_agent_design_job` | false | false | false |
| `get_agent_design_status` | true | false | **true** |
| `cancel_agent_design` | false | **true** | false |
| `list_agent_patterns` | true | false | — |
| `get_agent_pattern` | true | false | — |

`readOnlyHint: true` on the LLM tools means the server's own state is unchanged — they still
invoke the LLM, cost money, and are not cached.

## Design dict shape

`design` in a pipeline result (and the accepted `agent_system` input, minus
`best_practices`-style extras):

```ts
{
  overview: {topology: AgentTopology, category: PatternCategory, principles: [string], constraints: [string]?, score?: number|null},
  agents: [{
    id, name, role, description, responsibilities: [string],
    llm_role?: "planning"|"generation"|"reflection"|null,
    tools: [string], memory: [string], prompt_strategy?: [string]|null,
    technology_stack: [string], config_requirements: [string]
  }],
  relationships: [{source, target, type, description}],
  quality_attributes: {[attribute]: number},
  tool_contracts: [{tool_name, agent_id, description, input_schema?, output_schema?, auth_required}],
  shared_state_models: [{name, fields: [{...}], description, is_shared}],
  message_contracts: [{message_name, payload_schema, published_by, consumed_by: [string], description}]
}
```

`category` must be one of the ten category slugs; `overview.topology` must be one of the
eight `AgentTopology` values — both validated on input, so a hand-written design fails with
`ERR_012` if they drift.
