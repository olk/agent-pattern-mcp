# LATS Pattern

## Overview

[JSON Data](./lats-pattern.json)

Hard exploration tasks where a single reasoning path is not enough; the agent performs tree search over reasoning and action trajectories with environment feedback and self-reflection.

## When to Use

- Tasks in these domains: complex reasoning, code generation, exploratory research, web automation
- Algorithmic coding with test feedback

Avoid when: Budget-limited runs

## How It Works

- Search Tree
- Expansion Policy
- Value Evaluation Function
- Reflection Node

## Examples

**Algorithmic coding with test feedback**: A scenario where this pattern's approach is well-suited to the task.

**Web navigation tasks**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Deduplicate states
- Store trajectories for reuse
- Parallelize leaf evaluation

## Common Pitfalls

- Highest cost and latency among single-agent patterns
- Needs an environment or evaluator for feedback
- Implementation complexity

## Comparison

| Pattern | Mechanism |
|---|---|
| Chain-of-Thought | Step-by-step decomposition |
| Self-Discovery | Adaptive reasoning module selection |
| LATS | Tree search with environment feedback |

## References

- Zhou et al., *Language Agent Tree Search Unifies Reasoning, Acting, and Planning in Language Models*, 2023