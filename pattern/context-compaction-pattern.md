# Context Compaction Pattern

## Overview

[JSON Data](./context-compaction-pattern.json)

Long-running agent conversations or tasks that exceed the context window limit. Compaction periodically summarizes the accumulated context — including user messages, assistant reasoning traces, tool c

## When to Use

- Tasks in these domains: long-horizon-tasks, research-reports, code-generation

## How It Works

- Context Monitor
- Compaction Trigger
- Summarizer LLM
- Summary Serializer

## Examples

Long coding sessions that exceed the context window

## Best Practices

- Tune the compaction prompt for your domain — preserve what matters
- Serialize the compaction block so the model knows context was summarized
- Test compaction trajectories by querying for specific facts from before compaction

## Common Pitfalls

- Compaction itself requires an LLM call (latency and cost)
- Information loss is inevitable — overly aggressive compaction loses critical context

## References

- Anthropic, Effective Context Engineering for AI Agents: Compaction, 2025 — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
