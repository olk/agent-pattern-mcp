# Memoization Pattern

## Overview

[JSON Data](./memoization-pattern.json)

Repeated identical or near-identical LLM and tool calls: results are cached, keyed by normalized input, model, and parameters, to cut cost and latency.

## When to Use

- Tasks in these domains: cost sensitive workloads, latency sensitive tasks, api automation
- FAQ answering

Avoid when: Freshness-sensitive answers

## How It Works

- Cache Key Normalizer
- Result Cache (exact and semantic)
- TTL Invalidation Policy
- Hit and Miss Metrics

## Examples

**FAQ answering**: A scenario where this pattern's approach is well-suited to the task.

**Deterministic tool outputs**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Use two tiers: exact then semantic
- Measure hit rate
- Pin cache entries per model version

## Common Pitfalls

- Stale results after data changes
- Cache key normalization is tricky for semantic caches
- Storage cost

## Comparison

| Pattern | Mechanism |
|---|---|
| Conversational Memory | Short-term windowing |
| Episodic Memory | Experience recall |
| Semantic Memory | Long-term embedding store |

## References

- Agent Patterns library