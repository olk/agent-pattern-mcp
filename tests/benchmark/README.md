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

# Stage-0 selection benchmark harness

Selection-quality benchmark for the agent-system pipeline
(`tests/benchmark/harness/`). It measures which pattern the analyze phase selects,
how calibrated the selection's confidence is, and what a selection costs — per
scenario, per arm. It never edits `src/`: the pipeline is constructor-injected, so
the runners wrap the seams they hand in (retrieval legs, agent, reasoning client).
Run directories land in `data/benchmark-runs/` (gitignored).

## Modes

| mode    | wiring                                                 | stage attribution |
|---------|--------------------------------------------------------|-------------------|
| offline | scripted agent + single-slug stub retrieval legs       | scripted stubs    |
| live    | real pipeline in-process over probe-wrapped seams      | yes               |
| e2e     | fastmcp Client → deployed stack (`design_agent_system`) | wall times only  |

- **offline** (`harness/offline.py`) — deterministic plumbing proof, zero network.
  The `normal` arm feeds
  each scenario's own domain slug as the only recall-set node (the loader
  cross-checks guarantee the primary wins that set); `--flip` swaps in the first
  decoy slug for a guaranteed miss. A fixture-integrity gate after the run asserts
  normal = hit and flipped = miss for every scenario; any violation exits 2.
  Timings measure harness overhead only — do not read them as pipeline performance.
- **live** — the real pipeline in-process, wired the way `src/server.py` wires it
  (`ConfigManager` → `ServerConfig` → agent → `ReasoningClient` → embedder →
  `AgentPatternPipeline`) with probe wrappers on the agent, the reasoning client,
  and the retriever/reranker call sites. The manifest records a `reasoning_health`
  check; a missing reasoning server degrades per call instead of failing the run.
- **e2e** — black-box: what a deployed stack costs *in total*. One MCP
  `design_agent_system` call per scenario; the tool output (selected patterns,
  `final_pattern_name`, `final_topology`, `is_fallback`, `final_quality_score`) is
  scored, and a failed call is recorded, never dropped.

## Metrics (`harness/scoring.py`, pinned by `harness/selfcheck.py`)

- **hit@1** — `final_pattern_name` is one of the scenario's `acceptable_primary`
  and the run did not fall back; a fallback poisons the hit even with the correct
  name.
- **recall@1..5** — fraction of acceptable primaries inside the top-K analyze-phase
  selected patterns.
- **MRR** — reciprocal rank of the first acceptable primary in the selected
  patterns (0.0 when none appear).
- **topology_hit** — the pipeline's final topology equals the winner's catalog
  topology.
- **acceptable-primary F1** — hit ⇒ P=1, R=1/|A| (|A| = acceptable-primary count);
  a miss scores 0.
- **confidence** — calibration input for Brier/ECE. `score_scenario` defaults it
  to the top-1 blended analyze score (0.5 when unavailable), but every mode then
  replaces it with `final_quality_score/100`; a failed run carries 0.0.
- **Brier / ECE(10) / reliability curve** — confidence-vs-hit diagnostics over 10
  equal-width bins.
- **risk-coverage curve + elbow** — miss rate over confidence-sorted coverage
  prefixes; AURC (mean per-prefix risk, `None` for an empty arm) and risk@80/90/100.
- **percentiles** — p50/p95 via inclusive quantiles; below 4 samples they are
  `None` plus an explanatory note, never silently 0.
- **Wilson 95% interval** on hit rates; an exact paired sign test and a Newcombe
  paired-difference CI are reported as compare diagnostics.

## Pre-registered A/B decision rule (`harness/compare.py`)

> candidate wins iff holdout p95 e2e improves ≥ 15% AND candidate holdout hit rate
> ≥ the baseline HOLDOUT hit rate's Wilson 95% lower bound.

Fewer than 4 paired holdout scenarios, or an undefined holdout p95 (no measured
`e2e_ms` on either arm, or a zero baseline p95) ⇒ **inconclusive** — an unmeasured
speed leg is never scored as a candidate loss. Runs are paired by
`<scenario_id>#<repeat>`; the speed leg is each artifact's run-boundary `e2e_ms`
(an `e2e.http` record is the fallback for artifacts written before that field
existed). Every mode measures that wall clock, so offline and live arms carry a
speed leg too; at this corpus size holdout holds 8 pairs, above the 4-pair
minimum.

Exit codes: `0` candidate win or inconclusive, `1` candidate loss, `2` refusal.
`compare` refuses: a run with `aborted.json`, a run without `manifest.json`,
mismatched corpus `sha256` or mode, disjoint scenario key sets, and completed arms
that contain failed scenario runs. `--allow-mismatch` overrides the mismatch and
failed-run refusals (recorded in the output, at your own risk).

## Failure policy and warmup

By default a scenario whose run raises is **recorded, not fatal**: the arm
continues, the scenario's score is a zeroed miss (no hit, zero recall/MRR/F1,
confidence 0), its artifact carries `provenance.error`, it counts in every rate,
and it appears in `summary.failures` and the report's "Failed scenario runs"
table — one stochastic provider fault must not burn a live arm. `--fail-fast`
restores abort-on-first-failure: the exception escapes, the run writes
`aborted.json` instead of a summary, and `compare` refuses the run.

Offline adds a fixture-integrity gate on top: a failed run counts as a miss in
both arms, so a broken fixture cannot hide (a `normal`-arm failure violates the
gate and exits 2).

Live mode runs the first scenario once **untimed** before the arm so caches and
subprocesses are hot: its provenance (stage counts, wall ms, error if any) lands
in `warmup.json`, and its records sit before every scenario's attribution window,
so they never enter an arm summary. A warmup failure is recorded in
`warmup.json` and does not abort the arm (unless `--fail-fast`). `--no-warmup`
skips it entirely: `warmup.json` then records
`{"enabled": false, "measured": false, "reason": "--no-warmup"}`.

Every live run ends with `shutdown_live_components` (`harness/live.py`), called
from a `finally` so it also runs under `--fail-fast`. It closes the
`ReasoningClient` and disposes litellm's cached async HTTP clients *inside* the
live event loop, then drops the cache. This matters because each repeat gets its
own `asyncio.run` loop: litellm's OpenAI-compatible client is aiohttp-backed, so
an undisposed one is bound to an already-closed loop and cannot be freed by
litellm's atexit hook (which runs on a fresh loop) — aiohttp then prints
`Unclosed client session` / `Unclosed connector` at interpreter exit, and
`REPEAT>1` reuses a client pinned to a dead loop.

## Dead generator provider (fail-fast + runbook)

A permanently dead generator provider aborts the live arm within seconds of
first detection instead of burning the arm on zeroed scenarios:

- **Preflight**: before the warmup scenario, `run_live_corpus` probes the
  generator with one direct `litellm.acompletion` call, retries disabled
  (`preflight_generator`, `harness/live.py`). If it fails with a permanent
  provider fault, the arm aborts with `ProviderDeathError` before warmup.
  The probe bypasses llama-index's tenacity cascade (which would retry a
  429-flavored "no credits" fault for many minutes and can re-label it), so a
  dead provider is detected in seconds. Transient faults (timeout, single 429,
  parse slip) never abort the preflight.
- **Mid-run**: a scenario failure whose error text matches a permanent-fault
  signature (`is_permanent_provider_death`, `harness/live.py`) raises
  `ProviderDeathError` on first match, regardless of `--fail-fast`. Stochastic
  faults (parse errors, timeouts, transient 429s) keep the per-scenario
  tolerance described above.
- **Exit**: the CLI prints `ABORTED — generator provider permanently failed`,
  writes `aborted.json` (compare refuses aborted runs), and exits with code 3.
  Fix hint: top up the account or switch `GENERATOR_*` env (below).

Signatures are phrase-anchored (`insufficient balance`, `no credits remaining`,
`insufficient_quota`, `invalid_api_key`, `incorrect api key`,
`api key not valid`, `authentication_error`, `authorized_error`, `login fail`,
`unauthorized`, `permission denied`, `account is depleted`); bare numeric
tokens (`401`, `403`) are deliberately not matched because request ids contain
them — MiniMax's auth rejection, for instance, arrives as
`litellm.APIConnectionError ... "type":"authorized_error" ... (1004)`, and
llama-index *retries* that class, so an unclassified auth fault would hang the
arm in the retry cascade instead of aborting it. A new provider's
permanent-death phrase goes into `PROVIDER_DEATH_SIGNATURES` plus a `dead` case
in `anchor_provider_death` (`harness/selfcheck.py`) in the same change.

Runbook when the arm aborts:

1. **The generator account is out of credit.** The default provider is MiniMax
   (`minimax/MiniMax-M2.7`, key from `MINIMAXAI_API_KEY`); top up at
   platform.minimaxi.com. For DeepSeek (`GENERATOR_PROVIDER=deepseek`), top up
   at platform.deepseek.com (error docs: 402 = insufficient balance, fix = top
   up) and verify funding before rerunning:

   ```sh
   curl https://api.deepseek.com/user/balance -H "Authorization: Bearer $DEEPSEEK_API_KEY"
   ```

   (`is_available: true` means funded.)
2. **Or switch provider via env** — nothing is hardcoded:

   ```sh
   GENERATOR_PROVIDER=deepseek \
   make benchmark-live LIMIT=1 OUT=benchmarks/deepseek-check FORCE=1
   ```

   The `benchmark-live` recipe keys its generator defaults off the provider:
   `minimax` (default) → `minimax/MiniMax-M2.7`, `https://api.minimax.io/v1`,
   `GENERATOR_API_KEY=$MINIMAXAI_API_KEY` and
   `RETRIEVAL_USE_LEAN_WIRE_SCHEMA=true` (MiniMax emits malformed JSON on the
   fat `AgentSystemDesignResponse`, known from the 2026-09-27 live runs);
   `deepseek` → `deepseek-flash`, `https://api.deepseek.com/v1`,
   `GENERATOR_API_KEY=$DEEPSEEK_API_KEY`, lean wire schema off. Every value is
   still overridable individually, and any other provider falls through to the
   `{env:...}` defaults in `config/config.json` (the key must then be exported
   as `GENERATOR_API_KEY`).

`--fail-fast` behavior is unchanged.

## Stage attribution

Each scenario artifact carries only the stage records that scenario produced (a
per-scenario window over the shared recorder), an aggregated `stages` table, and
the latency block below. **`stage` is the latency bucket, `op` is the seam method
that produced the record** — the same split the sibling harness uses, so buckets
are comparable across repos:

| stage | op | what it times |
|---|---|---|
| `build.embed` | `AgentPatternPipeline.warmup_indexes` | one index build per run; excluded from per-scenario totals |
| `retrieval.fused` | `HybridPatternRetriever.retrieve` | fused hybrid retrieval (legs run inside) |
| `reranking` | `SafeTEIReranker.postprocess_nodes` | TEI rerank of the fused node set |
| `llm.weights` | `AgentSystemArchitect.generate_structured` | requirements-weight extraction call |
| `llm.generate` | same | design-schema generate call (one record per call; retries add records) |
| `llm.evaluate` | same | evaluation call |
| `llm.draft` | same | ThoughtGenerator draft call (reasoning traces) |
| `reasoning.{analyze,generate,evaluate}` | `ReasoningClient.run_pre_llm` | per-phase reasoning pre-LLM calls |
| `e2e.http` | `fastmcp_client.call` | the MCP wire call (e2e mode) |

Deviation from the sibling: it splits retrieval into `retrieval.dense` /
`retrieval.bm25` and leaves rerank unattributed. Here the legs run inside the
fusion retriever (not reachable as separate seams), so `retrieval.fused` is the
observable seam and the rerank *is* attributed — the frame accounting below makes
that safe.

Two seams nest inside another record's wall time: the reranker runs inside the
fused retriever call, and the reasoning block's `generate_structured` calls run
inside the reasoning pre-LLM call. The enclosing record therefore reports an
**exclusive** `duration_ms` (raw wall kept in `meta.inclusive_ms`, nested share in
`meta.nested_ms`), so the stage sum never exceeds the measured wall clock.

Per-scenario latency block: `e2e_ms` (the run-boundary wall clock, deliberately
*not* a stage record), `stages` (`count`, `failures`, `total_ms`, `ops`, plus
`p50_ms`/`p95_ms` with the <4-sample rule), `stage_total_ms` (Σ over non-build
stages) and `residual_ms` = `e2e_ms − stage_total_ms`, the honest unattributed
remainder. A negative residual means the seams overlapped beyond the frame
accounting; `residual_note` then says so. `summary.json` carries a `latency` block
with the run-wide `e2e_ms` and `residual_ms` distributions, the aggregated stage
table, `negative_residual_scenarios` and a per-scenario row list.

Provider fault class to expect from a thinking model: a tool call that arrives
with **empty or unparseable arguments** (`overview`/`summary` "Field required",
`input_value={}`) because the model answered in prose instead of the call. The
prompts route the analysis into `overview.reasoning` / `summary.reasoning` so
the prose channel does not exist, and `src/validation.py` adds a repair clause
for this exact shape ("arguments were empty or not valid JSON — emit the
complete object again, in ONE call"). Measured on the real prompts: EVALUATE
4/12 → 0/12 empty-argument calls; GENERATE single-shot 6/8, production path
(with the self-healing retries) 6/6.

Measurement caveat: the pipeline's reasoning client memoises traces for the
`analyze` and `generate` phases (`_CACHEABLE_PHASES` in
`src/reasoning/client.py`) and the live arm builds one client for the whole
corpus. After the first scenario, `reasoning.{analyze,generate}` rows therefore
read as ~0 ms for identical inputs — the reasoning cost of those phases is only
visible on the first scenario that pays it (or the warmup, which is untimed).
`reasoning.evaluate` is not cached. Compare like with like, or force a cold
client per scenario before treating those two rows as a cost measure.

## CLI

```sh
# run one arm (writes data/benchmark-runs/<run-id>/)
uv run python -m tests.benchmark.harness.main run --mode {offline,live,e2e} [flags]
# A/B verdict over two run directories
uv run python -m tests.benchmark.harness.main compare BASELINE_DIR CANDIDATE_DIR [--allow-mismatch]
# draft scenarios from run evidence (placeholders for human review, never auto-committed)
uv run python -m tests.benchmark.harness.main draft --run-dir DIR \
    [--run-dir DIR ...] [--output PATH] [--validate]
# metric/fixture self-check (separate module)
uv run python -m tests.benchmark.harness.selfcheck
```

`run` flags (defaults in parentheses): `--mode` (`offline`), `--limit`,
`--repeat` (1), `--split` (`all`, `train`, `holdout` — every mode), `--flip`
(offline), `--fail-fast`,
`--no-warmup` (live), `--log-level` (`warning`; applied to the root logger, its
handlers, and `bm25s`, which re-pins itself at import), `--output-root`
(`data/benchmark-runs`), `--call-timeout` (e2e, default 1500 s), `--mcp-url` (e2e;
beats the `BENCH_MCP_URL` env var, default `http://localhost:8061/mcp`),
`--out` (write the run into exactly this directory, sibling-style: artifacts
land directly in it, no generated child), `--force` (allow writing into a
non-empty `--out`; otherwise the run refuses with exit 2), `--dry-run` (load and
schema-validate the corpus, run nothing).

An offline run whose integrity gate trips exits 2; `compare` exits 0/1/2 as above.

## Run directory

`data/benchmark-runs/bench-<mode>-<utcstamp>-<rand>/`:

- `manifest.json` — run id, mode, UTC timestamp, `corpus_sha256` +
  `scenario_set_sha256`, effective config, env snapshot (unprefixed names +
  secret *presence* flags, never values), Python/platform fingerprint, wall secs
- `summary.json` — per-arm summary (metrics above, plus `failures`) and a
  `latency` block: `e2e_ms` / `residual_ms` distributions, `negative_residual_scenarios`
  with its `residual_note`, and `per_scenario` rows (`e2e_ms`,
  `stage_total_ms`, `residual_ms` per scenario run)
- `report.md` — mode note, stage table (bucket, n, failures, total, p50, p95, ops),
  per-arm metrics, failure table, fixture-integrity section
- `scenarios/<id>#<repeat>.json` — one artifact per scenario run: score fields,
  `provenance`, this scenario's raw `stage_records`, and the latency block
  (`e2e_ms`, `stages`, `stage_total_ms`, `residual_ms`, `residual_note`)
- `warmup.json` — live only: the warmup scenario's provenance
- `aborted.json` — written instead of a summary when the run aborts

## Corpus

`harness/scenarios/seed.json`: 20 scenarios, 2 per pattern category over all 10
categories. Each scenario carries `scenario_id`, `category`, `split`,
`requirements`, `domain`, `acceptable_primary` (≥1, winner first),
`decoy_domains` (≥2), and `scripted_weights` (the seven quality-attribute keys);
`scenarios/scenario.schema.json` pins that shape, validated on load by a
hand-rolled Draft-07-subset validator (the repo has no `jsonschema` dependency).

The family is the category, so the train/holdout split is category-disjoint:
holdout = {observability, safety_control, tool_use, research_synthesis}
(8 scenarios); every other family is train (12).

Beyond the schema, the loader cross-checks the seed against the pattern catalog:
duplicate `scenario_id`s; unknown `acceptable_primary` slugs; the winner's catalog
category must equal the scenario category; `domain` must be a `suitable_domains`
value of the winner; every decoy slug must carry none of the acceptable primaries'
categories; no category may span both splits. Every manifest records the corpus
fingerprint (`corpus_sha256` over the sorted catalog files, plus a
canonical-JSON `scenario_set_sha256`) — the pins `compare` checks.

`selfcheck` is the gate that pins the metric formulas: hand-computed anchors for
every statistic above, seed validation (accepts the seed, rejects tampered
variants), the offline fixture, and the compare verdicts. Exit 0 means the harness
numbers can be trusted; any anchor failure exits 2.

No `test_*.py` lives here: pytest never collects the harness; `selfcheck` is its
own gate.

## Make targets

```sh
make benchmark-selfcheck                        # metric + fixture anchors (no services)
make benchmark-offline [LIMIT=n] [FLIP=1] [REPEAT=n]        # deterministic, no network
make benchmark-sidecars-up                      # TEI on 127.0.0.1:18081/18082
make benchmark-live LIMIT=n [REPEAT=n] [SPLIT=holdout] [NO_WARMUP=1] [LOG_LEVEL=info] \
    [FAIL_FAST=1] [OUTPUT_ROOT=dir]  # needs sidecars + MINIMAXAI_API_KEY
make benchmark-e2e LIMIT=n [SPLIT=holdout] [CALL_TIMEOUT=s] [MCP_URL=url]  # needs a stack
make benchmark-draft RUN_DIR=dir [RUN_DIR2=dir] [RUN_DIR3=dir]
make benchmark-compare A=dir B=dir [ALLOW_MISMATCH=1]
```

`SPLIT`, `REPEAT`, `LOG_LEVEL`, `FAIL_FAST`, `NO_WARMUP`, `OUT` and `FORCE` are
pass-through make variables for the three run modes; anything not set is simply
not passed, so the CLI defaults apply. `OUT=benchmarks/base FORCE=1` therefore
writes one run into that exact directory (refused without `FORCE` when it already
holds a run).

Environment requirements:

- **offline / selfcheck** — nothing: scripted stubs, zero network (the offline
  reranker URL is an `offline-invalid` tripwire — a regression that re-enables
  reranking fails loudly instead of silently changing semantics).
- **live** — `make benchmark-sidecars-up` first (an additive compose override
  publishing the TEI embedder on `127.0.0.1:18081/v1` and the reranker on
  `127.0.0.1:18082`), plus a generator key: the recipe defaults to MiniMax
  (`GENERATOR_PROVIDER=minimax`, `GENERATOR_MODEL=minimax/MiniMax-M2.7`,
  `GENERATOR_BASE_URL=https://api.minimax.io/v1`, `GENERATOR_API_KEY` from
  `MINIMAXAI_API_KEY`); `GENERATOR_PROVIDER=deepseek` switches the whole set to
  DeepSeek, and any `GENERATOR_*` value already in the environment wins. It
  pins `CONFIG_PATH` to the repo `config/config.json` and points
  `REASONING_*_CMD` at the globally installed npm reasoning servers when present;
  without them the pipeline degrades per call (visible as `reasoning_health` in
  the manifest).
- **e2e** — a deployed MCP server at the endpoint (`MCP_URL` / `BENCH_MCP_URL` /
  default `http://localhost:8061/mcp`).
