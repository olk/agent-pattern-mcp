# Multi Agent Debate Pattern

## Overview

[JSON Data](./multi-agent-debate-pattern.json)

Decisions or analyses where a single generation risks bias or hallucination: multiple agents argue distinct positions across rounds while a judge synthesizes the final verdict.

## When to Use

- Tasks in these domains: high stakes outputs, complex reasoning, regulated domains
- Legal argument review

Avoid when: The task is routine

## How It Works

- Proponent Agents
- Opponent Agents
- Debate Round Router
- Judge Synthesizer

## Examples

**Legal argument review**: A scenario where this pattern's approach is well-suited to the task.

**Medical second-opinion synthesis**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Use two to three agents over two to three rounds
- Reveal positions simultaneously
- Score arguments by evidence

## Common Pitfalls

- Highest token multipliers (agents times rounds)
- Slow
- Judge quality bounds the outcome

## Comparison

| Pattern | Mechanism |
|---|---|
| Supervisor-Worker | Hierarchical routing |
| Orchestrator-Workers | Dynamic subtask delegation |
| Multi-Agent Debate | Adversarial stress-testing |

## References

- Du et al., *Improving Factuality and Reasoning in Language Models through Multiagent Debate*, 2023 — https://arxiv.org/abs/2305.14325