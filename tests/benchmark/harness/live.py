# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT

"""Live in-process benchmark mode (S7).

Builds the real pipeline the way ``src/server.py`` does (ConfigManager →
ServerConfig → AgentSystemArchitect → ReasoningClient → embedder →
AgentPatternPipeline), wraps the component seams with the S3 probes
(LLMProxy / EmbedderProbe / ReasoningProbe / retriever-reranker patches) and
runs the real catalog against each scenario's requirements+domain. No stubs:
this measures actual selection quality, including retrieval and reranking.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace
from typing import Any

import litellm

from tests.benchmark.harness.config import PATTERN_DIR, BenchmarkScenario, disable_embedding_cache
from tests.benchmark.harness.offline import ScenarioRun, _catalog
from tests.benchmark.harness.probes import (
    OP_WARMUP_INDEXES,
    STAGE_BUILD_EMBED,
    LLMProxy,
    ReasoningProbe,
    StageRecord,
    StageRecorder,
    apply_live_probes,
    request_stage_total_ms,
    residual_ms,
    stage_table,
)
from tests.benchmark.harness.scoring import (
    ScenarioScore,
    score_failure,
    score_scenario,
    summarize_arm,
)


class ProviderDeathError(RuntimeError):
    """Generator provider permanently failed (balance/quota/auth) — abort the arm."""


class DesignPhaseError(RuntimeError):
    """The design leg raised after the analysis leg had already succeeded.

    Carries the analysis so the paired analyze arm keeps its own result when
    the full arm records a failed scenario; without it a design-phase fault
    would zero a selection the analysis actually produced.
    """

    def __init__(self, cause: BaseException, analysis: Any) -> None:
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.cause = cause
        self.analysis = analysis


#: Substrings (lowercased) that mark a provider as dead for money/auth reasons.
#: Deliberately phrase-anchored: bare numeric tokens ('401','403') would
#: false-positive on request ids like 'b5b0466d-1ced-...'.
PROVIDER_DEATH_SIGNATURES: tuple[str, ...] = (
    "insufficient balance",
    "no credits remaining",
    "insufficient_quota",
    "invalid_api_key",
    "incorrect api key",
    "authorized_error",
    "login fail",
    "unauthorized",
    "api key not valid",
    "authentication_error",
    "permission denied",
    "account is depleted",
)


def is_permanent_provider_death(error_text: str) -> bool:
    """True when an error string names a permanent provider fault.

    Parse faults ('could not be parsed into', 'Field required'), timeouts,
    transient 429s and request-id noise match none of these phrases and stay
    tolerated by the per-scenario failure policy.
    """
    lowered = error_text.lower()
    return any(sig in lowered for sig in PROVIDER_DEATH_SIGNATURES)


async def preflight_generator(config: Any, timeout_s: float = 90.0) -> None:
    """Probe the generator directly (litellm, retries off) before the arm.

    Deliberately NOT ``agent.generate_structured``: llama-index wraps every
    agent call in a tenacity cascade (``acompletion_with_retry``, max_retries=10,
    4–10 s backoff, RateLimitError retried) that retries a dead provider for
    many minutes — far beyond any wall timeout — and its exception mapping can
    re-label the fault (OpenAI's "You have no credits remaining" arrives as
    ``litellm.RateLimitError``). A direct ``litellm.acompletion`` with
    ``num_retries=0`` surfaces the provider's real error text in seconds, which
    the phrase classifier can then judge.

    asyncio.TimeoutError and non-death errors pass through silently — the
    preflight must never abort an arm on a transient hiccup or a hard-to-map
    provider error; the mid-run classifier still catches a provider that dies
    later, and warmup/scenarios keep today's tolerance.
    """
    section = config.generator
    cfg = section.config
    bare_model = cfg.model
    if "/" in bare_model:
        bare_model = bare_model.split("/", 1)[1]
    model = f"{section.provider}/{bare_model}"
    try:
        await asyncio.wait_for(
            litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": "Reply with the single word: ok."}],
                api_key=cfg.api_key,
                api_base=cfg.base_url or None,
                num_retries=0,
                max_tokens=256,
                temperature=cfg.temperature,
            ),
            timeout=timeout_s,
        )
    except TimeoutError:
        return
    except Exception as exc:  # noqa: BLE001 — classified, else conservative pass
        text = f"{type(exc).__name__}: {exc}"
        if is_permanent_provider_death(text):
            raise ProviderDeathError(f"generator provider permanently failed preflight: {text}") from exc


@dataclass(frozen=True)
class LiveComponents:
    """Real pipeline plus its probe wrappers and effective config."""

    pipeline: Any
    config: Any
    reasoning_health: dict[str, str]
    # The ReasoningClient is kept here (not only inside the pipeline, which keeps
    # it private) so the run can close it: see shutdown_live_components.
    reasoning_client: Any


def load_server_config() -> Any:
    """Load ServerConfig exactly like the server (CONFIG_PATH or default)."""
    import os

    from src.config import ConfigManager, ServerConfig

    config_dict = ConfigManager.load_config(os.environ.get("CONFIG_PATH"))
    return ServerConfig.model_validate(config_dict)


async def build_live_components(recorder: StageRecorder) -> LiveComponents:
    """Assemble the real pipeline with probes attached (mirrors server init)."""
    # Every arm measures the cold embed path; a snapshot hit would report a
    # warm start under ``build.embed`` and leak into the operator's cache dir.
    disable_embedding_cache()
    from src.agent import AgentSystemArchitect
    from src.pipeline import AgentPatternPipeline
    from src.patterns.embedder import build_embedder
    from src.patterns.loader import PatternLoader
    from src.reasoning.client import ReasoningClient

    config = load_server_config()
    agent = AgentSystemArchitect(config)

    reasoning_client: ReasoningClient | None = None
    if config.reasoning.enabled:
        reasoning_client = ReasoningClient(config.reasoning, agent)
    reasoning_probe = ReasoningProbe(reasoning_client, recorder) if reasoning_client else None

    reasoning_health: dict[str, str] = {}
    if reasoning_client is not None:
        try:
            reasoning_health = await reasoning_client.health_check()
        except Exception as exc:  # noqa: BLE001 — health is informational, never fatal
            reasoning_health = {"error": f"{type(exc).__name__}: {exc}"}

    loader = PatternLoader(patterns_dir=str(PATTERN_DIR))
    loader.load_all()

    embedder_cfg = config.embedder
    embedder = build_embedder(
        provider=embedder_cfg.provider,
        base_url=embedder_cfg.config.base_url,
        api_key=embedder_cfg.config.api_key,
        query_instruction=embedder_cfg.config.query_instruction,
        text_instruction=embedder_cfg.config.text_instruction,
        embed_batch_size=embedder_cfg.config.embed_batch_size,
    )

    pipeline = AgentPatternPipeline(
        agent=LLMProxy(agent, recorder, stage="run"),  # type: ignore[arg-type]
        pattern_loader=loader,
        # NOTE: the embedder is passed unwrapped on purpose — llama-index's
        # VectorStoreIndex requires a real BaseEmbedding (isinstance check in
        # resolve_embed_model), which any __getattr__ wrapper fails. Embedding
        # call attribution is covered indirectly by retriever/rerank stages.
        embedder=embedder,
        embedder_config=embedder_cfg,
        retrieval_config=config.retrieval,
        reranker_config=config.reranker,
        reasoning_client=reasoning_probe,  # type: ignore[arg-type]
    )
    build_started = time.monotonic_ns()
    await asyncio.to_thread(pipeline.warmup_indexes)
    recorder.add(
        StageRecord(
            stage=STAGE_BUILD_EMBED,
            op=OP_WARMUP_INDEXES,
            started_ns=build_started,
            duration_ms=(time.monotonic_ns() - build_started) / 1e6,
            ok=True,
            meta={},
        )
    )
    return LiveComponents(
        pipeline=pipeline,
        config=config,
        reasoning_health=reasoning_health,
        reasoning_client=reasoning_client,
    )


def score_analysis(
    scenario: BenchmarkScenario,
    analysis: Any,
    catalog: dict[str, dict[str, Any]],
) -> ScenarioScore:
    """Score the analysis leg's own recommendation (no generated design).

    The analyze-only arm's "final" selection is whatever the analysis
    recommends; ``score_scenario`` already derives hit/recall/MRR from those
    fields, so the arm needs no separate metric code. Confidence stays the
    top-1 blended analysis score (there is no ``final_quality_score``).
    """
    selected_names = [str(p.get("name", "")) for p in analysis.selected_patterns]
    top_score: float | None = None
    if analysis.selected_patterns:
        blended = analysis.selected_patterns[0].get("blended_score")
        if blended is not None:
            top_score = float(blended)
    winner = scenario.acceptable_primary[0]
    return score_scenario(
        scenario_id=scenario.scenario_id,
        primaries=scenario.acceptable_primary,
        winner_topology=str(catalog[winner]["topology"]),
        selected_names=selected_names,
        top_blended_score=top_score,
        final_pattern_name=analysis.recommended_pattern_name,
        final_topology=analysis.recommended_topology,
        is_fallback=analysis.is_fallback,
    )


async def run_live_scenario(
    scenario: BenchmarkScenario,
    components: LiveComponents,
    master: StageRecorder,
) -> ScenarioRun:
    """Run one scenario against the real pipeline; return scored run.

    Uses ``master`` (shared across scenarios because the pipeline's probes are
    bound at build time); the caller slices the window for per-scenario
    artifacts via :func:`records_window`.
    """
    started_ns = time.monotonic_ns()
    catalog = _catalog()
    offset = len(master.records)
    with apply_live_probes(master):
        analysis = await components.pipeline.analyze(
            requirements=scenario.requirements,
            domain=scenario.domain,
        )
        try:
            result = await components.pipeline.run_design(
                requirements=scenario.requirements,
                domain=scenario.domain,
            )
        except Exception as exc:  # noqa: BLE001 — re-raised with the analysis attached
            raise DesignPhaseError(exc, analysis) from exc
    window = master.records[offset:]
    for record in window:
        if record.op == "retriever.retrieve" and not record.meta.get("scenario_id"):
            record.meta["scenario_id"] = scenario.scenario_id
    selected_names = [str(p.get("name", "")) for p in analysis.selected_patterns]
    top_score: float | None = None
    if analysis.selected_patterns:
        blended = analysis.selected_patterns[0].get("blended_score")
        if blended is not None:
            top_score = float(blended)
    winner = scenario.acceptable_primary[0]
    score = score_scenario(
        scenario_id=scenario.scenario_id,
        primaries=scenario.acceptable_primary,
        winner_topology=str(catalog[winner]["topology"]),
        selected_names=selected_names,
        top_blended_score=top_score,
        final_pattern_name=result.final_pattern_name,
        final_topology=result.final_topology,
        is_fallback=result.is_fallback,
    )
    score = replace(
        score,
        confidence=max(0.0, min(1.0, float(result.final_quality_score) / 100.0)),
    )
    del started_ns  # the run boundary is measured by the caller (see run_live_corpus)
    return ScenarioRun(scenario=scenario, arm="live", analysis=analysis, result=result, score=score)


def records_window(master: StageRecorder, offset: int) -> list[StageRecord]:
    """Slice the master recorder's records from ``offset`` on."""
    return master.records[offset:]


@dataclass(frozen=True)
class LiveOutcome:
    """One scenario's live result plus the records it alone produced.

    ``records`` is the per-scenario window (not the arm-wide window): a
    scenario's artifact must carry its own stage attribution, otherwise the
    report attributes scenario 1's LLM time to scenario 2 as well.
    """

    scenario: BenchmarkScenario
    run: ScenarioRun | None
    score: ScenarioScore
    analysis_score: ScenarioScore
    records: list[StageRecord]
    error: str | None
    e2e_ms: float


async def run_live_corpus(
    scenarios: list[BenchmarkScenario],
    recorder: StageRecorder,
    *,
    warmup: bool = True,
    fail_fast: bool = False,
) -> tuple[list[LiveOutcome], LiveComponents, dict[str, Any]]:
    """Build the live pipeline once, warm it up, then run the corpus.

    Failure policy: a scenario whose run raises is recorded as a zeroed
    miss (see :func:`score_failure`) and the arm continues — one stochastic
    provider fault must not burn a ~50-minute arm. ``fail_fast`` restores
    abort-on-first-failure. A provider that is permanently dead
    (balance/quota/auth) raises :class:`ProviderDeathError` before warmup
    (preflight) or on the first matching scenario failure — regardless of
    ``fail_fast``. The warmup scenario is untimed: its records are
    reported in ``warmup.json`` and never counted in the arm.
    """
    components = await build_live_components(recorder)
    try:
        await preflight_generator(components.config)
        warmup_record = (
            await _run_warmup(scenarios, components, recorder, fail_fast=fail_fast)
            if warmup
            else {"enabled": False, "measured": False, "reason": "--no-warmup"}
        )

        outcomes: list[LiveOutcome] = []
        for scenario in scenarios:
            offset = len(recorder.records)
            started_ns = time.monotonic_ns()
            try:
                run = await run_live_scenario(scenario, components, recorder)
            except Exception as exc:  # noqa: BLE001 — recorded, then the arm continues
                if fail_fast:
                    raise
                error = str(exc) if isinstance(exc, DesignPhaseError) else f"{type(exc).__name__}: {exc}"
                if is_permanent_provider_death(error):
                    raise ProviderDeathError(f"generator provider died mid-run: {error}") from exc
                failure = score_failure(scenario.scenario_id, error)
                failed_analysis = getattr(exc, "analysis", None)
                outcomes.append(
                    LiveOutcome(
                        scenario=scenario,
                        run=None,
                        score=failure,
                        analysis_score=(
                            score_analysis(scenario, failed_analysis, _catalog())
                            if failed_analysis is not None
                            else failure
                        ),
                        records=records_window(recorder, offset),
                        error=error,
                        e2e_ms=round((time.monotonic_ns() - started_ns) / 1e6, 3),
                    )
                )
                continue
            outcomes.append(
                LiveOutcome(
                    scenario=scenario,
                    run=run,
                    score=run.score,
                    analysis_score=score_analysis(scenario, run.analysis, _catalog()),
                    records=records_window(recorder, offset),
                    error=None,
                    e2e_ms=round((time.monotonic_ns() - started_ns) / 1e6, 3),
                )
            )
        return outcomes, components, warmup_record
    finally:
        await shutdown_live_components(components)


@dataclass(frozen=True)
class AnalyzeRun:
    """One scenario's analysis-only run (no design generated)."""

    scenario: BenchmarkScenario
    analysis: Any
    score: ScenarioScore
    records: list[StageRecord]


@dataclass(frozen=True)
class AnalyzeOutcome:
    """One scenario's analysis-only outcome, successful or failed.

    A failed run is recorded as a zeroed miss (see :func:`score_failure`) so
    the arm continues; ``fail_fast`` restores abort-on-first-failure.
    """

    scenario: BenchmarkScenario
    analysis: Any | None
    score: ScenarioScore
    records: list[StageRecord]
    error: str | None
    e2e_ms: float


async def run_analyze_scenario(
    scenario: BenchmarkScenario,
    components: LiveComponents,
    master: StageRecorder,
) -> AnalyzeRun:
    """Run the real pipeline's analysis leg only; return the scored run.

    The analyze-only arm exists to price the path a coding agent takes when it
    writes the implementation itself: retrieval + one analysis LLM call, then
    the agent implements. No generate/evaluate/refine phases run.
    """
    offset = len(master.records)
    with apply_live_probes(master):
        analysis = await components.pipeline.analyze(
            requirements=scenario.requirements,
            domain=scenario.domain,
        )
    window = master.records[offset:]
    for record in window:
        if record.op == "retriever.retrieve" and not record.meta.get("scenario_id"):
            record.meta["scenario_id"] = scenario.scenario_id
    return AnalyzeRun(
        scenario=scenario,
        analysis=analysis,
        score=score_analysis(scenario, analysis, _catalog()),
        records=window,
    )


async def run_analyze_corpus(
    scenarios: list[BenchmarkScenario],
    recorder: StageRecorder,
    *,
    warmup: bool = True,
    fail_fast: bool = False,
) -> tuple[list[AnalyzeOutcome], LiveComponents, dict[str, Any]]:
    """Build the live pipeline once, warm up, then run the analysis leg only.

    Shares :func:`build_live_components`, preflight, warmup accounting and
    shutdown with the full live arm; only the per-scenario call differs.
    """
    components = await build_live_components(recorder)
    try:
        await preflight_generator(components.config)
        warmup_record = (
            await _run_warmup(scenarios, components, recorder, fail_fast=fail_fast, analyze_only=True)
            if warmup
            else {"enabled": False, "measured": False, "reason": "--no-warmup"}
        )

        outcomes: list[AnalyzeOutcome] = []
        for scenario in scenarios:
            offset = len(recorder.records)
            started_ns = time.monotonic_ns()
            try:
                run = await run_analyze_scenario(scenario, components, recorder)
            except Exception as exc:  # noqa: BLE001 — recorded, then the arm continues
                if fail_fast:
                    raise
                error = f"{type(exc).__name__}: {exc}"
                if is_permanent_provider_death(error):
                    raise ProviderDeathError(f"generator provider died mid-run: {error}") from exc
                outcomes.append(
                    AnalyzeOutcome(
                        scenario=scenario,
                        analysis=None,
                        score=score_failure(scenario.scenario_id, error),
                        records=records_window(recorder, offset),
                        error=error,
                        e2e_ms=round((time.monotonic_ns() - started_ns) / 1e6, 3),
                    )
                )
                continue
            outcomes.append(
                AnalyzeOutcome(
                    scenario=scenario,
                    analysis=run.analysis,
                    score=run.score,
                    records=run.records,
                    error=None,
                    e2e_ms=round((time.monotonic_ns() - started_ns) / 1e6, 3),
                )
            )
        return outcomes, components, warmup_record
    finally:
        await shutdown_live_components(components)


async def shutdown_live_components(components: LiveComponents) -> None:
    """Release the loop-bound async clients one live run created.

    litellm caches one HTTP client per provider; for the OpenAI-compatible
    generator that client is aiohttp-backed. ``main`` gives every repeat its own
    event loop, so a client cached during repeat N is bound to a loop that is
    already closed when repeat N+1 starts, and litellm's atexit hook cannot free
    it either (it runs on a fresh loop) — aiohttp then reports "Unclosed client
    session" / "Unclosed connector" at interpreter exit. Disposing here, inside
    the live loop that owns the sessions, closes them and drops the cached
    handlers, so the next repeat builds clients bound to its own loop.
    """
    import litellm

    if components.reasoning_client is not None:
        await components.reasoning_client.close()
    await litellm.close_litellm_async_clients()
    litellm.in_memory_llm_clients_cache.cache_dict.clear()


async def _run_warmup(
    scenarios: list[BenchmarkScenario],
    components: LiveComponents,
    recorder: StageRecorder,
    *,
    fail_fast: bool,
    analyze_only: bool = False,
) -> dict[str, Any]:
    """Run the first scenario untimed so caches and processes are hot."""
    if not scenarios:
        return {"enabled": False, "reason": "empty corpus"}
    scenario = scenarios[0]
    offset = len(recorder.records)
    started_ns = time.monotonic_ns()
    error: str | None = None
    try:
        if analyze_only:
            await run_analyze_scenario(scenario, components, recorder)
        else:
            await run_live_scenario(scenario, components, recorder)
    except Exception as exc:  # noqa: BLE001 — recorded; the arm still runs
        if fail_fast:
            raise
        error = f"{type(exc).__name__}: {exc}"
    window = records_window(recorder, offset)
    e2e = round((time.monotonic_ns() - started_ns) / 1e6, 3)
    table = stage_table(window)
    return {
        "enabled": True,
        "measured": False,
        "scenario_id": scenario.scenario_id,
        "e2e_ms": e2e,
        "stages": table,
        "stage_total_ms": request_stage_total_ms(table),
        "residual_ms": residual_ms(e2e, table),
        "error": error,
        "stage_counts": _counts(window),
    }


def _counts(records: list[StageRecord]) -> dict[str, int]:
    """Record count per op for the warmup report."""
    tally: dict[str, int] = {}
    for record in records:
        tally[record.op] = tally.get(record.op, 0) + 1
    return tally
