# Parallelization Pattern

## Overview

[JSON Data](./parallelization-pattern.json)

Parallelization runs independent LLM calls concurrently to reduce wall-clock latency or to increase output quality through diversity. The pattern has two flavors: **sectioning** (splitting a task into independent subtasks run in parallel) and **voting** (running the same task multiple times to aggregate diverse outputs).

## When to Use

Use parallelization when:
- Subtasks are independent and can be executed in any order
- Multiple perspectives or attempts improve output confidence
- Latency reduction outweighs the additional coordination overhead
- You have a clear aggregation strategy (concatenation, majority vote, or judge)

Avoid when tasks have data dependencies, cost is the primary constraint, or the task is inherently sequential.

## How It Works

1. A **fan-out coordinator** divides the input into independent units
2. Multiple **worker LLMs** process their units simultaneously
3. A **result aggregator** combines outputs using voting, averaging, or a synthesis judge
4. The coordinator returns the aggregated result to the caller

## Examples

**Sectioning**: Running one LLM to process a document while another screens it for inappropriate content — both run concurrently and their outputs are combined.

**Voting**: Three different prompts review the same code for different vulnerability classes; a coordinator tallies the findings by severity.

## Best Practices

- Validate that tasks are truly independent before choosing this pattern
- Use diverse system prompts or model variants for voting to maximize coverage
- Set explicit per-worker timeouts and aggregate partial results on timeout
- Log the fan-out/fan-in structure for observability

## Common Pitfalls

- Running all workers on identical inputs with identical prompts — provides no diversity
- Failing to handle worker timeouts gracefully
- Aggregating results without checking for consensus when voting

## Comparison

| Pattern | When to use |
|---|---|
| LLM Compiler | Tools must be called in parallel with dependency-aware DAG scheduling |
| Orchestrator-Workers | Subtasks are determined dynamically at runtime by an orchestrator |
| Voting-Based Cooperation | Multiple agents produce candidate answers and a tally produces the final decision |

## References

- Anthropic, *Building Effective Agents* (2024) — Parallelization workflow
- Agent Patterns Catalog, *Parallelization* pattern
