# How Domain & Topology Are Selected

Analysis of how the agent-pattern-mcp server derives the target **domain** and the agent **topology** from a user's inputs (requirements + domain, optional `override_topology`).

## Three Different Vocabularies (`src/schemas/enums.py`)

- **`AgentDomain`** (`src/schemas/enums.py:69`) — 36 problem-space slugs (`rag-applications`, `tool-use-tasks`, `cybersecurity`, ...) used only for pattern suitability filtering.
- **Pattern `name`** — 61 kebab-case catalogue identities (`react`, `supervisor-worker`, ...), one per `pattern/*.json`.
- **`AgentTopology`** (`src/schemas/enums.py:116`) — 8 canonical structural shapes (`single-agent-loop`, `hierarchical`, `pipeline`, `plan-execute`, `swarm`, `parallel-fan-out`, `evaluator-loop`, `graph-orchestrated`) = the `topology` field in `pattern/*.json`.

Domain answers *"which patterns apply?"*; topology answers *"which structural shape was chosen?"*; the pattern name answers *"which catalogue entry won?"*. Name and topology are deliberately kept apart: `recommended_topology`/`final_topology` carry `AgentTopology` values, while `recommended_pattern_name`/`final_pattern_name` carry the winning pattern's name.

## Entry Point

User calls `design_agent_system(requirements, domain, override_topology=None)` — `src/tools/design.py:226`.

Domain is a **user-supplied parameter**, not LLM-classified. It flows into `run_design()` → Workflow `_orchestrate` step (`src/pipeline.py:1195`), which runs ANALYZE then:

```python
design_loop(topology=topology or analysis_result.recommended_topology)  # src/pipeline.py:1226
```

So the topology is either user-overridden (strictly validated against `AgentTopology` by `validate_topology_value`, `src/schemas/enums.py` — invalid values are rejected with `ERR_001` at the tool boundary) or derived in ANALYZE.

## DOMAIN Selection = Hybrid Retrieval, Not Classification

In `analyze()` (`src/pipeline.py:652`):

1. **Normalize**: `domain.lower().replace(" ", "-")` — `src/pipeline.py:678` (IC-31)
2. **Index corpus**: all slugs from every pattern's `suitable_domains` become shared `TextNode`s — `build_domain_nodes` `src/patterns/nodes.py:54` — feeding FAISS + BM25 legs built once at warmup (`warmup_indexes` `src/pipeline.py:1240`)
3. **Two-leg retrieval** (`HybridPatternRetriever.retrieve`, `src/patterns/retriever.py:361`):
   - Dense leg embeds the *raw* domain string (`QueryBundle.custom_embedding_strs`)
   - BM25 leg matches the *normalized* slug tokens (`QueryBundle.query_str`)
   - Different queries per leg is intentional
4. **Fusion + rerank**: `relative_score` fusion (leg weights default dense 0.7 / BM25 0.3, tunable via `RETRIEVAL_DENSE_WEIGHT` / `RETRIEVAL_BM25_WEIGHT` — see `docs/retrieval-fusion-modes.md`), then mandatory TEI cross-encoder rerank with the Vespa-style slug-cut `RR(fused_rank) + RR(ce_rank)`, k=60 (see `docs/vespa-style-blend-score.md`)
5. **Slug → patterns**: `filter_by_domain(slug)` — pattern included when the slug is in `suitable_domains` (or that list is empty) and not in `unsuitable_domains` (`src/patterns/loader.py:269`); pattern score = max fusion score over matching slugs
6. **Fallback**: empty result → `react` tagged `is_fallback=True` — `_fallback` `src/patterns/retriever.py:585` (`DEFAULT_FALLBACK_PATTERN_NAME` at `src/patterns/retriever.py:83`)

The retrieval runs off the event loop via `asyncio.to_thread` — `src/pipeline.py:707`.

## TOPOLOGY Selection = Requirements-Weighted Scoring

Also in ANALYZE:

1. **LLM weight extraction** (`_extract_requirement_weights`, `src/pipeline.py:1619`):
   - One small LLM call maps requirements → **7** quality-attribute weights 0–1 (reliability, cost_efficiency, latency, output_quality, observability, safety, simplicity)
   - All-zero result retries once, then unweighted mean
   - Convex smoothing `w' = α·w + (1−α)/n`, α=0.7 (`weight_smoothing_alpha` `src/config.py:254`)
2. **Deterministic scoring** (`_score_patterns`, `src/pipeline.py:1691`):
   - `analysis_score = Σ(w·quality_attributes)/Σw × 10` (0–100 scale)
   - Fusion score min-max normalized to 0–100 within the recall set
   - `blended = 0.7·analysis + 0.3·fusion` (`analysis_blend_weight`/`fusion_blend_weight` `src/config.py:238,246`)
   - Top `top_k_patterns=5` kept **after** scoring (`src/config.py:197`)
3. **Topology decision** (`_select_recommended_topology`, `src/pipeline.py:1744`):
   - Explicit `override_topology` always wins
   - Else the top pattern's **`topology` field** (an `AgentTopology` value — never its name) becomes `recommended_topology` if its `analysis_score >= topology_score_threshold=50` (`src/config.py:231`)
   - Else fallback to `single-agent-loop` (`DEFAULT_FALLBACK_TOPOLOGY` `src/patterns/retriever.py:91`)

## Topology Drives Generation & Final Validation

- Cached system prompt: *"You are a senior AI agent-system architect designing production {topology} systems"* plus canonical-shape guidance per topology — `get_topology_guidance` `src/prompts/topology_guidance.py:131` (`_generate_system_prompt_cached` `src/pipeline.py:236`)
- Generate user prompt embeds requirements/domain/topology plus `Primary Pattern: {name}` — `_build_generate_user_prompt` `src/pipeline.py:1480`
- Hard constraints: `overview.topology` must be one of the 8 `AgentTopology` values, `overview.category` one of the 10 `PatternCategory` values; violations trigger automatic retry
- `design_loop` (`src/pipeline.py:1030`) retries up to `max_tries=2` (`src/config.py:222`), keeping the best-scoring attempt
- `final_topology = best_design.overview.topology.value`; the matching pattern's name is exposed as `final_pattern_name` (`_selected_topology_pattern` `src/pipeline.py:829` matches by the `topology` field)
- Runner-ups exposed as `alternative_topologies` — deduplicated per topology, best-scoring pattern represents each (`_topology_candidates` `src/pipeline.py:798`)
- The REFINE phase picks its guidance pattern by matching the active topology, falling back to the top-scored pattern (`_select_refinement_pattern` `src/pipeline.py:1988`)

## Summary

| Aspect | Mechanism | Where decided |
|---|---|---|
| Domain | Hybrid retrieval (dense + BM25 + cross-encoder rerank) over curated `AgentDomain` slugs | `HybridPatternRetriever.retrieve` |
| Topology | Requirements-weighted pattern ranking, threshold-gated, override-precedent; winner's `topology` field (not name) | `_score_patterns` + `_select_recommended_topology` in ANALYZE |

**Domain = retrieval problem; topology = scored decision; pattern name = provenance metadata.**
