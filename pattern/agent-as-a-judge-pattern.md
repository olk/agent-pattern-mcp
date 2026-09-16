# Agent As A Judge Pattern

## Overview

[JSON Data](./agent-as-a-judge-pattern.json)

Agent systems where the quality of a trajectory (all steps, tool calls, intermediate states) must be evaluated before the final response is accepted. A dedicated judge agent — distinct from the genera...

## When to Use

- Tasks in these domains: high-stakes-outputs, regulated-domains, research-reports, code-generation, content-generation

## How It Works

- Generating Agent
- Judge Agent
- Trajectory Logger
- Score Threshold Gate

## Examples

Automated code review with quality gates

## Best Practices

- Calibrate judge on a golden dataset before production use
- Set per-dimension thresholds (e.g., safety must score >= 8)
- Limit retry rounds to prevent infinite revision loops

## Common Pitfalls

- Extra LLM call per evaluation round (significant cost overhead)
- Judge quality depends on judge model capability

## Comparison

| Pattern | Mechanism |
|---|---|
| agent-as-a-judge | Agent systems where the quality of a trajectory (a... |
| Related | Alternative approaches |

## References

- Zheng et al., LLMs as Judges: Evaluating and Improving Chatbot System, 2024 — https://arxiv.org/abs/2306.05685
