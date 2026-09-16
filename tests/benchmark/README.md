# GENERATE Prompt Benchmark

Measures the quality of the GENERATE-phase system prompt over a fixed case
list (`requirements.jsonl`), so prompt changes are validated against a
baseline instead of vibes.

## Workflow

1. **Baseline**: capture results with the CURRENT prompt

   ```bash
   uv run python tests/benchmark/runner.py --src . --out results_baseline.json
   ```

2. **Change** the prompt (or schemas, or pipeline phases).

3. **Candidate**: capture results in a second checkout/worktree with the
   change applied

   ```bash
   uv run python tests/benchmark/runner.py --src /path/to/changed --out results_candidate.json
   ```

4. **Compare** and decide the merge gate:

   ```bash
   uv run python tests/benchmark/compare.py results_baseline.json results_candidate.json
   ```

Exit codes: `0` gate passed, `1` gate failed, `2` inputs unusable.

## Notes

- Requires a working `config.json` and a reachable LLM endpoint — this is a
  live benchmark, not part of the unit-test suite.
- `--only <case-id>...` / `--limit N` support fast iteration; for the merge
  gate run the full case list in both arms.
- Structural assertions per case live in `tests/regression/`; the rubric for
  manual scoring lives in `RUBRIC.md`.
