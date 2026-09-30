# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

"""Stage-0 selection benchmark, offline arms (S5).

Drives ``AgentPatternPipeline.run_design`` per scenario per arm with fully
deterministic stand-ins: a scripted agent replays per-scenario pipeline
responses, both retrieval legs return a single slug node (fusion dedupes to
one fused node → reranker skipped → zero network; the ``offline-invalid``
reranker URL is a tripwire), and the reasoning client is ``None`` (degraded
in-prompt scaffold, no subprocess).

Arms:
- ``normal``  — recall set = the scenario's own domain slug (the seed's
  cross-checks guarantee the winner wins this set).
- ``flipped`` — recall set = the first decoy slug only (guaranteed miss).

Fixture integrity is asserted after the run: every normal-arm scenario must
hit@1, every flipped-arm scenario must miss; any violation aborts the run
with exit code 2.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from llama_index.core.schema import NodeWithScore, TextNode

from tests.benchmark.harness.config import (
    PATTERN_DIR,
    BenchmarkScenario,
    Corpus,
    offline_reranker_config,
    offline_retrieval_config,
)
from tests.benchmark.harness.probes import ScriptedAgent, StageRecorder, StubSlugRetriever
from tests.benchmark.harness.scoring import ScenarioScore, score_failure, score_scenario

#: Exit code signalling broken fixture integrity (a scripted guarantee failed).
EXIT_INTEGRITY_FAILURE = 2

_NORMAL_SCORE = 0.9
_FLIPPED_SCORE = 0.9

_CATALOG: dict[str, dict[str, Any]] | None = None


def _catalog() -> dict[str, dict[str, Any]]:
    """Load (and memoize) the pattern catalog keyed by pattern name."""
    # Module-level memo is intentional: catalog files are immutable during a
    # run and reloading per scenario would dominate offline runtime.
    global _CATALOG  # noqa: PLW0603
    if _CATALOG is None:
        _CATALOG = {
            data["name"]: data
            for data in (
                json.loads(path.read_text(encoding="utf-8"))
                for path in sorted(PATTERN_DIR.glob("*-pattern.json"))
            )
        }
    return _CATALOG


@dataclass(frozen=True)
class ScenarioRun:
    """One scenario's outcome in one arm.

    Attributes:
        scenario: The scenario that ran.
        arm: ``normal`` or ``flipped``.
        analysis: Full analyze-phase payload (selected_patterns, weights, …).
        result: Full design-loop pipeline result.
        score: Selection-quality metrics computed from the outputs.
    """

    scenario: BenchmarkScenario
    arm: str
    analysis: Any
    result: Any
    score: ScenarioScore


class _OfflineLegs:
    """Builds the per-scenario stub retriever for one arm."""

    @staticmethod
    def for_scenario(scenario: BenchmarkScenario, arm: str) -> StubSlugRetriever:
        """Single-slug stub: own domain (normal) or first decoy (flipped)."""
        slug = scenario.domain if arm == "normal" else scenario.decoy_domains[0]
        return StubSlugRetriever([slug], _FLIPPED_SCORE if arm == "flipped" else _NORMAL_SCORE)


async def _run_single(
    scenario: BenchmarkScenario, arm: str, recorder: StageRecorder
) -> ScenarioRun:
    """Run one scenario in one arm with deterministic stand-ins."""
    from src.config import RerankerConfig
    from src.pipeline import AgentPatternPipeline
    from src.patterns.loader import PatternLoader

    winner = scenario.acceptable_primary[0]
    catalog = _catalog()
    agent = ScriptedAgent(
        scenario_id=scenario.scenario_id,
        scripted_weights=scenario.scripted_weights,
        topology=str(catalog[winner]["topology"]),
        category=scenario.category,
        recorder=recorder,
    )
    loader = PatternLoader(patterns_dir=PATTERN_DIR)
    loader.load_all()
    reranker_config = offline_reranker_config()
    assert isinstance(reranker_config, RerankerConfig)
    pipeline = AgentPatternPipeline(
        agent=agent,  # type: ignore[arg-type]
        pattern_loader=loader,
        embedder=MagicMock(),
        retrieval_config=offline_retrieval_config(),
        reranker_config=reranker_config,
        reasoning_client=None,
    )
    stub = _OfflineLegs.for_scenario(scenario, arm)
    pipeline._dense_retriever = stub
    pipeline._bm25_retriever = stub

    analysis = await pipeline.analyze(
        requirements=scenario.requirements,
        domain=scenario.domain,
    )
    result = await pipeline.run_design(
        requirements=scenario.requirements,
        domain=scenario.domain,
    )
    selected_names = [str(p.get("name", "")) for p in analysis.selected_patterns]
    top_score: float | None = None
    if analysis.selected_patterns:
        blended = analysis.selected_patterns[0].get("blended_score")
        if blended is not None:
            top_score = float(blended)
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
    # Plan S4: calibration input is the pipeline's final quality score, not
    # the analyze-phase blend.
    score = replace(
        score,
        confidence=max(0.0, min(1.0, float(result.final_quality_score) / 100.0)),
    )
    return ScenarioRun(scenario=scenario, arm=arm, analysis=analysis, result=result, score=score)


@dataclass(frozen=True)
class ArmResult:
    """One scenario-arm execution plus its stage records.

    Attributes:
        run: The scenario-arm outcome.
        recorder: Stage records observed during this run.
    """

    run: ScenarioRun
    recorder: StageRecorder


async def run_scenario(
    scenario: BenchmarkScenario, arms: list[str], recorder: StageRecorder
) -> list[ArmResult]:
    """Run one scenario in the requested arms with a fresh recorder each."""
    results: list[ArmResult] = []
    for arm in arms:
        per_arm_recorder = StageRecorder()
        run = await _run_single(scenario, arm, per_arm_recorder)
        results.append(ArmResult(run=run, recorder=per_arm_recorder))
    return results


async def run_corpus(
    corpus: Corpus,
    arms: list[str],
    limit: int | None = None,
) -> list[ArmResult]:
    """Run every scenario (optionally the first ``limit``) in every arm."""
    scenarios = corpus.scenarios if limit is None else corpus.scenarios[:limit]
    results: list[ArmResult] = []
    for scenario in scenarios:
        results.extend(await run_scenario(scenario, arms, StageRecorder()))
    return results


def _fmt(exc: BaseException) -> str:
    """``TypeName: message`` for a recorded failure."""
    return f"{type(exc).__name__}: {exc}"


@dataclass(frozen=True)
class OfflineOutcome:
    """One scenario-arm execution, successful or failed."""

    scenario: BenchmarkScenario
    arm: str
    result: ScenarioRun | None
    score: ScenarioScore
    recorder: StageRecorder
    error: str | None = None
    e2e_ms: float | None = None


async def run_corpus_tolerant(
    scenarios: list[BenchmarkScenario],
    arms: list[str],
    *,
    fail_fast: bool = False,
) -> list[OfflineOutcome]:
    """Run every scenario in every arm, recording per-scenario failures."""
    outcomes: list[OfflineOutcome] = []
    for scenario in scenarios:
        for arm in arms:
            recorder = StageRecorder()
            started = time.monotonic_ns()
            try:
                run = await _run_single(scenario, arm, recorder)
            except Exception as exc:  # noqa: BLE001 — recorded, then the arm continues
                if fail_fast:
                    raise
                outcomes.append(
                    OfflineOutcome(
                        scenario=scenario,
                        arm=arm,
                        result=None,
                        score=score_failure(scenario.scenario_id, _fmt(exc)),
                        recorder=recorder,
                        error=_fmt(exc),
                        e2e_ms=round((time.monotonic_ns() - started) / 1e6, 3),
                    )
                )
                continue
            outcomes.append(
                OfflineOutcome(
                    scenario=scenario,
                    arm=arm,
                    result=run,
                    score=run.score,
                    recorder=recorder,
                    error=None,
                    e2e_ms=round((time.monotonic_ns() - started) / 1e6, 3),
                )
            )
    return outcomes


def check_integrity(
    results: list[tuple[str, BenchmarkScenario, ScenarioScore]],
) -> list[str]:
    """Assert the scripted fixture guarantees; returns violation descriptions.

    Takes ``(arm, scenario, score)`` triples so both the strict
    :class:`ArmResult` path and the failure-tolerant
    :class:`OfflineOutcome` path can be checked identically — a failed run
    is a miss, so it can never hide a broken fixture.
    """
    violations: list[str] = []
    for arm, scenario, score in results:
        if arm == "normal" and not score.hit_at_1:
            violations.append(
                f"{scenario.scenario_id}: normal arm missed"
                f" (final={score.final_pattern_name!r},"
                f" fallback={score.is_fallback})"
            )
        if arm == "flipped" and score.hit_at_1:
            violations.append(
                f"{scenario.scenario_id}: flipped arm unexpectedly hit"
                f" (final={score.final_pattern_name!r})"
            )
    return violations


def integrity_exit_code(
    results: list[tuple[str, BenchmarkScenario, ScenarioScore]],
) -> int:
    """0 when the fixture holds, :data:`EXIT_INTEGRITY_FAILURE` otherwise."""
    return EXIT_INTEGRITY_FAILURE if check_integrity(results) else 0


def slug_node(slug: str, score: float) -> NodeWithScore:
    """One slug node (helper mirroring the stub's payload for e2e reuse)."""
    return NodeWithScore(
        node=TextNode(text=slug, id_=f"slug::{slug}", metadata={"slug": slug}),
        score=score,
    )
