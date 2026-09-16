# Routing Pattern

## Overview

[JSON Data](./routing-pattern.json)

Heterogeneous inputs where one prompt cannot serve all: a classifier routes each input to the most suitable downstream handler, prompt, or agent.

## When to Use

- Tasks in these domains: customer support, conversational assistants, regulated domains
- Support ticket triage

Avoid when: Few, similar categories

## How It Works

- Input Classifier
- Route Registry
- Handlers
- Fallback Handler

## Examples

**Support ticket triage**: A scenario where this pattern's approach is well-suited to the task.

**Prompt selection by language or topic**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Log route plus confidence
- Audit labels periodically
- Version route definitions

## Common Pitfalls

- Router errors propagate downstream
- Route maintenance overhead
- Cold-start on new categories

## Comparison

| Pattern | Mechanism |
|---|---|
| Plan-and-Solve | Plan first, then execute |
| ReWOO | Plan all tool calls upfront |
| Prompt Chaining | Sequential LLM steps |

## References

- Agent Patterns library