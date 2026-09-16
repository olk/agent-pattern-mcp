# Naive RAG Pattern

## Overview

[JSON Data](./naive-rag-pattern.json)

Knowledge tasks beyond parametric memory: chunks from documents are embedded, the top-k are retrieved for a query, and the answer is generated with them in context.

## When to Use

- Tasks in these domains: rag applications, customer support, conversational assistants
- Documentation question answering

Avoid when: Questions are multi-hop

## How It Works

- Chunker
- Embedder
- Vector Index
- Retriever

## Examples

**Documentation question answering**: A scenario where this pattern's approach is well-suited to the task.

**Policy lookup**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Evaluate retrieval recall separately
- Chunk along semantic units
- Filter by metadata

## Common Pitfalls

- Single-shot retrieval misses multi-hop needs
- Chunking quality bounds everything
- No verification of relevance

## Comparison

| Pattern | Mechanism |
|---|---|
| Naive RAG | Single-shot retrieve-then-generate |
| Self-RAG | Self-reflective on-demand retrieval |
| Corrective RAG | Evaluate then retry if low quality |

## References

- Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*, 2020