# Goal Creator (Passive) Pattern

## Overview

[JSON Data](./goal-creator-passive-pattern.json)

Goal creator (passive) interprets a user's explicit natural-language request to extract and formalize the intended goal before planning begins. The user says what they want; the agent converts this into a structured goal with parameters, constraints, and success criteria. This is the entry point for most agentic workflows.

## When to Use

Use goal creator (passive) when:
- Users provide natural-language requests that need formalization before execution
- You need explicit success criteria to verify task completion
- Misaligned expectations should be caught early, before costly execution
- The agent operates in a human-in-the-loop environment

Avoid when user input is already structured (JSON, form data), when the agent is fully autonomous, or when tasks are exploratory and goals emerge dynamically.

## How It Works

1. The user issues a natural-language request
2. An **intent parser** extracts the core intent and entities from the request
3. A **goal formalizer** converts these into a structured goal with typed parameters and constraints
4. A **confirmation interface** presents the formalized goal back to the user for validation
5. The confirmed goal is passed to the planning and execution pipeline

## Examples

**Flight booking**: User asks to "book a flight to Tokyo next week under $1500"; the agent extracts destination, dates, and budget constraint.

**Bug fixing**: Developer reports "the login button doesn't work on mobile"; the agent extracts error context, affected environment, and expected behavior.

**Report generation**: Business user requests "Q4 sales report for the APAC region"; the agent extracts scope, time range, and delivery format.

## Best Practices

- Confirm extracted goals with the user before beginning execution
- Surface the goal in structured format so the user can correct misunderstandings
- Log the extracted goal alongside the final output for traceability
- Ask clarifying questions when the goal is under-specified

## Common Pitfalls

- Skipping confirmation and executing immediately on ambiguous input
- Asking the user to reformulate rather than doing it for them
- Extracting goals without capturing constraints or success criteria

## Comparison

| Pattern | Trigger |
|---|---|
| Goal Creator (Proactive) | Agent infers goals from context, not from explicit user request |
| Routing | Classify input and dispatch to a fixed handler |
| Plan-and-Solve | Decompose an already-formalized goal into steps |

## References

- Lu et al., *Agent Design Pattern Catalogue* (arXiv:2405.10467) — Passive Goal Creator
