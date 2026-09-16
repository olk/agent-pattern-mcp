# Query Rewriting Pattern

## Overview

[JSON Data](./query-rewriting-pattern.json)

Retrieval quality is gated by query formulation: user questions are reformulated, decomposed, or expanded (HyDE, multi-query) before hitting indexes.

## When to Use

- Tasks in these domains: rag-applications, customer-support, research-reports
- Vague or multi-concept queries needing decomposition
- Cross-lingual retrieval where query language differs from document language

Avoid when: Queries are already keyword-perfect; zero-latency tolerance applies

## How It Works

- Query Rewriter
- Decomposition Planner
- Expansion Generator
- Result Merger

## Examples

**Support paraphrase to knowledge-base language**: A scenario where this pattern's approach is well-suited to the task.

**Decompose comparison questions**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- A/B test rewrites on eval sets
- Cap expansions at three to five
- Keep the original query in the mix

## Common Pitfalls

- Rewrites that lose constraints
- Unbounded query fan-out
- No union dedup of results

## Comparison

| Pattern | Mechanism |
|---|---|
| Naive RAG | Single-shot retrieve-then-generate |
| Query Rewriting | Pre-retrieval reformulation |
| Hybrid Rerank | Post-retrieval precision |

## References

- Gao et al., *Query Rewriting for Retrieval-Augmented Large Language Models*, 2023
