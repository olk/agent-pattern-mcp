# Chain Of Thought Pattern

## Overview

[JSON Data](./chain-of-thought-pattern.json)

Tasks where the model must reason through multiple intermediate steps before producing a final answer; foundational prompt-level scaffolding for all structured reasoning patterns.

## When to Use

- Tasks in these domains: complex reasoning, content generation, code generation
- Math word problems

Avoid when: Answer is trivially retrievable

## How It Works

- Reasoning Prompt Scaffold
- Answer Synthesizer
- Trace Logger

## Examples

**Math word problems**: A scenario where this pattern's approach is well-suited to the task.

**Multi-hop question answering**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Provide few-shot examples of good chains
- Log full traces for observability
- Combine with structured-output for machine-readable steps

## Common Pitfalls

- Longer outputs increase token cost
- Chains can be plausible but wrong
- Gains shrink on trivial tasks

## Comparison

| Pattern | Mechanism |
|---|---|
| Chain-of-Thought | Step-by-step decomposition |
| Self-Discovery | Adaptive reasoning module selection |
| LATS | Tree search with environment feedback |

## References

- Wei et al., *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*, 2022