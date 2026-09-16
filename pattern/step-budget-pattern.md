# Step Budget Pattern

## Overview

[JSON Data](./step-budget-pattern.json)

Any autonomous loop (ReAct, LATS, agentic RAG) must be bounded: a per-request cap on tool calls, iterations, or tokens prevents runaway cost and infinite loops.

## When to Use

- Tasks in these domains: autonomous task execution, tool use tasks, long horizon tasks
- Cap ReAct at ten tool calls

Avoid when: Fixed budgets truncate mission-critical work without escalation

## How It Works

- Budget Counter
- Budget Enforcer
- Graceful-Stop Handler
- Partial Result Formatter

## Examples

**Cap ReAct at ten tool calls**: A scenario where this pattern's approach is well-suited to the task.

**Token budget per session**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Warn at eighty percent
- Return partial results with status
- Weight budgets per tool cost

## Common Pitfalls

- Hard caps can truncate legitimate long tasks
- Budget tuning is required
- No per-step semantic awareness

## Comparison

| Pattern | Mechanism |
|---|---|
| Human-in-the-Loop | Approval before actions |
| Kill Switch | Out-of-band halt |
| Guardrails | Input/output validation |

## References

- Agent Patterns Catalog, Step Budget pattern — https://www.agentpatternscatalog.org/patterns/step-budget/