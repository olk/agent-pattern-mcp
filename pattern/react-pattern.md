# ReAct Pattern

## Overview

[JSON Data](./react-pattern.json)

Tasks requiring interleaved reasoning and external tool or API calls where each action depends on the previous observation.

## When to Use

- Tasks in these domains: tool use tasks, api automation, data analysis
- Weather and local events lookup

Avoid when: No tools needed

## How It Works

- Thought Generator
- Tool Selector
- Tool Executor
- Observation Buffer

## Examples

**Weather and local events lookup**: A scenario where this pattern's approach is well-suited to the task.

**Stock price plus percent-change calculation**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Cap iterations (e.g., 5)
- Truncate stale observations
- Provide structured tool schemas

## Common Pitfalls

- Sequential tool execution (no parallelism)
- More LLM calls than plan-first patterns such as REWOO
- Can loop without careful iteration control

## Comparison

| Pattern | Mechanism |
|---|---|
| ReAct | Iterative reason + act |
| LLM Compiler | Parallel tool execution over DAG |
| Tool Agent Registry | Dynamic tool discovery |

## References

- Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models*, 2023