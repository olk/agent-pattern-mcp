# Self Consistency Pattern

## Overview

[JSON Data](./self-consistency-pattern.json)

Reasoning tasks where a single sampled reasoning path may be unreliable. The agent samples multiple diverse reasoning chains for the same problem, then selects the most consistent answer via majority ...

## When to Use

- Tasks in these domains: complex-reasoning, code-generation, data-analysis

## How It Works

- CoT Prompt
- Sample Generator
- Answer Extractor
- Vote Aggregator

## Examples

Mathematical word problems

## Best Practices

- Set temperature > 0 for diverse samples
- Normalize answer formats before voting (e.g., strip whitespace)
- Log all sampled answers for post-hoc analysis

## Common Pitfalls

- N× cost where N is the number of samples
- N× latency for same reason

## Comparison

| Pattern | Mechanism |
|---|---|
| self-consistency | Reasoning tasks where a single sampled reasoning p... |
| Related | Alternative approaches |

## References

- Wang et al., Self-Consistency Improves Chain of Thought Reasoning in Language Models, 2022 — https://arxiv.org/abs/2203.11171
