# Control Flow Integrity Pattern

## Overview

[JSON Data](./control-flow-integrity-pattern.json)

Agent systems that must execute tool calls in the presence of untrusted content (e.g., web pages, emails, documents) without allowing that content to redirect the control flow. The agent plans the ful

## When to Use

- Tasks in these domains: regulated-domains, api-automation, high-stakes-outputs, web-automation, document-processing

## How It Works

- Planner (clean context)
- Plan Commit Gate
- Executor
- Tool Output Filter

## Examples

Email automation where inbox content is untrusted

## Best Practices

- Keep the planner isolated from any untrusted content
- Serialize the plan before execution begins and log it for audit
- Abort and re-plan only at explicitly defined replan triggers, never on tool output content

## Common Pitfalls

- Cannot adapt the plan based on intermediate tool outputs
- Requires the full task to be decomposable into a static plan

## References

- Beurer-Kellner et al., Design Patterns for Securing LLM Agents against Prompt Injections, 2025 — https://arxiv.org/abs/2506.08837
