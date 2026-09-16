# Self-Heal Loop Pattern

## Overview

[JSON Data](./self-heal-loop-pattern.json)

Self-heal loop uses a deterministic verifier to evaluate the output of each execution step and triggers a targeted repair-retry cycle when validation fails. Unlike reflexion (which uses verbal learning from failure feedback), self-heal-loop drives repair through a programmatic evaluator — a test suite, schema validator, or policy check — enabling fully automated correction without LLM-generated critique.

## When to Use

Use self-heal loop when:
- You have a deterministic way to evaluate whether the output is correct
- Failures are detectable programmatically (schema violations, test failures, policy breaches)
- You need fully automated error correction without human intervention
- Tasks have verifiable end states (code that compiles, data matching a schema)

Avoid when no deterministic evaluator exists, the task is inherently subjective, or failures are so rare that the loop overhead is not justified.

## How It Works

1. A **generator agent** produces an initial output
2. A **deterministic verifier** evaluates the output against an objective test or schema
3. If verification fails, a **repair controller** extracts the specific failure and generates a targeted fix
4. The repaired output is reverified — the loop continues until verification passes or a maximum iteration count is reached
5. An **iteration guard** enforces the step budget to prevent infinite loops

## Examples

**Code generation**: An agent writes a Python function; pytest runs against it; failures trigger targeted repair of the specific failing assertion.

**Data pipeline**: Outputs are validated against a JSON schema; invalid rows trigger regeneration with corrected constraints.

**API responses**: JSON output is validated against a response schema; malformed responses are regenerated with corrected structure.

## Best Practices

- Design the verifier to be specific — catch only the failure class, not unrelated properties
- Log each verify-repair cycle so failures are traceable to specific input conditions
- Combine with agent-resumption so interrupted loops can resume from the last checkpoint
- An iteration cap is mandatory to prevent infinite loops

## Common Pitfalls

- Verifier that always passes — the loop becomes an infinite generator
- Repair that introduces a new error not caught by the verifier
- No maximum iteration cap — runaway loops consume budget without converging

## Comparison

| Pattern | Evaluation mechanism |
|---|---|
| Reflexion | Verbal learning from LLM-generated critique |
| Chain-of-Verification | Generate verification questions; check answers against the LLM's own knowledge |
| Evaluator-Optimizer | LLM-based evaluator drives iterative refinement |

## References

- Two-Dimensional Framework for AI Agent Design Patterns (arXiv:2605.13850) — Self-Heal Loop
