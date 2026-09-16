# Guardrails Pattern

## Overview

[JSON Data](./guardrails-pattern.json)

Any agent exposed to untrusted input or producing user-facing output: validation layers check prompts, completions, and tool payloads against safety policies such as PII, injection, toxicity, and scope.

## When to Use

- Tasks in these domains: regulated domains, customer support, conversational assistants
- PII redaction before logging

Avoid when: Heavy check chains double latency on hot paths

## How It Works

- Input Validator
- Output Validator
- Policy Engine
- Redaction Transformer

## Examples

**PII redaction before logging**: A scenario where this pattern's approach is well-suited to the task.

**Prompt-injection screening of retrieved documents**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Combine with step-budget for defense in depth
- Log all violations with categories
- Canary policy updates

## Common Pitfalls

- False positives reject legitimate requests
- Latency added per check
- Policy maintenance burden

## Comparison

| Pattern | Mechanism |
|---|---|
| Human-in-the-Loop | Approval before actions |
| Kill Switch | Out-of-band halt |
| Guardrails | Input/output validation |

## References

- Agent Patterns library