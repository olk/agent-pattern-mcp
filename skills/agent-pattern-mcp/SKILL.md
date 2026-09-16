---
name: agent-pattern-mcp
description: >
  Designs AI agent systems via the agent-pattern MCP server: analyses requirements,
  selects from 61 patterns (ReAct, reflexion, planner-executor, multi-agent debate,
  supervisor-worker, agentic-RAG and 55 more), generates full designs with agents,
  relationships, tool contracts, state models, and message contracts, and evaluates
  quality across reliability, cost efficiency, latency, output quality, observability,
  and safety. Use when designing a new agent system, comparing agent topologies,
  evaluating an existing agent design, or exploring the pattern catalog. Triggers on
  requests to design an agent system for X, compare supervisor-worker vs swarm,
  evaluate this agent design, choose an agent pattern for X, or any AI agent
  architecture task. Do NOT use for implementing individual features, prompt
  engineering for a single LLM call, or library/framework selection. Requires the
  agent-pattern MCP server connected.
---

## Critical Rules

### Client timeout matrix — pick the right entry point

| Client | Timeout | Use this |
|--------|---------|----------|
| Claude Code, OpenCode, Codex CLI | ~300 s (heartbeat-reset) | `design_agent_system` directly |
| Claude Desktop, Cursor, TS-SDK agents | 60 s (hardcoded) | Job trio: `submit_agent_design_job` → poll `get_agent_design_status` every 10–30 s |
| MCP clients with custom timeouts | varies | If timeout < 5 min, prefer job trio |

The `TASKS_HEARTBEAT_INTERVAL_SECONDS` env var (default 30 s) controls the heartbeat interval. Increase it toward 60 s for clients with tight idle limits.

### Structured arguments — domain and topology are separate parameters

- `requirements`: free-text description of what the agent system must do
- `domain`: problem-space tag (e.g. `code-generation`, `research-reports`, `customer-support`) — filters which patterns apply; pass as a separate argument, **never** embed in `requirements`
- `override_topology` / `topology`: agent topology name (e.g. `hierarchical`, `pipeline`, `swarm`) — **always** pass as its own argument; `override_topology` takes precedence over the server-derived topology

### Domain ≠ Topology vocabulary

- **Domain** (~30 slugs): problem-space classification — answers "which patterns are relevant?" Retrieved via BM25 + dense embedding + cross-encoder rerank
- **Topology** (8 names): orchestration decision — answers "which agent topology was chosen?" Scored by requirements-weighted ranking; `react` (single-agent loop) is the fallback when retrieval score < threshold

---

## Overview

The agent-pattern-mcp server provides a full agent system design pipeline:

1. **Analyse** requirements + domain → recommended topology + top-k matching patterns with quality-attribute scores
2. **Generate** a concrete agent system: agents (roles, tools, memory), relationships, tool contracts, state models, message contracts
3. **Evaluate** the design against quality attributes (reliability, cost efficiency, latency, output quality, observability, safety)
4. **Refine** — up to 2 automatic retries if quality score < 50

The server ships 61 built-in patterns (ReAct, reflexion, plan-and-solve, LLM-compiler, supervisor-worker, multi-agent debate, agentic-RAG, self-RAG, guardrails, and 52 more). Custom patterns can be added via JSON files in the pattern directory.

---

## When to Use This Skill

**Use when the user asks to:**
- Design an AI agent system for a new task or domain
- Compare agent topologies (e.g. supervisor-worker vs swarm)
- Evaluate an existing agent system design
- Explore the pattern catalog to find the right pattern
- Choose an agent pattern for a given workload

**Do NOT use for:**
- Implementing individual features or writing application code
- Prompt engineering for a single LLM call
- Choosing a library or framework (LangGraph vs CrewAI etc.)
- Refactoring a single agent's internals

**Tune heartbeat intervals** if borderline on timeout: set `TASKS_HEARTBEAT_INTERVAL_SECONDS=45` (below client idle limit).

---

## Entry-Point Decision Guide

```
Does the user have an existing agent system design?
├── YES → evaluate_agent_system(agent_system, criteria, domain)
└── NO
    ├── Want to explore patterns first?
    │   ├── list_agent_patterns(category?, domain?)   ← fast, idempotent
    │   └── get_agent_pattern(name)                   ← full JSON
    │
    ├── Want a full design + evaluation?
    │   ├── Claude Code / OpenCode / Codex CLI
    │   │   → design_agent_system(requirements, domain, override_topology?)
    │   └── Claude Desktop / Cursor / TS-SDK
    │       → submit_agent_design_job → poll get_agent_design_status
    │
    └── Want to generate with specific topology + patterns?
        → generate_agent_system(requirements, style, domain, selected_patterns?)
```

---

## Tools Quick Reference

| Tool | Purpose | Latency | Idempotent | See |
|------|---------|---------|------------|-----|
| `analyze_agent_system` | Derive topology + pattern recommendations from requirements | Long (LLM) | No | references/tools.md |
| `generate_agent_system` | Produce design with specified topology + patterns | Long (LLM) | No | references/tools.md |
| `evaluate_agent_system` | Score existing design against quality criteria | Long (LLM) | No | references/tools.md |
| `design_agent_system` | Full pipeline: analyse → generate → evaluate → refine | 5–10 min | No | references/tools.md |
| `submit_agent_design_job` | Start long job; returns job_id immediately | Fast return | N/A | references/tools.md |
| `get_agent_design_status` | Poll job status; result when `completed` | Fast | Yes | references/tools.md |
| `cancel_agent_design` | Best-effort cancel at next stage boundary | Fast | No | references/tools.md |
| `list_agent_patterns` | List all / filtered patterns (minimal view) | Fast | Yes | references/tools.md |
| `get_agent_pattern` | Full pattern JSON by name | Fast | Yes | references/tools.md |

---

## Resources & Prompts at a Glance

### MCP Resources
```
pattern://{name}     # Full pattern JSON (e.g. pattern://react-pattern)
template://{name}    # Agent system template
component://{type}   # Agent blueprint (e.g. component://supervisor)
```

### Slash-Command Prompts (4 total)
| Prompt | Args | What it does |
|--------|------|--------------|
| `/design_agent_system_workflow` | `requirements*`, `domain="general"`, `style` | Full analyse → generate → evaluate → refine pipeline |
| `/explore_pattern_catalog` | `domain`, `category` | Live catalog discovery; embeds pattern names dynamically |
| `/evaluate_my_agent_system` | `focus` | Guide user through evaluate_agent_system; prioritises score < 70 |
| `/compare_agent_topologies` | `style_a*`, `style_b*`, `requirements*` | Two designs side-by-side; ~2× token cost |

Tool-only clients (no native prompts protocol): use `list_prompts` and `get_prompt` instead.

For full detail see `references/tools.md` and `references/workflows.md`.
