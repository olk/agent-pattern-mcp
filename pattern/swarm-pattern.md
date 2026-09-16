# Swarm Pattern

## Overview

[JSON Data](./swarm-pattern.json)

Peer-to-peer agent collectives with no supervisor: agents post to and read from a shared blackboard or message bus and self-organize opportunistically.

## When to Use

- Tasks in these domains: exploratory research, multi agent systems, parallel data gathering
- Research swarm on shared notes

Avoid when: Deterministic business workflows are required

## How It Works

- Shared Blackboard or Bus
- Peer Agents
- Signal and Subscription Registry
- Convergence Detector

## Examples

**Research swarm on shared notes**: A scenario where this pattern's approach is well-suited to the task.

**Open-source triage bots**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Cap message rates
- Tag provenance on every post
- Snapshot board state periodically

## Common Pitfalls

- Emergent, hard-to-predict behavior
- Debugging is difficult
- Duplicated work
- Weakest fit for deterministic SLAs; avoid on critical production paths

## Comparison

| Pattern | Mechanism |
|---|---|
| Supervisor-Worker | Hierarchical routing |
| Orchestrator-Workers | Dynamic subtask delegation |
| Multi-Agent Debate | Adversarial stress-testing |

## References

- Agent Patterns library