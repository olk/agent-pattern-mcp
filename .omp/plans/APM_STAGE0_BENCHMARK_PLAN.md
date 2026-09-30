# Plan: `apm-stage0-benchmark` — Stage-0 Selection Benchmark Harness for agent-pattern-mcp

Port of the reference harness (`../design-pattern-mcp-local` @ `25cbfba`, "Stage-0 selection benchmark with stage attribution and A/B comparison"), adapted to agent-pattern-mcp's seams. **Equivalent features, not a literal copy.**

## Context

agent-pattern-mcp is an MCP server (FastMCP) that recommends agent patterns: `analyze` (retrieval → LLM `RequirementWeights` → deterministic `_score_patterns`) → `design_loop` (generate → evaluate → retry × `max_tries`). The goal is a benchmark instrument that measures **selection quality + stage-attribution timings + A/B comparison** across three modes (offline scripted / live in-process / e2e over the wire), with pre-registered verdicts, paired comparisons, and fixture-integrity self-checks — mirroring the reference harness's modes/metrics/protocol.

**Hard constraints (repo rules + design decisions):**
- **Zero edits to `src/`** → no `.fizz` verification-program obligations, no mutmut ratchet risk, no mypy-strict impact (scope is `src/` only).
- **Zero edits to `pyproject.toml`** → harness imports only declared deps (`fastmcp`, `llama-index-core`, `pydantic`, `numpy`, `httpx`, `click`) + stdlib + `src`. **`jsonschema` is NOT a dependency here (unlike the reference) → scenario schema validation is hand-rolled** (Draft-07 subset: `type`, `required`, `enum`, `minLength`, `minItems`, `additionalProperties` — sufficient for a schema we author).
- Harness lives in `tests/benchmark/harness/` — **no `test_*.py`, no `conftest.py`** in that tree → pytest never collects it (reference-verified pattern). Existing `tests/benchmark/{runner.py,compare.py,requirements.jsonl}` (GENERATE-quality instrument) stay untouched.
- Gates that must stay green: `make check-lint` (ruff, repo-wide incl. tests, line-length 120, rule set E/W/I/UP/B/C4/DTZ/T10/ISC/PIE/PT/RET/SIM/ARG/PL/TRY/RUF), `make check-static-typing`, `make check-deadcode` (scans `src examples whitelist.py` only — harness invisible), `make check-depcheck` (`deptry .`, `extend_exclude=["verify"]`, `known_first_party=["src"]`), `make test-unit`.
- Ruff `ARG` (unused args) and `PLR0913` (ignored in config) noted; wrappers must use `*args, **kwargs` passthrough or consume named params.

## Verified anchors (all read this session)

| Fact | Location |
|---|---|
| `AgentPatternPipeline.__init__(agent, pattern_loader, embedder, retrieval_config=None, reranker_config=None, reasoning_client=None)`, Workflow `timeout=1200` | `src/pipeline.py:527-577` |
| `_reasoning_block` reads `.enabled` + `await run_pre_llm(phase, task_inputs)`; phases `"analyze"/"generate"/"evaluate"` | `src/pipeline.py:583-616`, calls at `:739/:897/:999` |
| `ReasoningMCPClient.enabled` property | `src/reasoning/client.py:190-192` |
| LLM dispatch: `generate_structured(system_prompt, user_prompt, response_schema)` with `RequirementWeights` (`:1667`), `AgentSystemDesignResponse`/`AgentSystemDesignResponseWire` (`:907-912`), `AgentSystemEvaluation` (`:1013`) | `src/pipeline.py`, `src/agent.py:163` |
| `analyze` builds a **new** `HybridPatternRetriever` per call | `src/pipeline.py:689` |
| `HybridPatternRetriever.retrieve(user_domain, normalized_domain)` def | `src/patterns/retriever.py:361` |
| `SafeTEIReranker` defined in `src/patterns/safe_tei_rerank.py`, imported into retriever module ns at `:69`, lazily instantiated at `:334` inside `_ensure_reranker` (`:319`) — late-bound via module globals | `src/patterns/retriever.py:69,319,334` |
| Reranker stashes stage-1 fused score in `node.metadata["retrieval_score"]` before overwriting `node.score` — wrapper must observe only, never touch scores | `src/patterns/retriever.py:313-317` docstring |
| `build_vector_index` probes `embed_model.get_query_embedding("dimension-probe")` | `src/patterns/nodes.py:131` |
| Selection: `selected = scored[:top_k_patterns=5]` (`:750-751`), `recommended_pattern_name = selected[0]["name"]` (`:784`); `_score_patterns` blended = `0.7·analysis + 0.3·fusion_normalized` (`:1691`) | `src/pipeline.py` |
| `PipelineResult` carries `final_pattern_name`, `final_topology`, `final_quality_score` (0-100), `attempts`, `is_fallback`, `alternative_topologies`, `matched_domains` | `src/pipeline.py:1170-1192` |
| Wire output: `pipeline_result_to_output` → `DesignAgentSystemOutput.model_dump()` with all fields above | `src/tools/design.py:371-401` |
| Corpus: 61 records in `pattern/*-pattern.json`; 10 categories (`reflection` 7, `observability` 3, `retrieval` 7, `multi_agent` 11, `reasoning` 5, `tool_use` 4, `memory` 7, `safety_control` 8, `planning` 8, `research_synthesis` 1); 8 topologies (`single-agent-loop` 28, `pipeline` 8, `evaluator-loop` 6, `swarm` 5, `plan-execute` 5, `hierarchical` 5, `parallel-fan-out` 3, `graph-orchestrated` 1) | `src/schemas/enums.py:35-59` + live count |
| Offline-double precedent: `MockAgentSystemArchitect` (dispatch on `response_schema`), `MockDenseRetriever`/`MockBM25Retriever` injected as `pipeline._dense_retriever`/`_bm25_retriever`, `create_test_pipeline` pins `min_fusion_score=0.0` | `tests/unit/test_pipeline.py:55-360` |
| Dev compose: service `agent-pattern-mcp` port `${MCP_HOST_PORT:-8061}:8051`; TEI services `pattern-tei-embed`/`pattern-tei-rerank` internal `:8080`, **no published ports**; generator env `GENERATOR_PROVIDER=minimax`, `GENERATOR_MODEL=minimax/MiniMax-M2.7`, key `MINIMAXAI_API_KEY`; env names **unprefixed** (`EMBEDDER_BASE_URL`, `RERANKER_BASE_URL`, `REASONING_*`) | `docker/docker-compose.yml:30-36,38-39,64,84,95,106-135` |
| `from fastmcp import Client` client precedent | `examples/agent_client.py:52,72` |
| Makefile conventions: `UV ?= uv`, `COMPOSE := docker compose -f docker/docker-compose.yml`, `##@` section headers; no benchmark targets yet; tail is `##@ Maintenance / clean` | `Makefile` |
| deptry/vulture/ruff scopes | `Makefile:48-66`, `pyproject.toml:203-208` |

## Reference harness inventory to port (@25cbfba)

`tests/benchmark/harness/{__init__,config,probes,scoring,offline,runner,main,e2e,compare,selfcheck,draft}.py`, `scenarios/{scenario.schema.json,seed.json}`, `docker/docker-compose.benchmark.yml`, Makefile benchmark block. Key behaviors ported verbatim where applicable:
- `StageRecorder`/`StageRecord {stage, op, started_ns, duration_ms, ok, meta}`; percentiles via `statistics.quantiles(n=20, method="inclusive")` (p50 = cut 9, p95 = cut 18); `<4` samples → `null` + note.
- Hand-rolled Wilson score interval, sign test (`math.comb`), Newcombe paired-difference CI — stdlib only.
- Offline FLIP: decoy pool → guaranteed miss; **fixture-integrity assert both directions** (non-flipped must hit, flipped must miss).
- Paired-by-scenario compare keyed `<scenario_id>#<repeat>`; refuses mismatched corpus sha256/modes; refuses `aborted.json` marker; exit 1 on candidate-loss.
- Pre-registered verdict: candidate wins iff holdout p95 e2e ≥15% better AND holdout hit rate ≥ baseline Wilson lower bound; `<4` holdout samples → inconclusive.
- Warmup = `scenarios[0]` → `warmup.json`, excluded from metrics.
- Run dir `data/benchmark-runs/<run-id>/{manifest,summary,report.md,scenarios/,warmup.json}`.
- draft.py: user-gated corpus expansion, split by family position (last third → holdout).

## Approach (ordered execution steps)

### S1 — Scenario corpus + schema
Create `tests/benchmark/harness/scenarios/scenario.schema.json` (Draft-07, **only** subset keywords: `type`, `required`, `enum`, `minLength`, `minItems`, `additionalProperties`) and `seed.json` with **20 scenarios = 2 per category × 10 categories**, split **13 train / 7 holdout, family-disjoint** (each category's scenarios share one split; `research_synthesis` and `observability` (1 and 3 catalog patterns) get train/holdout respectively so both splits contain sparse categories). Scenario fields:
- `scenario_id` (kebab, unique), `category` (= family key, one of the 10 enum values), `split` (`train`|`holdout`)
- `requirements` (≥40 chars, realistic agent-system brief phrased to imply the category's quality profile)
- `domain` — a real `suitable_domains` slug of `acceptable_primary[0]` (read from `pattern/<name>-pattern.json` while authoring)
- `acceptable_primary`: 1–3 pattern names that exist in `pattern/` and belong to the scenario category
- `decoy_domains`: 2+ slugs that map to patterns of **other** categories (FLIP fuel)

Authoring procedure: for each category pick its 2 most distinctive patterns as primaries across the 2 scenarios; write requirements that emphasize those patterns' `quality_attributes` strengths; verify `domain ∈ suitable_domains` of the primary via `jq`.

### S2 — `harness/config.py`
- `Scenario` frozen dataclass; `load_corpus()` → scenarios + corpus `sha256` (hash of sorted `pattern/*.json` bytes).
- `validate_scenarios(draft7_subset_validator)` — ~60-line hand-rolled validator walking the schema; error messages carry JSON-pointer paths.
- Cross-checks beyond schema: every `acceptable_primary`/`decoy`-referenced pattern exists; `domain ∈ suitable_domains` of primary; category of primary == scenario category; split disjointness per family.
- Offline config pin: `RetrievalConfig(min_fusion_score=0.0)` (stage-C floor analog; rationale mirrors reference `primary_score_threshold: 0`); record `effective_config` in manifest via `model_dump()`.
- Run-id (`bench-<mode>-<utcstamp>-<shortrand>`), run-dir layout constants.

### S3 — `harness/probes.py`
- `StageRecord`/`StageRecorder` (port verbatim; `ok: bool`, `meta: dict`).
- `LLMProxy(real_agent, recorder)`: async `generate_structured(system_prompt, user_prompt, response_schema, *, role=...)` — buckets on `response_schema.__name__`: `RequirementWeights → llm.weights`, `AgentSystemDesignResponse|AgentSystemDesignResponseWire → llm.generate`, `AgentSystemEvaluation → llm.evaluate`; times + records, delegates untouched.
- `EmbedderProbe(real)`: overrides `get_query_embedding`, `get_text_embedding`, `_get_text_embeddings`; `__getattr__` delegates everything else (dimension-probe + index build stay functional).
- `ReasoningProbe(real)`: exposes `enabled` (delegates) + async `run_pre_llm(phase, task_inputs)` → records `reasoning.<phase>` timing, delegates.
- `apply_live_probes(recorder)` contextmanager (try/finally):
  1. `unittest.mock.patch.object(src.patterns.retriever.HybridPatternRetriever, "retrieve")` with an **async** passthrough wrapper (signature `(user_domain, normalized_domain)`; records duration, ok, `len(patterns)`, matched_domains count) — class-object patch is location-safe (`src.pipeline` imports the same class, `pipeline.py:68-71`) and timing-robust (retriever constructed per analyze call, `pipeline.py:689`).
  2. `unittest.mock.patch.object(src.patterns.retriever, "SafeTEIReranker", factory)` — factory returns a wrapper with `postprocess_nodes(nodes, query_bundle=...)` recording per-chunk latency + chunk size, **delegating without touching scores or `metadata["retrieval_score"]`** (contract at `retriever.py:313-317`). Late binding works because `_ensure_reranker` resolves the name from module globals at first use (`:319,334`).
- Stage taxonomy: `analyze.retrieve`, `analyze.rerank`, `analyze.weights`, `analyze.score` (residual = analyze wall − attributed ops), `generate`, `evaluate`, `reasoning.<phase>`, `design_loop.wall`, `e2e.http`, `e2e.total`.

### S4 — `harness/scoring.py`
- Selection observables: ordered set `S = AnalysisResult.selected_patterns` (rank 1 = recommended primary, ranks 2–5 supporting context).
  - `hit@1` = `final_pattern_name ∈ acceptable_primary` **and not** `is_fallback`.
  - `recall@K` (K = 1..5) over `S` vs `acceptable_primary`; `MRR` over `S`.
  - `topology_hit` = `final_topology ==` primary label's catalog `topology` field, **read from `pattern/<primary[0]>-pattern.json` at scoring time** (derived expectation, not scenario-authored).
- Calibration: score = `clip(final_quality_score/100, 0, 1)` per scenario; `Brier`, `ECE` (10 equal-width bins), reliability-curve data; event = hit.
- Risk-coverage: sort by score desc; coverage = k/n; risk = miss-rate among top-k; report elbow.
- `Wilson` (score interval), sign test (`math.comb` two-sided exact), Newcombe paired-difference CI — port verbatim from reference (stdlib only).
- Percentile helper: `statistics.quantiles(n=20, method="inclusive")`, p50 = idx 9, p95 = idx 18; `<4` samples → `None` + note field.
- **Dropped (no seam in this repo):** supporting-F1 (selection is a flat ranked list — no supporting role), veto-conflicts (no veto step).

### S5 — `harness/offline.py`
- `ScriptedAgent(scenario)`: `RequirementWeights` → fixed plausible weights dict (all 7 keys from `QUALITY_ATTRIBUTE_KEYS`); design → canned `AgentSystemDesignResponse`-shaped payload with `overview.topology` = expected topology; evaluation → canned metrics incl. `overall_quality` (deterministic per scenario via seeded hash so scores vary across scenarios but are stable across runs).
- Stub retrievers (dense + BM25) keyed on scenario slugs: return `NodeWithScore(TextNode(text=slug, metadata={"slug": slug}), score=…)` for the scenario's domain + decoy list (shape per `tests/unit/test_pipeline.py:299-328`).
- Pipeline assembly: `AgentPatternPipeline(agent=ScriptedAgent(...), pattern_loader=PatternLoader(pattern dir=<repo>/pattern), embedder=<MagicMock or stub>, retrieval_config=RetrievalConfig(min_fusion_score=0.0), reranker_config=RerankerConfig(config=RerankerInnerConfig(base_url="http://offline-invalid:8080")))`; then inject `pipeline._dense_retriever`/`_bm25_retriever` with stubs (offline arm needs **zero patching**). Do NOT call `ConfigManager` (class-cache trap).
- FLIP: `--flip` swaps scenario domain/decoy slug sets → retrieval surfaces decoy-category patterns → `_score_patterns` ranks them → `final_pattern_name ∉ acceptable_primary`. **Fixture integrity assert**: every non-flipped scenario must hit; every flipped scenario must miss; violation = harness bug, exit 2.
- Reasoning client: `None` (constructor default) — offline records `reasoning: disabled`.

### S6 — `harness/runner.py` + `harness/main.py`
- CLI (click, mirroring reference flags): `--mode {offline,live,e2e}`, `--limit`, `--flip` (offline), `--repeat`, `--output-root`, `--call-timeout` (e2e), `--dry-run` (draft).
- Per run: load corpus → validate → warmup (`scenarios[0]`, result → `warmup.json`, excluded from metrics) → loop scenarios × repeats → write per-scenario JSON (`scenarios/<scenario_id>.json`: selection, stages, timings, metrics) → aggregate `summary.json` + `report.md` (stage table with p50/p95 + residual line, hit/recall/MRR/topology-hit, calibration, risk-coverage, mode-specific notes) → `manifest.json` (mode, corpus sha256, scenario-set sha256, `effective_config`, env snapshot with **unprefixed** names: `GENERATOR_*`, `EMBEDDER_BASE_URL`, `RERANKER_BASE_URL`, `REASONING_*`; secrets recorded as presence-flags only, never values; `reasoning_health` in live/e2e).
- Failure handling: `aborted.json` marker + partial artifacts preserved (compare refuses such runs).
- Exit codes: 0 ok, 1 candidate-loss/verdict-fail (compare only), 2 harness/fixture-integrity error.

### S7 — `harness/e2e.py`
- `from fastmcp import Client` (precedent `examples/agent_client.py:52`); URL `--mcp-url` default `env BENCH_MCP_URL or http://localhost:8061/mcp`.
- Call `design_agent_system(requirements=..., domain=...)`; parse `DesignAgentSystemOutput` fields (`final_pattern_name`, `final_topology`, `final_quality_score`, `is_fallback`, `attempts`, `matched_domains`).
- Stages recorded: `e2e.http` (client-side wall per call), `e2e.total` (per scenario incl. parse). Default `--call-timeout 1500` (server Workflow timeout is 1200s + margin).

### S8 — `harness/compare.py`
- Paired by `<scenario_id>#<repeat>`; refuse: corpus sha256 mismatch, mode mismatch, `aborted.json` present in either run.
- Per-scenario deltas (e2e p95, hit, score); Wilson on hit rates per split; sign test + Newcombe CI on paired e2e times; **holdout-only verdict**: candidate wins iff holdout p95 e2e ≥15% better AND holdout hit rate ≥ baseline Wilson LB; `<4` holdout samples → `inconclusive`; `--allow-mismatch` escape hatch for mode-differing A/B (explicitly recorded in output).

### S9 — `harness/selfcheck.py` (≈12 anchors, exit 0 required)
1. Percentile cuts (p50=9, p95=18) on a known vector; 2. `<4` samples → null + note; 3. stage-table sums + residual identity (`phase_wall == Σops + residual` ±1ms); 4. Wilson LB/UB against known values; 5. sign-test p-value on symmetric split; 6. Newcombe CI sign behavior (contains/excludes 0); 7. recall@K monotonic non-decreasing; 8. MRR on hand-computed case; 9. hit requires `not is_fallback` (fallback with correct name = miss); 10. Brier/ECE on toy vectors (perfect → 0, anti-calibrated → high); 11. risk-coverage risk non-increasing with coverage on sorted scores; 12. schema validator accepts `seed.json`, rejects each tampered variant (missing required, bad enum, unknown key, short requirements); 13. topology_hit consistency vs catalog file.

### S10 — `docker/docker-compose.benchmark.yml` (additive override)
- Reuses existing TEI service definitions via `extends` or full re-declaration (verify `extends` works with the existing `build:` blocks; if not, redeclare services `pattern-tei-embed`/`pattern-tei-rerank` with same images but **published ports** `127.0.0.1:${BENCH_EMBED_PORT:-18081}:8080` / `127.0.0.1:${BENCH_RERANK_PORT:-18082}:8080`, unique container names `agent-pattern-tei-bench*`). Run with `docker compose -f docker/docker-compose.yml -f docker/docker-compose.benchmark.yml up -d pattern-tei-embed pattern-tei-rerank`.
- Live-mode env for the harness process (NOT the container): `EMBEDDER_BASE_URL=http://127.0.0.1:18081/v1`, `RERANKER_BASE_URL=http://127.0.0.1:18082`, plus unprefixed `GENERATOR_*` (MiniMax defaults from dev compose; key from `MINIMAXAI_API_KEY`).

### S11 — Makefile `##@ Benchmark` block + `.gitignore`
Append before `##@ Maintenance` (conventions `UV ?= uv`, tab recipes, `## help` comments):
```make
benchmark-selfcheck:   ## Run benchmark harness self-checks
benchmark-offline:     ## Offline scripted benchmark (FLIP=1 for decoy arm)
benchmark-live:        ## Live in-process benchmark (needs sidecars + generator key)
benchmark-e2e:         ## Wire-mode benchmark via MCP client (CALL_TIMEOUT=)
benchmark-compare:     ## A/B compare two runs (A=<id> B=<id> ALLOW_MISMATCH=1)
benchmark-sidecars-up: ## Start TEI sidecars with published bench ports
benchmark-draft:       ## Draft new scenarios from live transcripts (DRY_RUN=1)
```
Each recipe: `cd`-free `$(UV) run python -m tests.benchmark.harness.main --mode …` (add `tests/benchmark/harness/__main__.py` shim or call module path directly — decide: use `python -m tests.benchmark.harness.main` with `__init__.py` present; repo root on `sys.path` via `uv run` cwd). `.gitignore` += `data/benchmark-runs/` (append near the fizz artifacts block at tail).

## Critical files

**New:** `tests/benchmark/harness/{__init__,config,probes,scoring,offline,runner,main,e2e,compare,selfcheck,draft}.py`, `tests/benchmark/harness/scenarios/{scenario.schema.json,seed.json}`, `docker/docker-compose.benchmark.yml`, (optional `__main__.py`).
**Edited:** `Makefile` (one `##@ Benchmark` block), `.gitignore` (one line).
**Untouched:** everything under `src/`, `pyproject.toml`, existing `tests/benchmark/{runner.py,compare.py,requirements.jsonl,README.md,RUBRIC.md}`, `docker/docker-compose.yml`.

## Verification

1. `make benchmark-selfcheck` → exit 0, all anchors listed PASS.
2. `make benchmark-offline LIMIT=3` → run dir populated; fixture-integrity assert green (non-flipped hit, flipped miss with `FLIP=1`); stage table shows `analyze.retrieve/rerank/weights` + residual + `generate`/`evaluate` with sane sums; `report.md` renders.
3. Compare smoke: two offline runs (A normal, B `FLIP=1`) → `make benchmark-compare A=<a> B=<b>` → verdict machinery exercised (B loses), exit codes correct; `ALLOW_MISMATCH` path not needed (same mode).
4. Repo gates untouched-green: `make check-lint check-static-typing check-deadcode check-depcheck test-unit`.
5. Live/e2e: **user-gated** (needs `MINIMAXAI_API_KEY` + sidecars `make benchmark-sidecars-up`); smoke = `LIMIT=1` live run with populated reasoning stage records and `reasoning_health` in manifest; e2e `LIMIT=1` against dev server.

## Assumptions & contingencies

- **Compose override port publishing**: if `extends` + ports proves awkward, redeclare the two TEI services fully in the override file (same images/build, new container names) — no edit to the base file either way.
- **`research_synthesis` has 1 catalog pattern**: its 2 seed scenarios both accept that single pattern (acceptable_primary length 1) — legitimate: hit measures whether the pipeline surfaces it for research-synthesis-shaped requirements.
- **Live mode needs the reasoning servers resolvable** (`make install-mcps` / `npm root -g` paths from `REASONING_*` env); harness records `reasoning_health` but does not fail on unhealthy reasoning (server-side degradation contract).
- **Wire schema flip**: `use_lean_wire_schema` changes the generate schema class name — LLMProxy buckets both names to `generate` (attribution stable across schema modes).
- **Python version**: `py312` target — harness may use 3.12 syntax but nothing newer.
- Draft (`benchmark-draft`) ships as user-gated corpus expansion reading live-run scenario artifacts; split assignment by category position (last third of each family's scenarios → holdout), mirroring reference semantics with category as family.
