# Camel Role Play Pattern

## Overview

[JSON Data](./camel-role-play-pattern.json)

Multi-agent collaboration where agents adopt distinct social roles (e.g., a software architect and a frontend developer) and communicate autonomously to solve a task. Agents are given their role descr

## When to Use

- Tasks in these domains: multi-agent-systems, content-generation, code-generation

## How It Works

- Role Specifier
- User Proxy Agent
- Assistant Agent
- Dialogue Manager

## Examples

AI writing team with specialized writer and editor agents

## Best Practices

- Start with a minimal task to calibrate role descriptions
- Set a maximum number of dialogue rounds with a fallback synthesizer
- Log the full dialogue for post-hoc analysis and debugging

## Common Pitfalls

- Unbounded dialogue can drift from the task goal
- Harder to predict and audit than structured pipelines

## References

- Li et al., CAMEL: Communicative Agents for Automated Literature Review, 2023 — https://arxiv.org/abs/2308.00352
