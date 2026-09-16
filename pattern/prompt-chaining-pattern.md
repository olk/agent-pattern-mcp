# Prompt Chaining Pattern

## Overview

[JSON Data](./prompt-chaining-pattern.json)

Fixed, well-understood workflows decomposed into sequential LLM steps, each transforming the previous output with a gate check before the next step runs.

## When to Use

- Tasks in these domains: content generation, code generation, regulated domains
- Generate, grade, refine marketing copy

Avoid when: Steps are unknown at design time

## How It Works

- Step Prompt
- Output Gate Validator
- Context Pass-through

## Examples

**Generate, grade, refine marketing copy**: A scenario where this pattern's approach is well-suited to the task.

**Extract, validate, format data**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Add an eval per step
- Retry with feedback on gate failure
- Cache stable intermediate results

## Common Pitfalls

- No adaptivity
- Latency grows linearly
- Breaks when input distribution shifts

## Comparison

| Pattern | Mechanism |
|---|---|
| Plan-and-Solve | Plan first, then execute |
| ReWOO | Plan all tool calls upfront |
| Prompt Chaining | Sequential LLM steps |

## References

- Agent Patterns library