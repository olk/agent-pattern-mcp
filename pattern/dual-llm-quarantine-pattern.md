# Dual Llm Quarantine Pattern

## Overview

[JSON Data](./dual-llm-quarantine-pattern.json)

Agent systems exposed to untrusted input (user prompts, fetched web pages, email attachments, third-party API responses) that may contain prompt injection attacks. A Privileged LLM holds tool access b...

## When to Use

- Tasks in these domains: regulated-domains, customer-support, api-automation

## How It Works

- Privileged LLM
- Quarantined LLM
- Schema Validator
- Symbolic Handle

## Examples

Email assistants that read inbound messages and draft replies

## Best Practices

- Define minimal schemas for each extraction task (30-char max field names)
- Rate-limit or timeout the Quarantined LLM to prevent resource exhaustion
- Log all Quarantined LLM extractions for audit trail

## Common Pitfalls

- Near-doubled cost and latency (two LLM calls per processing step)
- Requires a privileged LLM that never sees untrusted content

## Comparison

| Pattern | Mechanism |
|---|---|
| dual-llm-quarantine | Agent systems exposed to untrusted input (user pro... |
| Related | Alternative approaches |

## References

- Willison, The Dual LLM Pattern for Building AI Assistants that Resist Prompt Injection, 2023 — https://simonwillison.net/2023/Apr/14/dual-llm-pattern/
- Beurer-Kellner et al., Design Patterns for Securing LLM Agents against Prompt Injections, 2025 — https://arxiv.org/abs/2506.08837
- Debenedetti et al., CaMeL: Capabilities for Machine Learning, 2025 — https://arxiv.org/abs/2505.22852
