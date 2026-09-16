# Agent Resumption Pattern

## Overview

[JSON Data](./agent-resumption-pattern.json)

Agent resumption persists agent execution state so that long-running tasks survive process restarts, container redeployments, user disconnects, or infrastructure events. The agent resumes from a named checkpoint rather than retrying from scratch or duplicating side effects.

## When to Use

Use agent resumption when:
- Tasks are long enough that restarts or disconnects would lose meaningful work
- Side effects must not be duplicated on replay (idempotency required)
- You need pause points for human review or escalation mid-task
- The agent operates in an environment where restarts are common

Avoid when tasks complete in seconds, when retrying from scratch is acceptable, or when downstream services cannot make their operations idempotent.

## How It Works

1. The agent runs in a loop, and at meaningful boundaries (goal milestones), a **checkpoint manager** serializes state to durable storage
2. State includes the current goal, working memory, partial outputs, and pending tool calls — all keyed by a run ID
3. If the process dies, the **resume controller** reloads the checkpoint and continues from the next step
4. Side-effect targets receive idempotency keys so that replayed calls are deduplicated

Two production approaches: **deterministic replay** (re-execute skipping logged side effects) and **snapshot restoration** (restore serialized agent state directly).

## Examples

**Research scraping**: A 40-minute scrape-and-summarize run survives a container restart and continues from the last completed source.

**Code migration**: A multi-hour refactoring task resumes after a deployment without reprocessing already-migrated files.

## Best Practices

- Checkpoint at goal milestones, not at arbitrary iteration counts
- Distinguish durable state (keep across restarts) from ephemeral state (recompute)
- Validate that resumed runs re-check volatile external state (queue positions, approvals)
- Ensure all downstream side-effect targets accept idempotency keys

## Common Pitfalls

- Keeping all state in memory with no durable checkpoint
- Checkpointing at arbitrary points rather than meaningful boundaries
- Resuming without revalidating external state that may have drifted

## Comparison

| Pattern | Mechanism |
|---|---|
| Conversational Memory | Short-term context carryover within a session |
| Decision Log | Persists reasoning trace for audit; does not enable resumption |
| Agent Resumption | Full execution state persistence for crash recovery |

## References

- Agent Patterns Catalog, *Agent Resumption* pattern
- Crab, *A Semantics-Aware Checkpoint/Restore Runtime for Agent Sandboxes* (arXiv:2604.28138)
