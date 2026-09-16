# Self Discovery Pattern

## Overview

[JSON Data](./self-discovery-pattern.json)

Novel problems where no single fixed reasoning strategy works; the agent discovers and composes its own reasoning structure from a catalogue of modules before solving.

## When to Use

- Tasks in these domains: complex reasoning, code generation, data analysis
- Olympiad-style math problems

Avoid when: Task family is homogeneous (use a fixed chain)

## How It Works

- Module Catalogue
- Structure Selector
- Reasoning Executor
- Answer Synthesizer

## Examples

**Olympiad-style math problems**: A scenario where this pattern's approach is well-suited to the task.

**Logic puzzles**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Log which modules were chosen
- Validate the structure before execution
- Limit the catalogue to about ten modules

## Common Pitfalls

- Extra selection phase adds cost
- Module catalogue must be curated
- Harder to debug than fixed chains

## Comparison

| Pattern | Mechanism |
|---|---|
| Chain-of-Thought | Step-by-step decomposition |
| Self-Discovery | Adaptive reasoning module selection |
| LATS | Tree search with environment feedback |

## References

- Wang et al., *Self-Discover: Large Language Models Self-Compose Reasoning Structures*, 2023