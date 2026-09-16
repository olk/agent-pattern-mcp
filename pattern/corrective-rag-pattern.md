# Corrective RAG Pattern

## Overview

[JSON Data](./corrective-rag-pattern.json)

RAG pipelines that must self-heal: retrieved documents are evaluated for quality and relevance; weak sets trigger re-retrieval or web search before generation.

## When to Use

- Tasks in these domains: rag applications, research reports, high stakes outputs
- Support answers verified against the knowledge base

Avoid when: Bulk low-cost question answering

## How It Works

- Retrieval Evaluator
- Retry Reformulate Handler
- Web-Search Fallback
- Knowledge Filter

## Examples

**Support answers verified against the knowledge base**: A scenario where this pattern's approach is well-suited to the task.

**Legal research with web fallback**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Calibrate the evaluator on labeled pairs
- Cache grades
- Log fallback reasons

## Common Pitfalls

- Extra evaluation pass
- Latency grows on failures
- Evaluator calibration needed

## Comparison

| Pattern | Mechanism |
|---|---|
| Naive RAG | Single-shot retrieve-then-generate |
| Self-RAG | Self-reflective on-demand retrieval |
| Corrective RAG | Evaluate then retry if low quality |

## References

- Gao et al., *Retrieval-Augmented Generation for Large Language Models: A Survey*, 2024