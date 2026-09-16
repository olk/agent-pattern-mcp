# Tree Of Thoughts Pattern

## Overview

[JSON Data](./tree-of-thoughts-pattern.json)

Complex reasoning tasks where a single linear reasoning chain is insufficient and the agent must explore multiple alternative reasoning branches. The agent generates intermediate thoughts as nodes, ev...

## When to Use

- Tasks in these domains: complex-reasoning, code-generation, exploratory-research

## How It Works

- Thought Generator
- Branch Evaluator
- Search Controller
- Node Budget Manager

## Examples

Mathematical proof search

## Best Practices

- Start breadth-first, switch to depth-first when a strong candidate emerges
- Store failed branch summaries to avoid repeating dead ends
- Use the LLM itself as the branch evaluator when no external signal exists

## Common Pitfalls

- Exponential branching increases cost and latency
- Requires a good evaluation function to prune branches

## Comparison

| Pattern | Mechanism |
|---|---|
| tree-of-thoughts | Complex reasoning tasks where a single linear reas... |
| Related | Alternative approaches |

## References

- Yao et al., Tree of Thoughts: Deliberate Problem Solving with Large Language Models, 2023 — https://arxiv.org/abs/2305.10601
