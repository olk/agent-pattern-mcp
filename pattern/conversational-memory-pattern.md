# Conversational Memory Pattern

## Overview

[JSON Data](./conversational-memory-pattern.json)

Multi-turn assistants that must remember earlier turns: short-term history is windowed, summarized, or selectively compressed to fit the context budget.

## When to Use

- Tasks in these domains: conversational assistants, customer support, api automation
- Chat assistants

Avoid when: Compliance forbids storing conversations

## How It Works

- Message Buffer
- Window Manager
- Summarizer
- Session Store

## Examples

**Chat assistants**: A scenario where this pattern's approach is well-suited to the task.

**Support sessions**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Use a hybrid window plus summary
- Encrypt sessions at rest
- Store summaries, not raw PII

## Common Pitfalls

- Summarization loses detail
- Window tuning per use case
- Sensitive data retention risk

## Comparison

| Pattern | Mechanism |
|---|---|
| Conversational Memory | Short-term windowing |
| Episodic Memory | Experience recall |
| Semantic Memory | Long-term embedding store |

## References

- Agent Patterns library