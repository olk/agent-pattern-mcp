# Human In The Loop Pattern

## Overview

[JSON Data](./human-in-the-loop-pattern.json)

Agents whose actions can have irreversible or high-impact consequences; defined checkpoints require explicit human approval before proceeding.

## When to Use

- Tasks in these domains: high stakes outputs, regulated domains, api automation
- Payment execution approval

Avoid when: Latency budget forbids waiting

## How It Works

- Approval Gate
- Action Risk Classifier
- Notification Channel
- Audit Log

## Examples

**Payment execution approval**: A scenario where this pattern's approach is well-suited to the task.

**Production database migration**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Batch approvals where possible
- Show a diff or preview
- Auto-approve idempotent reads

## Common Pitfalls

- Adds latency and staffing
- Approval fatigue can erode safety
- Breaks fully autonomous SLAs

## Comparison

| Pattern | Mechanism |
|---|---|
| Human-in-the-Loop | Approval before actions |
| Kill Switch | Out-of-band halt |
| Guardrails | Input/output validation |

## References

- Agent Patterns library