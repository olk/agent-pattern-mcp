# Subagent Isolation Pattern

## Overview

[JSON Data](./subagent-isolation-pattern.json)

Multi-agent systems where parallel subagents operate in independent workspaces to prevent file-level conflicts and enable safe concurrent execution. Each subagent works in its own isolated context — writes do not collide, and the orchestrator synthesizes results from distilled summaries rather than retaining full subagent context.

## When to Use

- Tasks in these domains: multi agent systems, code generation, parallel data gathering, document processing
- Incident investigation: three agents dig logs, attempt reproduction, and check history concurrently

Avoid when: Subtasks must react to each other's findings in real time

## How It Works

- Orchestrator Agent
- Isolated Subagent
- Workspace Manager
- Cross-Run Recall

## Examples

**Incident investigation: three agents dig logs, attempt reproduction, and check history concurrently**: A scenario where this pattern's approach is well-suited to the task.

**Code migration: agents modifying different files of the same codebase simultaneously**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Use run IDs to link each subagent execution back to the orchestrator session
- Write observations as structured facts (not just a text summary) for queryable recall
- Test that cross-run queries correctly combine evidence from all subagents

## Common Pitfalls

- Subagents cannot coordinate mid-flight on tightly coupled findings
- Synthesis quality depends on the quality of subagent summary distillation
- Isolation boundaries require careful workspace provisioning
- Debugging requires querying across isolated run contexts

## Comparison

| Pattern | Mechanism |
|---|---|
| Supervisor-Worker | Hierarchical routing |
| Orchestrator-Workers | Dynamic subtask delegation |
| Multi-Agent Debate | Adversarial stress-testing |

## References

- Agent Patterns library