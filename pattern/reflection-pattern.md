# Reflection Pattern

## Overview

[JSON Data](./reflection-pattern.json)

High-quality generation tasks where a first draft benefits from an explicit critique pass; the same or a second LLM reviews the draft against the goal and a refined version is produced.

## When to Use

- Tasks in these domains: content generation, code generation, high stakes outputs
- Technical blog post writing

Avoid when: Simple queries

## How It Works

- Generator
- Critic
- Revision Applier
- Cycle Controller

## Examples

**Technical blog post writing**: A scenario where this pattern's approach is well-suited to the task.

**Product description polish**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Use a different model or temperature for the critic
- Apply rubric-based critique
- Stop early on a quality threshold

## Common Pitfalls

- Two to three times the token cost
- Diminishing returns after two to three cycles
- Latency roughly doubles

## Comparison

| Pattern | Mechanism |
|---|---|
| Reflection | Generate → critique → refine |
| Reflexion | Verbal reinforcement from failures |
| Self-Heal Loop | Deterministic verifier drives repair |

## References

- Shinn et al., *Reflexion: Language Agents with Verbal Reinforcement Learning*, 2023