# Episodic Memory Pattern

## Overview

[JSON Data](./episodic-memory-pattern.json)

Agents that should improve across tasks: records of past executions (goal, actions, outcome, lesson) are stored and retrieved to guide new attempts.

## When to Use

- Tasks in these domains: trial and error learning, long horizon tasks, autonomous task execution
- Coding agent remembering prior bug fixes

Avoid when: The domain changes so fast the past misleads

## How It Works

- Episode Store
- Episode Encoder (embeddings)
- Retrieval Index
- Lesson Extractor

## Examples

**Coding agent remembering prior bug fixes**: A scenario where this pattern's approach is well-suited to the task.

**Ops agent runbooks from past incidents**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Validate lessons periodically
- Deduplicate near-identical episodes
- Include outcome labels

## Common Pitfalls

- Retrieval quality bounds usefulness
- Storage growth over time
- Stale lessons mislead

## Comparison

| Pattern | Mechanism |
|---|---|
| Conversational Memory | Short-term windowing |
| Episodic Memory | Experience recall |
| Semantic Memory | Long-term embedding store |

## References

- Agent Patterns library