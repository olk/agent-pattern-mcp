# GENERATE Prompt Benchmark — Scoring Rubric

Scores each benchmark result on a 1–5 scale per dimension. The overall case
score is the mean. Compare arms with `compare.py`; treat quality regressions
as merge blockers even when paired significance is not reached (n is small).

## Dimensions

1. **Structural integrity (weight 2×)**
   - 5: All relationship source/target and contract references resolve; no
        dangling ids anywhere.
   - 3: ≤1 dangling reference; contracts structurally valid.
   - 1: Multiple dangling references or malformed contract lists.

2. **Requirement coverage**
   - 5: Every stated requirement maps to at least one agent's
        responsibilities; no invented requirements.
   - 3: Core requirements covered; peripheral ones missing.
   - 1: Key requirements unaddressed or hallucinated ones added.

3. **Topology fidelity**
   - 5: Design embodies the requested topology (control flow, coordination
        and escalation match the pattern's canonical shape).
   - 3: Correct topology label with partial shape fidelity.
   - 1: Label-only compliance — a flat loop dressed up as the topology.

4. **Scoring honesty**
   - 5: quality_attributes are 10-scale strings; balanced designs score 5–7;
        9+ only with explicit exceptional justification in overview.reasoning.
   - 3: Format valid but mild inflation.
   - 1: All-10s, non-numeric values, or missing keys.

5. **Contracts quality**
   - 5: tool_contracts/shared_state_models/message_contracts populated only
        where the requirements imply them; shared entities marked is_shared.
   - 3: Valid but speculative entries.
   - 1: Invented contracts for hypothetical future needs.

## Gate (compare.py)

- `overall_quality`: candidate must improve significantly (paired
  permutation test, α=0.05) to pass the merge gate.
- `attempts`, `dangling_references`: must not regress.
- `validation_success`, `qa_format_valid`: candidate rate ≥ baseline rate.
