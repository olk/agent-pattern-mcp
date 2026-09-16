# Semantic Memory Pattern

## Overview

[JSON Data](./semantic-memory-pattern.json)

Agents needing durable factual knowledge beyond the context window: curated facts are embedded in a knowledge store queried by similarity at prompt time.

## When to Use

- Tasks in these domains: rag applications, customer support, research reports
- Product FAQ knowledge

Avoid when: Fast-changing source-of-truth data

## How It Works

- Knowledge Store
- Embedding Pipeline
- Similarity Retriever
- Provenance Metadata

## Examples

**Product FAQ knowledge**: A scenario where this pattern's approach is well-suited to the task.

**Company policy store**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Chunk by semantic units
- Evaluate recall on golden questions
- Watch drift after re-embedding

## Common Pitfalls

- Knowledge curation cost
- Retrieval misses on phrasing drift
- Index maintenance

## Comparison

| Pattern | Mechanism |
|---|---|
| Conversational Memory | Short-term windowing |
| Episodic Memory | Experience recall |
| Semantic Memory | Long-term embedding store |

## References

- Agent Patterns library