# Orchestrator Workers Pattern

## Overview

[JSON Data](./orchestrator-workers-pattern.json)

Tasks where subtasks cannot be predicted in advance (for example, the number of files to change depends on the codebase): a central LLM dynamically decomposes and delegates, then synthesizes.

## When to Use

- Tasks in these domains: code generation, complex reasoning, multi agent systems
- Refactor across an unknown file set

Avoid when: Subtasks are enumerable upfront

## How It Works

- Orchestrator
- Worker Pool
- Task Spec Generator
- Synthesizer

## Examples

**Refactor across an unknown file set**: A scenario where this pattern's approach is well-suited to the task.

**Open-ended analysis with unknown subtopics**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Provide few-shot decomposition examples
- Give workers scratchpads
- Define a conflict resolution policy

## Common Pitfalls

- Decomposition quality bounds everything
- Coordination overhead similar to supervisor-worker
- Unpredictable cost

## Comparison

| Pattern | Mechanism |
|---|---|
| Supervisor-Worker | Hierarchical routing |
| Orchestrator-Workers | Dynamic subtask delegation |
| Multi-Agent Debate | Adversarial stress-testing |

## References

- Agent Patterns library