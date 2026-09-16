# Kill Switch Pattern

## Overview

[JSON Data](./kill-switch-pattern.json)

Deployed agents need an out-of-band control plane to halt, pause, or drain running instances without redeploying code.

## When to Use

- Tasks in these domains: autonomous task execution, api automation, multi agent systems
- Halt agent fleet during an incident

Avoid when: Stateless short-lived requests (overkill)

## How It Works

- Control Signal Channel
- Instance Registry
- State Persister
- Cleanup Executor

## Examples

**Halt agent fleet during an incident**: A scenario where this pattern's approach is well-suited to the task.

**Pause during data corruption investigation**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Drill the switch regularly
- Audit switch usage
- Wire switch events to alerting

## Common Pitfalls

- Operational infrastructure required
- Misuse can drop in-flight work
- Needs idempotent cleanup design

## Comparison

| Pattern | Mechanism |
|---|---|
| Human-in-the-Loop | Approval before actions |
| Kill Switch | Out-of-band halt |
| Guardrails | Input/output validation |

## References

- Agent Patterns library