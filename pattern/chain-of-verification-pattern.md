# Chain Of Verification Pattern

## Overview

[JSON Data](./chain-of-verification-pattern.json)

Hallucination-prone factual tasks: after answering, the model drafts verification questions, answers them independently, and revises the final answer when contradictions appear.

## When to Use

- Tasks in these domains: research reports, rag applications, regulated domains
- Factual long-form answers

Avoid when: Creative generation

## How It Works

- Answer Generator
- Verification Question Generator
- Independent Verifier
- Revision Applier

## Examples

**Factual long-form answers**: A scenario where this pattern's approach is well-suited to the task.

**Medical or legal summaries**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Pair with retrieval for verification
- Limit to a handful of verification questions
- Expose the contradiction list

## Common Pitfalls

- Three or more LLM passes
- Verification answers can also hallucinate
- Adds latency

## Comparison

| Pattern | Mechanism |
|---|---|
| Reflection | Generate → critique → refine |
| Reflexion | Verbal reinforcement from failures |
| Self-Heal Loop | Deterministic verifier drives repair |

## References

- Dhuliawala et al., *Chain-of-Verification Reduces Hallucination in Large Language Models*, 2023