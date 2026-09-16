# Decision Log Pattern

## Overview

[JSON Data](./decision-log-pattern.json)

Decision log persists the agent's reasoning trace alongside its actions so that post-hoc review, debugging, or compliance auditing can explain why a particular output was produced. Action-only logs leave reviewers unable to reconstruct the agent's reasoning — the decision log provides the causal chain.

## When to Use

Use decision log when:
- Compliance or regulation requires explaining agent decisions
- Debugging production issues requires tracing outputs back to reasoning steps
- You need to distinguish a bad decision from a bad outcome during incident analysis
- Multiple stakeholders need to audit agent behavior

Avoid when no requirement to explain decisions exists, privacy constraints prohibit retaining reasoning traces, or the agent loop is so fast that logging adds meaningful overhead.

## How It Works

1. As the agent executes, a **decision logger** records each reasoning step and its outcome to an append-only ledger
2. Each entry links an action to the specific context (evidence, constraints, alternatives considered) that caused it
3. The ledger is indexed by request ID and decision type for efficient post-hoc query
4. Reviewers can reconstruct the agent's reasoning path without access to the live context window

## Examples

**Compliance audit**: Reconstruct why an agent approved or rejected a loan application by tracing the decision log entries that led to the outcome.

**Incident response**: Trace a production failure back to the specific tool call and reasoning step that produced the faulty output.

**Customer dispute**: Show exactly what information the agent based its response on, including which sources were consulted and which were rejected.

## Best Practices

- Link each action record to the specific reasoning step that caused it
- Distinguish key decisions from routine steps — not every token needs a log entry
- Index logs by request ID and decision type for efficient post-hoc retrieval
- Ensure logs are append-only — the agent cannot rewrite its own history

## Common Pitfalls

- Logging actions without corresponding reasoning — leaves no explanation
- Rewriting reasoning logs after the fact — destroys auditability
- Retaining logs without any review process or query mechanism

## Comparison

| Pattern | Focus |
|---|---|
| Conversational Memory | Carry context across turns within a session |
| Agent Resumption | Full execution state for crash recovery |
| Decision Log | Reasoning trace for audit and explanation |

## References

- Agent Patterns Catalog, *Decision Log* pattern
- Continuity Ledger, *Provenance-Carrying Context-Control Runtime for LLM Agents*
