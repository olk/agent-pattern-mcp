# Tool Reference

All nine tools exposed by the agent-pattern-mcp server. Parameter types are Pydantic-validated; descriptions are verbatim from the server's `inputSchema`.

---

## Group 1 — LLM Pipeline Tools

### `analyze_agent_system`

Analyses requirements and domain → recommended topology, top-k patterns, quality-attribute weights, and matched domain slugs. Does NOT produce a full design.

```python
analyze_agent_system(
    requirements: str,      # 1–100000 chars printable text
    domain: str,            # 1–200 chars; e.g. "code-generation", "research-reports"
) -> dict
```

**Key output fields:**
- `recommended_topology`: AgentTopology value (e.g. `"hierarchical"`, `"single-agent-loop"`) — the topology of the top-scored pattern
- `recommended_pattern_name`: name of the top-scored pattern that drove the recommendation (e.g. `"react"`)
- `alternative_topologies`: runner-up topologies, deduplicated per topology; each entry is `{pattern_name, topology, score}`
- `quality_metrics`: {reliability, cost_efficiency, latency, output_quality, observability, safety, simplicity} — weights 0–1
- `matched_domains`: top BM25+FAISS retrieval results with fusion scores

Long-running (LLM call). Not idempotent.

---

### `generate_agent_system`

Generates a full agent system design using the specified topology and selected patterns. Requires a topology — use `analyze_agent_system` first to get recommendations, or pass `override_topology` to `design_agent_system` instead.

```python
generate_agent_system(
    requirements: str,          # 1–100000 chars
    topology: str,             # agent topology name, e.g. "hierarchical", "pipeline", "swarm"
    domain: str,               # 1–200 chars
    selected_patterns: list[str] | None = None,  # pattern names, e.g. ["react", "human-in-the-loop"]
) -> dict
```

**Note:** `selected_patterns` is optional. When omitted the server auto-selects top-k patterns based on domain retrieval. Pass explicit pattern names to force inclusion of specific patterns (e.g. `["human-in-the-loop"]` for approval-gated workflows).

**Key output fields:**
- `design.overview.topology`: confirmed topology used
- `design.agents`: list of {id, name, role, description, responsibilities, tools, memory, technology_stack}
- `design.relationships`: list of {source, target, type, description}
- `design.tool_contracts`, `design.shared_state_models`, `design.message_contracts`

Long-running (LLM call). Not idempotent.

---

### `evaluate_agent_system`

Scores an existing agent system design against specified criteria and domain via pattern benchmarking. Annotated `readOnlyHint=True` (server state is unchanged) but still triggers an LLM call and is long-running.

```python
evaluate_agent_system(
    agent_system: dict,     # Agent system design as dictionary
    criteria: str,           # 1–100000 chars; evaluation focus, e.g. "reliability, safety"
    domain: str,            # 1–200 chars
) -> dict
```

**Expected `agent_system` dict shape:**
```python
{
  "overview": {"topology": "...", "category": "...", "principles": [...], "constraints": [...]},
  "agents": [{"id": "...", "name": "...", "role": "...", "description": "...",
              "responsibilities": [...], "tools": [...], "memory": [...]}],
  "relationships": [{"source": "...", "target": "...", "type": "...", "description": "..."}],
  "quality_attributes": {"reliability": 8.0, "output_quality": 9.0, ...}
}
```

**Key output fields:**
- `evaluation.summary`: overall assessment
- `evaluation.metrics`: per-attribute scores (each 1–10)
- `evaluation.recommendations`: improvement suggestions grouped by quality attribute
- `evaluation.risks`: identified risks with severity

Long-running (LLM call). Not idempotent.

---

### `design_agent_system`

Full pipeline: `analyze_agent_system` → `generate_agent_system` → `evaluate_agent_system` → up to 2 automatic retries if quality < 50. Returns both the design and its evaluation in one call.

```python
design_agent_system(
    requirements: str,                          # 1–100000 chars
    domain: str,                               # 1–200 chars
    override_topology: str | None = None,         # force a specific topology
) -> dict
```

**Use this unless** your client has a hard 60-second timeout** (Claude Desktop, Cursor, TS-SDK agents) — in those cases use the job trio instead.

**Key output fields (from `DesignAgentSystemOutput`):**
- `design`: full agent-system dict (overview, agents, relationships, contracts)
- `evaluation`: evaluation dict (summary, metrics, recommendations, risks)
- `attempts`: number of generate attempts made (1 = succeeded first try; >1 = retry succeeded)
- `final_topology`: confirmed topology (AgentTopology value)
- `final_pattern_name`: name of the top-scored pattern matching `final_topology` (`""` when the topology was overridden or no patterns were scored)
- `quality_metrics`: analysis-stage quality attribute weights
- `final_quality_score`: 0–100 overall quality score after best attempt
- `matched_domains`: top matched domain slugs with fusion scores
- `is_fallback`: True when no real pattern candidates matched and the fallback was used
- `alternative_topologies`: runner-up topologies, deduplicated per topology; each entry is `{pattern_name, topology, score}`

`override_topology` is strictly validated against the `AgentTopology` enum (`evaluator-loop`, `graph-orchestrated`, `hierarchical`, `parallel-fan-out`, `pipeline`, `plan-execute`, `single-agent-loop`, `swarm`); any other value is rejected with `ERR_001`.

**Retry logic:** if `final_quality_score < 50` after generation, the pipeline retries (up to 2 times). `attempts > 1` indicates a retry was needed — inspect `evaluation.recommendations` to understand what changed.

Long-running (5–10 min; 3–9 LLM round trips). Not idempotent.

---

## Group 2 — Async Job Trio

For clients with hard 60-second request timeouts (Claude Desktop, Cursor, TS-SDK agents). Returns `job_id` immediately; poll `get_agent_design_status` every 10–30 seconds.

### `submit_agent_design_job`

```python
submit_agent_design_job(
    requirements: str,              # 1–100000 chars
    domain: str,                   # 1–200 chars
    override_topology: str | None = None,
) -> dict
```

Returns immediately:
```python
{
    "job_id": "<uuid>",
    "status": "pending",
    "message": "Job <uuid> created. Poll get_agent_design_status('<uuid>') until status is 'completed', 'failed', or 'cancelled'."
}
```

Store the `job_id` — there is no `tasks/list` equivalent; the client owns the handle.

---

### `get_agent_design_status`

```python
get_agent_design_status(
    job_id: str,   # returned by submit_agent_design_job
) -> dict
```

**Status values (`JobStatus` enum):**

| Status | Meaning |
|--------|---------|
| `pending` | Job queued, pipeline not yet started |
| `running` | Pipeline active; wait and poll again |
| `completed` | Done — full design is in `result` field |
| `failed` | Pipeline error — `error` field contains message |
| `cancelled` | Cancelled by `cancel_agent_design` |

**Polling loop:**
```python
while True:
    result = get_agent_design_status(job_id)
    if result["status"] == "completed":
        design = result["result"]["design"]
        evaluation = result["result"]["evaluation"]
        break
    elif result["status"] in ("failed", "cancelled"):
        handle_error(result)
        break
    sleep(15)  # poll every 10–30 s
```

Returns `{job_id, status, message, created_at, updated_at}` plus `result` when completed or `error` when failed.

---

### `cancel_agent_design`

Best-effort cancellation. Takes effect at the next pipeline stage boundary (may take up to one LLM call).

```python
cancel_agent_design(
    job_id: str,   # returned by submit_agent_design_job
) -> dict
```

Returns `{cancelled: bool, status: <current status>}`.
Cannot cancel jobs that are already `completed`, `failed`, or `cancelled`.

---

## Group 3 — Read-Only Pattern Catalog

Fast, idempotent. Safe for exploration before committing to an expensive pipeline call.

### `list_agent_patterns`

Returns a **minimal view** (name + one-line description) of all patterns, optionally filtered.

```python
list_agent_patterns(
    category: str | None = None,   # reasoning, tool_use, planning, reflection,
                                   # research_synthesis, multi_agent, memory, retrieval,
                                   # safety_control, observability
    domain: str | None = None,    # matches against pattern.suitable_domains
) -> list[dict[str, str]]
```

**For full pattern JSON** use `get_agent_pattern(name=...)` — do not try to parse the minimal list entries.

Valid `category` values: `reasoning`, `tool_use`, `planning`, `reflection`, `research_synthesis`, `multi_agent`, `memory`, `retrieval`, `safety_control`, `observability`.

---

### `get_agent_pattern`

Returns the **full JSON** for one pattern by exact name.

```python
get_agent_pattern(
    name: str,   # exact pattern name, e.g. "react", "supervisor-worker", "agentic-rag"
) -> dict
```

**Pattern JSON shape:**
```python
{
    "category": "...",
    "name": "...",
    "context": "when this pattern applies",
    "benefits": ["...", "..."],
    "tradeoffs": ["...", "..."],
    "quality_attributes": {
        "reliability": 8, "cost_efficiency": 6, "latency": 5,
        "output_quality": 8, "observability": 9, "safety": 6, "simplicity": 9
    },
    "suitable_domains": ["tool-use-tasks", "api-automation", ...],
    "unsuitable_domains": ["..."],
    "component_types": ["...", "..."],
    "technology_stack": ["...", "..."],
    "anti_patterns": ["...", "..."],
    "migration_from": ["..."],
    "migration_to": ["..."],
    "design_principles": ["...", "..."],
    "best_practices": ["...", "..."],
    "topology": "single-agent-loop"
}
```

Raises `ToolError` if the pattern name is not found. Use `list_agent_patterns` first to discover exact names.

---

## MCP Resources

| URI | What it returns |
|-----|-----------------|
| `pattern://{name}` | Full pattern JSON (same as `get_agent_pattern`) |
| `template://{name}` | Agent system template by name |
| `component://{type}` | Agent blueprint (e.g. `component://supervisor`) |

Access via `mcp_read_resource(server="agent-pattern-mcp", uri="pattern://react-pattern")`.

---

## Tool Annotations Reference

| Tool | readOnlyHint | destructiveHint | idempotentHint |
|------|-------------|----------------|-----------------|
| `analyze_agent_system` | — | — | No |
| `generate_agent_system` | — | — | No |
| `evaluate_agent_system` | **True** | False | No |
| `design_agent_system` | — | — | No |
| `submit_agent_design_job` | — | — | N/A |
| `get_agent_design_status` | True | False | **True** |
| `cancel_agent_design` | False | **True** | No |
| `list_agent_patterns` | True | False | **True** |
| `get_agent_pattern` | True | False | **True** |

`readOnlyHint=True` on `evaluate_agent_system` means the server's own state is unchanged (it benchmarks, not writes). It still invokes the LLM and is long-running.
