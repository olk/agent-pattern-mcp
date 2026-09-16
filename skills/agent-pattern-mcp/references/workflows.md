# Workflow Examples

Four tested orchestration recipes for the agent-pattern-mcp server's tools and prompts.

---

## Workflow 1 — Full Design via `design_agent_system`

For clients with heartbeat coverage (Claude Code, OpenCode, Codex CLI). Runs the complete analyse → generate → evaluate → refine pipeline in one blocking call.

```
Call design_agent_system with:
  requirements: "Autonomous research assistant: plan searches across the web,
    retrieve and read sources, verify claims against each other, and write a
    cited report with a human review step before sending"
  domain: "research-reports"
```

**What happens:**
1. Server runs `analyze_agent_system` — derives recommended topology + top-k patterns
2. Server runs `generate_agent_system` with recommended topology
3. Server runs `evaluate_agent_system` against quality criteria
4. If `final_quality_score < 50`, retry generate (up to 2 times)
5. Returns `{design, evaluation, attempts, final_topology, final_pattern_name, quality_metrics, final_quality_score, matched_domains, is_fallback, alternative_topologies}`

**Interpreting `attempts > 1`:** the pipeline retried generation automatically. Inspect `evaluation.recommendations` to see what the retried design changed.

**Expected runtime:** 5–10 minutes. Claude Code / OpenCode / Codex CLI handle this via heartbeat notifications every 30 s.

---

## Workflow 2 — Async Job Trio (for timeout-constrained clients)

For clients with hard 60-second timeouts (Claude Desktop, Cursor, TS-SDK agents). Three steps: submit → poll → handle result.

### Step 1 — Submit the job

```
Call submit_agent_design_job with:
  requirements: "Research assistant: plan searches → retrieve sources → verify claims → write cited report"
  domain: "research-reports"
```

Returns `{job_id: "<uuid>", status: "pending", message: "..."}` immediately.

### Step 2 — Poll until terminal status

```
Call get_agent_design_status with:
  job_id: "<uuid from step 1>"
```

Poll every 10–30 seconds. Branch on `status`:

| Status received | Action |
|----------------|--------|
| `pending` or `running` | Wait, poll again |
| `completed` | Extract `result.design` and `result.evaluation` |
| `failed` | Read `error` field for error details |
| `cancelled` | Inform user; offer to resubmit |

### Step 3 — Cancel if needed

```
Call cancel_agent_design with:
  job_id: "<uuid>"
```

Cancellation is best-effort: takes effect at the next pipeline stage boundary.

---

## Workflow 3 — Explore Catalog Then Generate with Specific Patterns

Use the read-only catalog tools to explore, then call `generate_agent_system` with explicit pattern selection.

### Explore patterns

```
Call list_agent_patterns with:
  category: "research_synthesis"
```

```
Call list_agent_patterns with:
  domain: "exploratory-research"
```

### Get full detail on a candidate

```
Call get_agent_pattern with:
  name: "plan-and-solve-pattern"
```

### Generate with explicit pattern selection

```
Call generate_agent_system with:
  requirements: "Autonomous coding assistant: decompose feature requests,
    edit multiple files, run tests, and self-heal on failures"
  style: "hierarchical"
  domain: "code-generation"
  selected_patterns: ["plan-and-solve-pattern", "reflexion-pattern", "self-heal-loop-pattern"]
```

**Why use `generate_agent_system` instead of `design_agent_system`?** When you already know which topology and patterns you want and do not need the full analyse → evaluate pipeline.

---

## Workflow 4 — Evaluate an Existing Agent System Design

When the user already has an agent-system and wants quality-attribute scores.

```
Call evaluate_agent_system with:
  agent_system: {
    "overview": {
      "topology": "hierarchical",
      "category": "multi_agent",
      "principles": ["single-responsibility-agents", "least-privilege-tools"],
      "constraints": ["max-30s-step-latency", "human-approval-for-external-actions"]
    },
    "agents": [
      {"id": "a1", "name": "PlannerAgent", "role": "planner",
       "description": "Decomposes the goal into a task plan", "responsibilities": ["task decomposition"],
       "tools": [], "memory": ["task_state"], "technology_stack": ["LangGraph"]},
      {"id": "a2", "name": "ExecutorAgent", "role": "executor",
       "description": "Executes plan steps with tool calls", "responsibilities": ["tool invocation"],
       "tools": ["web_search", "code_runner"], "memory": ["conversation_history"], "technology_stack": ["LiteLLM"]}
    ],
    "relationships": [
      {"source": "a1", "target": "a2", "type": "handoff", "description": "Dispatches planned steps"}
    ],
    "quality_attributes": {"reliability": "8", "safety": "9", "output_quality": "8", "latency": "6"}
  }
  criteria: "reliability, safety, output_quality"
  domain: "web-automation"
```

**Focus on critical findings** (any attribute score < 70) first. Group recommendations by quality attribute.

---

## MCP Prompts (Slash Commands)

Four user-invoked workflow templates. The LLM does not auto-invoke these — the user selects one explicitly.

### `/design_agent_system_workflow`

```
/design_agent_system_workflow requirements="..." domain="research-reports" style="hierarchical"
```

Guides the user through: (1) call `design_agent_system`, (2) review quality scores, (3) list tradeoffs, (4) if any score < 75, propose refinements via `evaluate_agent_system`.

**Prompt argument → tool argument mapping:**
- `style` maps to `override_topology` in `design_agent_system`

---

### `/explore_pattern_catalog`

```
/explore_pattern_catalog domain="exploratory-research" category="research_synthesis"
```

Dynamically embeds the live pattern catalog (all 61 pattern names) into the prompt body at registration time — so the prompt always reflects the current catalog. Guides the user through: (1) `list_agent_patterns` with optional filters, (2) `get_agent_pattern` for the chosen name, (3) `mcp_read_resource(uri='pattern://...')` for full JSON detail.

---

### `/evaluate_my_agent_system`

```
/evaluate_my_agent_system focus="safety"
```

Guides: (1) help user structure their design as a dict, (2) call `evaluate_agent_system`, (3) flag critical findings (score < 70), (4) group recommendations by attribute. Extra attention to `safety` if `focus` is specified.

---

### `/compare_agent_topologies`

```
/compare_agent_topologies style_a="hierarchical" style_b="swarm" requirements="Multi-source market research with parallel data gathering"
```

Generates two designs side-by-side and compares tradeoffs. **Cost note:** triggers two `generate_agent_system` calls — approximately 2× token cost and latency. If both scores are within 5 points, note that either topology works.

---

### Tool-Only Clients: `list_prompts` / `get_prompt`

Clients without native `prompts/list` support (e.g. Cursor) can access all four prompts via the generated tools:
```
list_prompts()                           # list available prompts
get_prompt(name="design_agent_system_workflow", arguments={...})  # invoke one
```

---

## Interpreting Results

### `final_quality_score`

0–100 scale. Scores ≥ 75 are strong; 50–74 indicate notable tradeoffs; < 50 triggers automatic retry (up to 2 times). After retries, the best attempt is returned regardless of score.

### `attempts`

| Value | Meaning |
|-------|---------|
| `1` | Succeeded first try |
| `2` | First generation was retry-eligible; retry succeeded |
| `3` | Two retries were needed |

`attempts > 1` is not a failure — it means the pipeline self-healed. Inspect `evaluation.recommendations` for what changed.

### `evaluation.recommendations`

Improvement suggestions grouped by quality attribute. Process: (1) address critical findings (score < 70) first, (2) then address recommendations for attributes below target threshold.

### `matched_domains`

Top domain slugs from BM25 + dense retrieval with fusion scores. If the top score is low, the server falls back to the `single-agent-loop` topology (pattern `react`) — this is expected behaviour, not an error.

### Topology fallback

When retrieval score < `topology_score_threshold` (default 50), the server uses the fallback topology `single-agent-loop` (the topology of the `react` pattern; `recommended_pattern_name` stays `react` only when that pattern was actually scored). If your requirements clearly call for a different topology, pass `override_topology` explicitly (must be one of the 8 `AgentTopology` values).

---

## Best Practices

1. **Pass `domain` and `topology` as separate structured arguments** — never embed them in the `requirements` text. The server uses domain for pattern retrieval; embedding it loses that signal.

2. **Pick your entry point by client type** — `design_agent_system` for heartbeat clients; job trio for 60 s timeout clients. Do not use `design_agent_system` with Claude Desktop or Cursor.

3. **Explore the catalog first** when requirements are vague — use `list_agent_patterns` with domain/category filters to discover candidate patterns before committing to a full design.

4. **Expect `single-agent-loop` as fallback topology** when domain is ambiguous. Pass explicit `override_topology` (an `AgentTopology` value) if you know the desired topology.

5. **Tune heartbeat interval for borderline clients** — set `TASKS_HEARTBEAT_INTERVAL_SECONDS=45` (keep below the client's idle timeout). This avoids the job trio migration for clients that could otherwise use `design_agent_system`.

6. **Use `generate_agent_system` with explicit patterns** when you know the topology and patterns upfront — skips the analyse phase, saving one LLM round trip.

7. **For full design prefer `design_agent_system`** over chaining `analyze_agent_system` + `generate_agent_system` + `evaluate_agent_system` yourself — the pipeline handles retries and refinement automatically.

8. **Cancel via `cancel_agent_design`** rather than abandoning a timed-out request — the server-side task checks the cancellation flag at stage boundaries, freeing resources.
