# Cross-Reflection Pattern

## Overview

[JSON Data](./cross-reflection-pattern.json)

Cross-reflection uses two or more agents or models to provide reflective feedback on each other's plans or outputs before execution. Unlike debate (which is adversarial and converges through argument), cross-reflection is cooperative — agents share critiques to strengthen reasoning before a final decision is made.

## When to Use

Use cross-reflection when:
- Multiple agents with distinct expertise are available
- Plans or outputs can be significantly strengthened by external critique
- You need to surface implicit assumptions before irreversible actions are taken
- A single agent's self-reflection is insufficient to catch blind spots

Avoid when only one agent has relevant expertise, time pressure requires immediate response, or agents do not have sufficient context about each other's domain to critique effectively.

## How It Works

1. A **proposer agent** produces an initial plan or output
2. One or more **critic agents** — each with a distinct perspective — review the proposal and emit critiques
3. The proposer or a **reflection aggregator** integrates the critiques and revises
4. A **resolution gate** determines whether the revised output is sufficient or another round of reflection is needed
5. The loop exits on consensus, vote, or max iterations

## Examples

**Strategic planning**: A planner agent and a risk agent cross-review a proposed course of action before execution begins.

**Research**: Two agents with different source expertise critique each other's literature interpretations before a report is finalized.

**Legal reasoning**: A facts agent and a law agent cross-check each other's analysis before a brief is filed.

## Best Practices

- Structure critique around specific questions — vague criticism without revision paths is noise
- Limit the number of cross-reflection rounds to prevent infinite loops
- Combine with a final synthesizer agent that integrates revisions
- Critics must have a distinct expertise from the proposer

## Common Pitfalls

- Having critics with identical perspectives — no new information is generated
- No mechanism to resolve persistent disagreement — loops indefinitely
- Critique without actionable revision — agents identify problems but do not fix them

## Comparison

| Pattern | Mechanism |
|---|---|
| Multi-Agent Debate | Adversarial; agents argue and revise in response to each other |
| Verifier-Critic | A single evaluator scores output against a rubric |
| Reflection | Single agent critiques its own output |

## References

- Lu et al., *Agent Design Pattern Catalogue* (arXiv:2405.10467) — Cross-reflection
