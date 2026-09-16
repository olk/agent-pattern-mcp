# Plan And Solve Pattern

## Overview

[JSON Data](./plan-and-solve-pattern.json)

Multi-step tasks with clear structure: a planner produces an explicit ordered plan, then an executor walks the plan step by step and aggregates the results.

## When to Use

- Tasks in these domains: content generation, research reports, code generation
- Marketing strategy draft

Avoid when: Task requires tools (use ReAct)

## How It Works

- Planner
- Step Executor
- State Tracker
- Result Aggregator

## Examples

**Marketing strategy draft**: A scenario where this pattern's approach is well-suited to the task.

**Competitive landscape analysis**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Strong model plans, cheap model executes
- Cap plan length
- Allow re-plan checkpoints

## Common Pitfalls

- No tool use in the base form
- The plan may be suboptimal
- Weak recovery when reality drifts from the plan

## Comparison

| Pattern | Mechanism |
|---|---|
| Plan-and-Solve | Plan first, then execute |
| ReWOO | Plan all tool calls upfront |
| Prompt Chaining | Sequential LLM steps |

## References

- Wang et al., *Plan-and-Solve Prompting*, 2023