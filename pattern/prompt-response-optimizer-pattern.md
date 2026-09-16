# Prompt Response Optimizer Pattern

## Overview

[JSON Data](./prompt-response-optimizer-pattern.json)

Systems that iteratively refine prompts or response templates based on observed outputs, success rates, or user feedback. Rather than treating prompts as fixed, the system treats them as tunable parameters — adjusting prompt construction, instruction ordering, or response schemas to maximize measured quality over multiple rounds.

## When to Use

- Tasks in these domains: tool use tasks, code generation, content generation
- Tool definition refinement: a prompt is tuned based on observed tool call success rates

Avoid when: No feedback signal is available to evaluate prompt quality

## How It Works

- Prompt Generator
- Evaluator
- Optimizer Controller
- Prompt Version Store

## Examples

**Tool definition refinement: a prompt is tuned based on observed tool call success rates**: A scenario where this pattern's approach is well-suited to the task.

**RAG query optimization: prompt templates are refined based on retrieval precision metrics**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Start with a simple heuristic (word ordering, few-shot examples) before automated optimization
- Use a held-out eval set to detect overfitting to the optimization signal
- Maintain a prompt changelog so regressions can be traced to specific changes

## Common Pitfalls

- Requires a feedback signal (human labels, task success, evaluator scores)
- Prompt optimization can be sample-inefficient — many attempts before improvement
- Overfitting to the evaluation metric can degrade real-world performance
- Optimized prompts may not generalize to out-of-distribution inputs

## Comparison

| Pattern | Mechanism |
|---|---|
| Plan-and-Solve | Plan first, then execute |
| ReWOO | Plan all tool calls upfront |
| Prompt Chaining | Sequential LLM steps |

## References

- Agent Patterns library