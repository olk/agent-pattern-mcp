# Hybrid Rerank Pattern

## Overview

[JSON Data](./hybrid-rerank-pattern.json)

Retrieval at scale where a single strategy misses: sparse (BM25) and dense (embedding) candidates are fused, then a cross-encoder reranks the merged pool.

## When to Use

- Tasks in these domains: rag applications, research reports, data analysis
- Enterprise search

Avoid when: The corpus is small

## How It Works

- BM25 Index
- Dense Vector Index
- Fusion Layer (reciprocal rank)
- Cross-Encoder Reranker

## Examples

**Enterprise search**: A scenario where this pattern's approach is well-suited to the task.

**Legal and medical document retrieval**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Use a 50-to-10 rerank funnel
- Refresh BM25 on corpus change
- Monitor per-strategy contribution

## Common Pitfalls

- Reranker compute on candidates
- More moving parts
- Two indexes to maintain

## Comparison

| Pattern | Mechanism |
|---|---|
| Naive RAG | Single-shot retrieve-then-generate |
| Self-RAG | Self-reflective on-demand retrieval |
| Corrective RAG | Evaluate then retry if low quality |

## References

- Agent Patterns library