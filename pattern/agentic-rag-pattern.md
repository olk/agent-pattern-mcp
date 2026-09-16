# Agentic RAG Pattern

## Overview

[JSON Data](./agentic-rag-pattern.json)

Research-grade retrieval where the query process itself is agentic: the agent plans searches, chooses sources, retrieves iteratively, reflects on gaps, and re-queries.

## When to Use

- Tasks in these domains: rag applications, research reports, exploratory research
- Literature review

Avoid when: A simple lookup suffices

## How It Works

- Query Planner
- Source Router
- Iterative Retriever
- Gap Reflector

## Examples

**Literature review**: A scenario where this pattern's approach is well-suited to the task.

**Market research**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Limit retrieval rounds to three or four
- Score source credibility
- Log the query plan

## Common Pitfalls

- Many LLM and retrieval rounds
- High latency and cost
- Implementation complexity

## Comparison

| Pattern | Mechanism |
|---|---|
| Naive RAG | Single-shot retrieve-then-generate |
| Self-RAG | Self-reflective on-demand retrieval |
| Corrective RAG | Evaluate then retry if low quality |

## References

- Agent Patterns library