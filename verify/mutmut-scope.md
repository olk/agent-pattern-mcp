# mutmut Scope Ledger — Tier A (initial)

> Companion to `verify/mutmut-thresholds.toml`, `verify/mutmut-baseline.json`,
> and `verify/mutmut-equivalents.md`. Doctrine: the mutation scope is the
> critical 5–10% of the tree — pure decision logic whose mutants have cheap,
> decisive kill oracles. Scope changes must edit this ledger in the same PR
> that edits `[tool.mutmut] do_not_mutate` (AGENTS.md rule).

## In scope (mutated)

| Module | Oracle(s) | Notes |
|---|---|---|
| `src/text_validation.py` | `tests/unit/test_text_validation.py`, `tests/unit/test_text_validation_internals.py`, `tests/verification/test_text_validation_properties.py` | Tier-A decision engine (strip window / verdict kinds); the V-1..V-6 oracles kill regex/branch/clamp mutants |
| `src/config_expansion.py` | `tests/unit/test_config_expansion.py`, `tests/verification/test_config_properties.py` | CE-1..CE-6 kill regex-group and default-branch mutants |
| `src/patterns/loader.py` | `tests/unit/test_pattern_loader.py`, `tests/verification/test_loader_properties.py` | LD-1..LD-6 kill slug-normalization and filter mutants over the real 61-pattern catalogue |
| `src/design_normalization.py` | `tests/unit/test_normalization.py`, `tests/verification/test_normalization_idempotence.py` | N-1..N-4 dedup/idempotence over the agent contract keys |
| `src/tools/jobs.py` | `tests/unit/test_jobs.py` (exhaustive 4×5 guarded transition matrix), `tests/verification/test_jobs_properties.py` | W0-1 guard automaton; J-1..J-4 |
| `src/validation.py` | `tests/unit/test_validation.py`, `tests/verification/test_jobs_properties.py` (E5 retry oracle) | self-healing retry bounding + error formatting |

## Deferred — awaiting dedicated kill oracles (scope growth backlog)

`src/config.py`, `src/reasoning/config.py`, `src/tools/*` (per-tool output
mapping), `src/patterns/{nodes,retriever,embedder,safe_tei_rerank}.py`,
`src/pipeline.py` (model-checked by the L4 fizz specs instead),
`src/errors.py`, `src/agent.py`.

Growth procedure (mirrors architecture-pattern-mcp's ratchet):
1. Write the dedicated internals/property kill oracle for the module.
2. Move the module out of `do_not_mutate` in the same PR.
3. Run `make test-mutations`, triage survivors (kill or record equivalents).
4. `make regen-mutmut-baseline` and update the ledger row.

## Permanent — excluded by design

Entry points and wiring (`src/main.py`, `src/__main__.py`, `src/server.py`,
`src/tools/__init__.py`), declarative schemas (`src/schemas/*`,
`src/reasoning/{config,schemas,__init__}.py`), prompt/content modules
(`src/prompts/*`, `src/mcp_prompts/*`), resources (`src/resources/*`) —
no branchable decision content, oracles would be vacuous.
