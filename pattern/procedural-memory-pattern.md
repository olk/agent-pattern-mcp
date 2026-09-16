# Procedural Memory Pattern

## Overview

[JSON Data](./procedural-memory-pattern.json)

Long-horizon agents that must acquire, store, and reuse executable skills across tasks. After completing a task or task type, the agent extracts a reusable procedure (e.g., a Python function or shell 

## When to Use

- Tasks in these domains: autonomous-task-execution, long-horizon-tasks, code-generation

## How It Works

- Skill Extractor
- Skill Library Index
- Precondition Matcher
- Skill Executor

## Examples

Coding agents that learn reusable functions across tasks

## Best Practices

- Store skills as executable code with docstrings and type hints
- Test each new skill against a golden validation case before committing
- Set a skill library size cap and evict rarely-used skills

## Common Pitfalls

- Skill extraction requires an LLM call per skill
- Precondition matching is non-trivial (what task fits which skill?)

## References

- Wang et al., Voyager: An Open-Ended Embodied Agent with Large Language Models, 2023 — https://arxiv.org/abs/2305.16291
