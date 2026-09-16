# LLM Compiler Pattern

## Overview

[JSON Data](./llm-compiler-pattern.json)

Workloads with many independent tool calls; a planner compiles the request into a DAG of function calls that execute in parallel where dependencies allow.

## When to Use

- Tasks in these domains: parallel data gathering, data analysis, research reports
- Weather in five cities compared

Avoid when: Tools must run sequentially

## How It Works

- Planner Compiler
- DAG Scheduler
- Parallel Tool Executors
- Join Reducer

## Examples

**Weather in five cities compared**: A scenario where this pattern's approach is well-suited to the task.

**Fan-out enrichment of records**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Batch independent calls
- Cache repeated subgraphs
- Log per-node timings

## Common Pitfalls

- Planning overhead on every request
- Weak when dependencies emerge mid-execution
- Complex failure handling
- Requires a parallel-capable runtime

## Comparison

| Pattern | Mechanism |
|---|---|
| ReAct | Iterative reason + act |
| LLM Compiler | Parallel tool execution over DAG |
| Tool Agent Registry | Dynamic tool discovery |

## References

- Kim et al., *An LLM Compiler for Parallel Function Calling*, 2024