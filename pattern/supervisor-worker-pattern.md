# Supervisor Worker Pattern

## Overview

[JSON Data](./supervisor-worker-pattern.json)

Complex work exceeding one agent's context or skill breadth: a supervisor decomposes the goal, routes subtasks to specialized worker agents, aggregates results, and decides completion.

## When to Use

- Tasks in these domains: multi agent systems, long horizon tasks, complex reasoning
- Research three competitors then compare

Avoid when: One agent suffices

## How It Works

- Supervisor
- Task Queue
- Worker Agents
- Result Aggregator

## Examples

**Research three competitors then compare**: A scenario where this pattern's approach is well-suited to the task.

**Multi-file code change**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Use typed task messages
- Retry at the worker level
- Cap workers per goal

## Common Pitfalls

- Coordination overhead
- Supervisor is a bottleneck and failure point
- Harder debugging
- More total tokens

## Comparison

| Pattern | Mechanism |
|---|---|
| Supervisor-Worker | Hierarchical routing |
| Orchestrator-Workers | Dynamic subtask delegation |
| Multi-Agent Debate | Adversarial stress-testing |

## References

- Agent Patterns library