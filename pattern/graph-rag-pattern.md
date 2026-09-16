# Graph Rag Pattern

## Overview

[JSON Data](./graph-rag-pattern.json)

Knowledge-intensive tasks over large document collections where flat-text chunk retrieval misses relationships between entities. GraphRAG first extracts a knowledge graph from the corpus (entities, re...

## When to Use

- Tasks in these domains: rag-applications, research-reports, exploratory-research, document-processing

## How It Works

- Graph Extractor
- Community Detector
- Community Summarizer
- Global Retriever

## Examples

Answering questions about a legal document corpus

## Best Practices

- Use an LLM for entity and relationship extraction from each chunk
- Apply community detection (e.g., Leiden algorithm) before summarization
- Store both the community summaries and the raw community subgraph for answer grounding

## Common Pitfalls

- Graph construction is expensive (requires LLM entity extraction)
- Higher latency than naive chunk retrieval

## Comparison

| Pattern | Mechanism |
|---|---|
| graph-rag | Knowledge-intensive tasks over large document coll... |
| Related | Alternative approaches |

## References

- Microsoft Research, GraphRAG Project, 2024 — https://www.microsoft.com/en-us/research/project/graphrag/
- Edge et al., From Local to Global: A GraphRAG Approach to Query-Focused Summarization, 2024 — https://arxiv.org/abs/2404.16130
