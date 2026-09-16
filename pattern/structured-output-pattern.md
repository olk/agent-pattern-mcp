# Structured Output Pattern

## Overview

[JSON Data](./structured-output-pattern.json)

Every machine-consumed agent output: responses are constrained to a schema (JSON or function-call format) so downstream parsing and validation never depend on free-text luck.

## When to Use

- Tasks in these domains: api automation, data analysis, tool use tasks
- Agent-to-API payloads

Avoid when: Creative free-form writing

## How It Works

- Response Schema
- Constrained Decoder or API mode
- Schema Validator
- Retry Repair Handler

## Examples

**Agent-to-API payloads**: A scenario where this pattern's approach is well-suited to the task.

**Pipeline step contracts**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Use native constrained decoding
- Validate with Pydantic and clear errors
- Reject and repair on violation

## Common Pitfalls

- Schema rigidity versus open-ended tasks
- Constrained decoding can reduce creativity
- Schema maintenance

## Comparison

| Pattern | Mechanism |
|---|---|
| Human-in-the-Loop | Approval before actions |
| Kill Switch | Out-of-band halt |
| Guardrails | Input/output validation |

## References

- Agent Patterns library