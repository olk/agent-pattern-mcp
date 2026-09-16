# Goal Creator (Proactive) Pattern

## Overview

[JSON Data](./goal-creator-proactive-pattern.json)

Goal creator (proactive) infers goals proactively from context — not from an explicit user request but from environmental signals, historical patterns, or implicit cues. The agent acts as a proactive assistant, anticipating what the user needs before being asked, based on situation awareness and learned preferences.

## When to Use

Use goal creator (proactive) when:
- The agent has access to contextual signals (calendar, history, sensors, ambient data)
- Proactive assistance improves user experience for the target domain
- Low-stakes suggestions can be confirmed before irreversible actions
- You want to reduce the number of explicit commands a user needs to issue

Avoid when the domain requires explicit user authorization before any action, inference signals are unreliable, or privacy constraints prohibit the contextual data needed.

## How It Works

1. A **context monitor** observes environmental signals (calendar, chat history, sensor data, usage patterns)
2. An **inference engine** identifies patterns that suggest a potential need or goal
3. A **hypothesis ranker** scores inferred goals by confidence and urgency
4. A **confirmation gate** presents high-confidence proactive suggestions to the user for confirmation
5. On confirmation, the inferred goal is formalized and passed to the execution pipeline

## Examples

**Calendar assistant**: Detects from meeting notes that a follow-up task was created and proactively offers to schedule it.

**Research assistant**: Notices the user has been reading papers on topic X and proactively surfaces related work.

**DevOps agent**: Detects an unusual traffic pattern and proposes a scaling action before being asked.

## Best Practices

- Start with low-stakes, easily revocable proactive suggestions
- Require confirmation for any action that has external side effects
- Track user feedback on proactive suggestions to improve inference over time
- Make the inference chain explainable — the agent should be able to say why it inferred this goal

## Common Pitfalls

- Acting on misinferred goals without confirmation — can be disruptive
- Proposing actions the user has previously declined
- Inferring from a single ambiguous signal without corroboration

## Comparison

| Pattern | Trigger |
|---|---|
| Goal Creator (Passive) | User issues an explicit natural-language request |
| Storm | Multi-perspective research driven by a topic, not an explicit goal |
| Plan-and-Solve | Decompose an already-formalized goal into steps |

## References

- Lu et al., *Agent Design Pattern Catalogue* (arXiv:2405.10467) — Proactive Goal Creator
