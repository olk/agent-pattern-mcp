# Tool Agent Registry Pattern

## Overview

[JSON Data](./tool-agent-registry-pattern.json)

Agent systems where multiple tools or subagents must be discovered, selected, and invoked dynamically at runtime. A registry maintains a queryable catalogue of available capabilities — with metadata on cost, latency, and quality — so the agent can programmatically pick the right tool or subagent for a task rather than relying on hardcoded tool lists.

## When to Use

- Tasks in these domains: multi agent systems, tool use tasks, rag applications
- Dynamic routing: an agent queries the registry for tools matching a task description

Avoid when: The toolset is fixed and known at design time

## How It Works

- Registry Database
- Tool Metadata Store
- Discovery Query Interface
- Registration API

## Examples

**Dynamic routing: an agent queries the registry for tools matching a task description**: A scenario where this pattern's approach is well-suited to the task.

**Multi-agent systems: workers discover available subagents and their capabilities at runtime**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Include capability, cost, latency, and reliability metadata per tool entry
- Version tool entries so agents can pin to known-good versions
- Periodically health-check registered tools and mark degraded entries

## Common Pitfalls

- Registry must be kept in sync with actual tool availability
- Adding a registry layer introduces latency on first tool selection
- Registry metadata can become stale — tools may degrade without updating their entries
- Increased system complexity for what a static tool list achieves simply

## Comparison

| Pattern | Mechanism |
|---|---|
| ReAct | Iterative reason + act |
| LLM Compiler | Parallel tool execution over DAG |
| Tool Agent Registry | Dynamic tool discovery |

## References

- Agent Patterns library