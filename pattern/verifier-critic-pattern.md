# Verifier Critic Pattern

## Overview

[JSON Data](./verifier-critic-pattern.json)

Production pipelines where generated output must meet a rubric: a critic agent scores and annotates the generator's output and gates release until criteria pass.

## When to Use

- Tasks in these domains: high stakes outputs, regulated domains, content generation
- Legal draft gating

Avoid when: Bulk low-cost content

## How It Works

- Generator
- Critic Agent
- Rubric Store
- Gate Release Decision

## Examples

**Legal draft gating**: A scenario where this pattern's approach is well-suited to the task.

**Medical summary checks**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Verify by sampling at scale
- Feed critic failures back into generator prompts
- Watch for rubric drift

## Common Pitfalls

- Doubles inference on the verified subset
- Rubric maintenance burden
- Critic false positives block good output

## Comparison

| Pattern | Mechanism |
|---|---|
| Supervisor-Worker | Hierarchical routing |
| Orchestrator-Workers | Dynamic subtask delegation |
| Multi-Agent Debate | Adversarial stress-testing |

## References

- Agent Patterns library