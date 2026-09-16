# Storm Pattern

## Overview

[JSON Data](./storm-pattern.json)

Research-report writing that needs breadth: the system generates an outline, simulates multiple expert perspectives, produces per-section questions, retrieves answers, and synthesizes a cited report.

## When to Use

- Tasks in these domains: research reports, exploratory research, rag applications
- Wikipedia-style article drafting

Avoid when: Quick factual answers are enough

## How It Works

- Outline Planner
- Perspective Simulator
- Question Generator
- Retrieval Tools

## Examples

**Wikipedia-style article drafting**: A scenario where this pattern's approach is well-suited to the task.

**Technology landscape report**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Deduplicate overlapping questions
- Cap perspectives at three to five
- Verify citation coverage before the final pass

## Common Pitfalls

- Many LLM and retrieval calls
- High latency and cost
- Pipeline complexity

## Comparison

| Pattern | Mechanism |
|---|---|


## References

- Shao et al., *Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models*, 2024