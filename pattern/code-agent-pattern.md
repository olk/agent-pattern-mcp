# Code Agent Pattern

## Overview

[JSON Data](./code-agent-pattern.json)

Agents that write and execute code to accomplish tasks, using the execution results as observations that ground subsequent reasoning. The agent produces code (not free-form text) as its primary action

## When to Use

- Tasks in these domains: code-generation, data-analysis, autonomous-task-execution

## How It Works

- Code Generator
- Sandbox Executor
- Output Parser
- State Manager

## Examples

Autonomous bug fixing with test-driven feedback

## Best Practices

- Use a fresh sandbox for each code execution to avoid state pollution
- Set resource limits (CPU, memory, time) on code execution
- Parse and validate code output programmatically before proceeding

## Common Pitfalls

- Requires a reliable code execution environment
- Code generation quality depends heavily on the model's coding capability

## References

- Yang et al., SWE-Agent: Agentic LLM for Software Engineering, 2024 — https://arxiv.org/abs/2405.15793
- Anthropic, Claude Computer Use, 2024 — https://www.anthropic.com/news/claude-computer-use
