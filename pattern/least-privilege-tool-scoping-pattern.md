# Least Privilege Tool Scoping Pattern

## Overview

[JSON Data](./least-privilege-tool-scoping-pattern.json)

Agent systems with broad tool access where each task or user request should only be able to invoke the minimal subset of tools necessary to complete that request. Rather than granting an agent full to

## When to Use

- Tasks in these domains: regulated-domains, api-automation, multi-agent-systems

## How It Works

- Scope Policy Engine
- Task Classifier
- Tool Allowlist Generator
- Capability Claim

## Examples

Multi-tenant SaaS agents where each tenant has different API permissions

## Best Practices

- Define tool capabilities as first-class policy objects
- Classify tasks by risk level and provision scopes accordingly
- Re-evaluate scope on each new user request, not just at session start

## Common Pitfalls

- Requires a tool scoping policy engine and task classification
- Mis-scoping can break legitimate tool usage

## References

- Anthropic, Anthropic Tool Use Best Practices, 2024 — https://docs.anthropic.com/en/docs/build-with-claude/tool-use-best-practices
- Agent Patterns Catalog, Least-Privilege Tool Scoping pattern — https://www.agentpatternscatalog.org/patterns/least-privilege-tool-scoping/
