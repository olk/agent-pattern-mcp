# Evaluator Optimizer Pattern

## Overview

[JSON Data](./evaluator-optimizer-pattern.json)

Tightly coupled generate-and-evaluate loop between two LLM roles: one produces output, the other scores it against clear criteria and returns actionable feedback until convergence.

## When to Use

- Tasks in these domains: high stakes outputs, content generation, regulated domains
- Literary translation polish

Avoid when: Criteria are vague

## How It Works

- Generator
- Evaluator
- Feedback Channel
- Convergence Check

## Examples

**Literary translation polish**: A scenario where this pattern's approach is well-suited to the task.

**Legal clause drafting**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Put the rubric in the evaluator prompt
- Use delta-based feedback
- Log the score trajectory

## Common Pitfalls

- Doubles inference on the verified subset
- Needs evaluable criteria
- Risk of preference ping-pong

## Comparison

| Pattern | Mechanism |
|---|---|
| Reflection | Generate → critique → refine |
| Reflexion | Verbal reinforcement from failures |
| Self-Heal Loop | Deterministic verifier drives repair |

## References

- Agent Patterns library