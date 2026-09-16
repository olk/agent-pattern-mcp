# Metagpt Sop Pipeline Pattern

## Overview

[JSON Data](./metagpt-sop-pipeline-pattern.json)

Multi-agent systems that mimic software team SOPs by assigning agents to sequential pipeline stages (e.g., requirements → architecture → coding → testing → review). Unlike role-play (autonomous dialog

## When to Use

- Tasks in these domains: code-generation, research-reports, content-generation

## How It Works

- Stage Specifier
- Role Agent
- Stage Output Schema
- Pipeline Orchestrator

## Examples

Automated code generation with code-review pipeline

## Best Practices

- Limit each stage to a single well-defined role
- Validate stage outputs against a schema before passing to the next stage
- Log each stage's input, output, and execution time for cost attribution

## Common Pitfalls

- Fixed pipeline cannot adapt to unexpected task structure
- Sequential execution limits parallelism

## References

- Hong et al., MetaGPT: Meta Programming for Multi-Agent Collaboration Framework, 2023 — https://arxiv.org/abs/2308.00352
