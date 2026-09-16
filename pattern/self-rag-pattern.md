# Self RAG Pattern

## Overview

[JSON Data](./self-rag-pattern.json)

Retrieval decisions made by the model itself: the agent reflects on whether retrieval is needed per claim, critiques retrieved passages, and cites what it used.

## When to Use

- Tasks in these domains: rag applications, high stakes outputs, regulated domains
- Citation-required answers

Avoid when: Every claim needs retrieval (just retrieve always)

## How It Works

- Retrieval Need Detector
- Passage Critic
- Citation Tracker
- Reflection Tokens

## Examples

**Citation-required answers**: A scenario where this pattern's approach is well-suited to the task.

**Mixed parametric and retrieval question answering**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Spot-check citations automatically
- Calibrate the need detector
- Log decisions per segment

## Common Pitfalls

- Reflection tokens add overhead
- Critique quality varies
- Subtle implementation

## Comparison

| Pattern | Mechanism |
|---|---|
| Naive RAG | Single-shot retrieve-then-generate |
| Self-RAG | Self-reflective on-demand retrieval |
| Corrective RAG | Evaluate then retry if low quality |

## References

- Asai et al., *Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection*, 2023