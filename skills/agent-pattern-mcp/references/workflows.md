# Workflows — agent-pattern MCP in OMP

Recipes for the four jobs this server is used for. Tool parameters and output fields are in
`tools.md`; the entry-point rules (deadline, job trio) are in `SKILL.md`.

Every call below is a JSON write to a device:

```text
write xd://mcp__agent_pattern_<tool>  <json args>
```

---

## Recipe 1 — Full design via the job trio (default)

Use this whenever the user wants a design. With OMP's default 30 s deadline the job-trio calls
are also the only ones that fit: a single `analyze_agent_system` call was aborted at 30.04 s in a
test, and `design_agent_system` alone runs 5–10 minutes.

**Step 1 — submit** (returns in ~50 ms):

```json
{"requirements": "Autonomous research assistant: plan searches across the web, retrieve and read sources, verify claims against each other, and write a cited report with a human review step before sending",
 "domain": "research-reports"}
```

→ `{"job_id": "affe6c9d-…", "status": "pending", "message": "…"}`

**Step 2 — record the `job_id`** before polling. There is no server-side job list, and OMP has no
handle registry for MCP jobs; if the poll loop may span turns, write the id to a scratch file
(e.g. `.omp/agent-pattern-job.txt`) so a later turn can resume.

**Step 3 — poll** every 10–30 s with `{"job_id": "affe6c9d-…"}`:

| `status` | Action |
|----------|--------|
| `pending` / `running` | wait, poll again |
| `completed` | read `result.design` and `result.evaluation` |
| `failed` | report `error` |
| `cancelled` | report; offer to resubmit |

Between polls, interleave useful work (or `bash sleep 15`); the poll call itself is ~40 ms.

**Step 4 — cancel** if the user changes their mind or the job is no longer needed:

```json
{"job_id": "affe6c9d-…"}
```

→ `{"status": "cancelled", "cancelled": true, "task_was_running": true, …}` — takes effect at the
next stage boundary, so up to one LLM call may still land.

**What the pipeline did:** analyse (topology + top-k patterns) → generate → evaluate →
refine while `overall_score < 50`, up to `max_tries` attempts (default 2, ceiling 3).

---

## Recipe 2 — One-shot `design_agent_system`

Only for a user who prefers one blocking call and accepts a multi-minute turn. First raise the
deadline for this server in `~/.omp/agent/mcp.json`:

```json
"agent-pattern": { "type": "http", "url": "http://localhost:8051/mcp", "timeout": 900000 }
```

- `timeout` is milliseconds; `0` disables the client-side deadline entirely.
- `OMP_MCP_TIMEOUT_MS` overrides every per-server value process-wide.
- A project `.omp/mcp.json` entry shadows the user entry; the user file's `disabledServers`
  beats `enabledServers` in every source.
- Run `/mcp reload` after editing, then confirm with `/mcp list`.

Then in one call:

```json
{"requirements": "Autonomous coding assistant: decompose feature requests, edit multiple files, run tests, and self-heal on failures",
 "domain": "code-generation",
 "override_topology": "hierarchical"}
```

Expect 5–10 minutes; the result carries `design`, `evaluation`, `attempts`, `final_topology`,
`final_pattern_name`, `final_quality_score`, `quality_metrics`, `matched_domains`, `is_fallback`,
`alternative_topologies`. `override_topology` is validated against the eight `AgentTopology`
values and rejected with `ERR_001` otherwise.

---

## Recipe 3 — Explore the catalog, then generate with chosen patterns

**List by category** (fast, no LLM):

```json
{"category": "research_synthesis"}
```

**Narrow by domain** instead when the category is unclear:

```json
{"domain": "exploratory-research"}
```

**Fetch a candidate in full:**

```json
{"name": "plan-and-solve"}
```

**Generate with the patterns you picked** (skips the analyse leg, one LLM round trip):

```json
{"requirements": "Autonomous coding assistant: decompose feature requests, edit multiple files, run tests, and self-heal on failures",
 "topology": "hierarchical",
 "domain": "code-generation",
 "selected_patterns": ["plan-and-solve", "reflexion", "self-heal-loop"]}
```

Pattern names are exact and carry no `-pattern` suffix; useful ones here include
`supervisor-worker`, `orchestrator-workers`, `parallelization`, `verifier-critic`,
`reflexion`, `self-heal-loop`, `human-in-the-loop`, `guardrails`, `dual-llm-quarantine`,
`self-rag`, `corrective-rag`, `graph-rag`.

**Caveat:** the unfiltered `list_agent_patterns` call returns all 61 patterns and is cut off by
OMP's device-output cap near 10 KB — always filter, or read patterns individually.

---

## Recipe 4 — Evaluate an existing design

```json
{"agent_system": {"overview": {"topology": "hierarchical", "category": "multi_agent", "principles": ["single-responsibility-agents"]},
                  "agents": [{"id": "planner", "name": "PlannerAgent", "role": "planner",
                              "description": "Decomposes the goal into a task plan",
                              "responsibilities": ["task decomposition"], "tools": [], "memory": ["task_state"]},
                             {"id": "executor", "name": "ExecutorAgent", "role": "executor",
                              "description": "Executes plan steps with tool calls",
                              "responsibilities": ["tool invocation"], "tools": ["web_search", "code_runner"],
                              "memory": ["conversation_history"]}],
                  "relationships": [{"source": "planner", "target": "executor", "type": "handoff",
                                     "description": "Dispatches planned steps"}]},
 "criteria": "reliability, safety, output_quality",
 "domain": "web-automation"}
```

Returns `{summary, metrics, recommendations}` — `summary` is a string carrying the overall
`n/100` score, `metrics` maps attribute → score on a **0–10** scale, `recommendations` is a flat
string list (the per-area map of the pipeline is flattened).

Input validation is strict: `overview.topology` must be a valid `AgentTopology` value, agent ids
must be kebab-case, and at least one agent plus an overview are required (`ERR_012` / `ERR_004`).

Report order: state the overall score, then attributes below ~7, then the recommendations
grouped by the attribute they target.

---

## Recipe 5 — Prompts (both routes)

Interactive TUI — one slash command per server prompt, `key=value` args, quote multi-word values:

```text
/agent-pattern:design_agent_system_workflow requirements="Autonomous research assistant with cited reports" domain="research-reports" topology="hierarchical"
/agent-pattern:explore_pattern_catalog domain="exploratory-research" category="research_synthesis"
/agent-pattern:evaluate_my_agent_system focus="safety"
/agent-pattern:compare_agent_topologies topology_a="hierarchical" topology_b="swarm" requirements="Multi-source market research"
```

`/mcp prompts` lists the connected prompts; `/mcp resources` lists resources.

Non-interactive (agent-driven, works in scripts and headless runs):

```json
{"name": "design_agent_system_workflow",
 "arguments": {"requirements": "…", "domain": "research-reports", "topology": "swarm"}}
```

→ `{"messages": [{"role": "user", "content": "…"}]}`; follow the returned instructions in the
current turn. `list_prompts` (no args) enumerates prompt names and arguments.

Cost note: `compare_agent_topologies` triggers two `generate_agent_system` calls — roughly 2×
tokens and latency. If the two designs score within ~5 points of each other, say so and pick
either.

---

## Interpreting results

### `final_quality_score`

0–100. ≥ 75 strong; 50–74 workable with named tradeoffs; < 50 means the pipeline regenerated and
still returned its best attempt — surface `evaluation.recommendations` instead of presenting the
design as finished.

### `attempts`

| Value | Meaning |
|-------|---------|
| 1 | succeeded first try |
| 2 | first attempt scored below `min_quality_score` (50); the retry succeeded |
| 3+ | two or more retries — only reached when `retrieval.max_tries` is configured above 2 (default), up to 10 |

`attempts > 1` is the loop self-healing, not a failure — read the recommendations to see what
changed.

### `evaluation.recommendations`

A map keyed by area (`{"reliability": [...], "safety": [...]}`). Fix critical findings first
(metric score < 70 on the 0–100 pipeline scale, < 7 on the flattened evaluate scale), then work
down the attributes the user cares about.

### `matched_domains` and fallback

Top domain slugs with fusion scores. When the top score is low or `is_fallback` is `true`, the
analyzer substituted `react` / `single-agent-loop` — expected behaviour. Pass `override_topology`
(explicit) or `topology` (generate) when the requirement clearly calls for another topology.

### `alternative_topologies`

`{pattern_name, topology, score}` runner-ups. Use them to present a genuine second option — e.g.
`hierarchical` → `swarm` — instead of an invented comparison.

---

## Troubleshooting (OMP-specific)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `MCP failure … failure: timeout … Request timeout after 30000ms` | OMP's per-request MCP deadline; server progress notifications do not extend it | use the job trio, or set `"timeout": 900000` (or `0`) for `agent-pattern` and `/mcp reload`. The outcome of the aborted call is unknown — re-check job state or re-issue deliberately |
| `list_agent_patterns` result ends mid-JSON | device-output cap near 10 KB | filter by `category`/`domain`, or page with individual `get_agent_pattern` calls |
| `read mcp://pattern://react` says `Pattern not found: react` | `pattern://{name}` is registered by both pattern servers; OMP matched the architecture one | read patterns via `get_agent_pattern` |
| Tool list changed / calls fail after an edit to the server | OMP keeps stale MCP connections | `/mcp reload` (full) or `/mcp reconnect agent-pattern` |
| `ERR_009` | LLM provider problem on the server side | report the message; do not retry blindly — check the server's credentials/quota |
| `ERR_012` on evaluate | hand-written design failed schema validation | use the design dict shape in `tools.md`; check `overview.topology` and agent ids |
