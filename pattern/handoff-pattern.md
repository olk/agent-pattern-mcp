# Handoff Pattern

## Overview

[JSON Data](./handoff-pattern.json)

Conversational systems with multiple specialists: the active conversation is transferred from one agent to another carrying full context, instead of one agent handling everything.

## When to Use

- Tasks in these domains: customer support, conversational assistants, api automation
- Billing to technical support transfer

Avoid when: Specialists differ only marginally

## How It Works

- Handoff Tool or Router
- Context Serializer
- Specialist Agents
- Transcript Store

## Examples

**Billing to technical support transfer**: A scenario where this pattern's approach is well-suited to the task.

**Sales to onboarding**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Summarize-so-far in the transfer payload
- Count and limit handoffs
- Verify state after transfer

## Common Pitfalls

- Context transfer losses
- Handoff-churn loops
- Specialist overlap confusion

## Comparison

| Pattern | Mechanism |
|---|---|
| Supervisor-Worker | Hierarchical routing |
| Orchestrator-Workers | Dynamic subtask delegation |
| Multi-Agent Debate | Adversarial stress-testing |

## References

- Agent Patterns library