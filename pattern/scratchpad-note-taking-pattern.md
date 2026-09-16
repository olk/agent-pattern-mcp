# Scratchpad Note Taking Pattern

## Overview

[JSON Data](./scratchpad-note-taking-pattern.json)

Long-running multi-step tasks where the agent accumulates intermediate findings, partial results, and reminders that must survive across tool calls and context resets. The agent writes notes to persis...

## When to Use

- Tasks in these domains: long-horizon-tasks, code-generation, research-reports, autonomous-task-execution

## How It Works

- Note Writer Tool
- Note Reader Tool
- Note Index
- Staleness Checker

## Examples

Complex coding tasks where the agent must track file changes across many edits

## Best Practices

- Use a structured format (JSON or Markdown) for machine-readable notes
- Validate notes on read — check staleness before trusting
- Expose notes to the user via a read tool so they can follow the agent's reasoning

## Common Pitfalls

- Extra tool calls to write and read notes
- Note format and retrieval strategy must be designed carefully

## Comparison

| Pattern | Mechanism |
|---|---|
| scratchpad-note-taking | Long-running multi-step tasks where the agent accu... |
| Related | Alternative approaches |

## References

- Anthropic, Effective Context Engineering for AI Agents, 2025 — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- LangChain Blog, Context Engineering for Agents, 2025 — https://www.langchain.com/blog/context-engineering-for-agents
