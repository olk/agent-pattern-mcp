# Rewoo Pattern

## Overview

[JSON Data](./rewoo-pattern.json)

Cost-conscious tool workflows: all tool calls are planned upfront in one pass as a plan of expressions, then executed without interleaved LLM reasoning.

## When to Use

- Tasks in these domains: cost sensitive workloads, tool use tasks, api automation
- Scheduled data pulls

Avoid when: Task shape is unknown upfront

## How It Works

- Planner (expression graph)
- Tool Executor
- Substitute Solver

## Examples

**Scheduled data pulls**: A scenario where this pattern's approach is well-suited to the task.

**Batch enrichment pipelines**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Dry-run plan validation
- Use explicit variable syntax (#E1..#En)
- Fall back to ReAct on solver failure

## Common Pitfalls

- Brittle when observations invalidate later plan steps
- No adaptive tool choice
- Solver quality depends on plan coverage

## Comparison

| Pattern | Mechanism |
|---|---|
| Plan-and-Solve | Plan first, then execute |
| ReWOO | Plan all tool calls upfront |
| Prompt Chaining | Sequential LLM steps |

## References

- Xu et al., *ReWOO: Decoupling Reasoning from Observations*, 2023