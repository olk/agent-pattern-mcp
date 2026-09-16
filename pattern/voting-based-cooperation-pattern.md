# Voting Based Cooperation Pattern

## Overview

[JSON Data](./voting-based-cooperation-pattern.json)

Multi-agent systems where several agents produce candidate answers or evaluations on the same task and the system needs to return a single decision that reflects the group's collective judgment rather than any individual agent's output. Unlike debate, agents do not argue with each other — they vote, and a tallying mechanism produces the final outcome.

## When to Use

- Tasks in these domains: multi agent systems, high stakes outputs, regulated domains
- Medical triage: three specialist agents recommend tests; five generalist voters rank and tally

Avoid when: Expertise is concentrated in one agent and others have no meaningful signal

## How It Works

- Voter Agent
- Ballot Coordinator
- Tally Engine
- Audit Trail Logger

## Examples

**Medical triage: three specialist agents recommend tests; five generalist voters rank and tally**: A scenario where this pattern's approach is well-suited to the task.

**Code review: multiple agents flag different vulnerability classes; a coordinator tallies by severity**: A scenario where this pattern's approach is well-suited to the task.

## Best Practices

- Use weighted voting where voter expertise is known (role-based weights)
- Define explicit tie-breaking rules before deployment
- Log the full ballot (who voted what) alongside the outcome for accountability

## Common Pitfalls

- Majority rule can entrench dominant agents regardless of expertise
- Agents may vote strategically rather than truthfully
- No mechanism for agents to revise beliefs based on others' evidence
- Tie-breaking rules require explicit design

## Comparison

| Pattern | Mechanism |
|---|---|
| Supervisor-Worker | Hierarchical routing |
| Orchestrator-Workers | Dynamic subtask delegation |
| Multi-Agent Debate | Adversarial stress-testing |

## References

- Agent Patterns library