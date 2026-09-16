# Reflexion Pattern

## Overview

[JSON Data](./reflexion-pattern.json)

Trial-and-error tasks with an evaluator: after each failed attempt the agent writes a verbal reflection about the failure, stores it in memory, and uses it to guide the next attempt.

## When to Use

- Tasks in these domains: code generation, trial and error learning, complex reasoning
- Function passing test cases

Avoid when: No clear success metric

## How It Works

- Actor (generator)
- Evaluator
- Self-Reflector
- Episodic Memory Store

## Examples

**Function passing test cases**: A scenario where this pattern's approach is well-suited to the task.

**SQL passing validation**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Set max_trials to about three
- Include evaluator output verbatim in the reflection
- Reset memory on task change

## Common Pitfalls

- Needs an evaluator or success signal
- Multiple full attempts are expensive
- May not converge

## Comparison

| Pattern | Mechanism |
|---|---|
| Reflection | Generate → critique → refine |
| Reflexion | Verbal reinforcement from failures |
| Self-Heal Loop | Deterministic verifier drives repair |

## References

- Shinn et al., *Reflexion: Language Agents with Verbal Reinforcement Learning*, 2023