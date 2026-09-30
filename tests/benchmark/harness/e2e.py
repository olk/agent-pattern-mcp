# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT

"""E2E (wire-mode) benchmark driver (S7).

Calls ``design_agent_system`` over the MCP wire with fastmcp's async client
(precedent ``examples/agent_client.py``). Stage records capture client-side
per-call HTTP wall time and per-scenario total time.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, replace
from typing import Any

from fastmcp import Client

from tests.benchmark.harness.config import PATTERN_DIR, BenchmarkScenario
from tests.benchmark.harness.probes import (
    OP_HTTP,
    STAGE_E2E_HTTP,
    StageRecord,
    StageRecorder,
)
from tests.benchmark.harness.scoring import ScenarioScore, score_failure, score_scenario

#: Exit-code-neutral default endpoint (plan S7: env BENCH_MCP_URL override).
DEFAULT_MCP_URL = "http://localhost:8061/mcp"

_CATALOG: dict[str, dict[str, Any]] | None = None


def _catalog() -> dict[str, dict[str, Any]]:
    """Load (and memoize) the pattern catalog keyed by pattern name."""
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


def resolve_mcp_url(mcp_url: str | None) -> str:
    """Explicit flag > BENCH_MCP_URL env > default dev endpoint."""
    return mcp_url or os.environ.get("BENCH_MCP_URL") or DEFAULT_MCP_URL


@dataclass(frozen=True)
class E2ERun:
    """One scenario's wire-mode outcome.

    Attributes:
        scenario: The scenario that ran.
        output: Parsed ``DesignAgentSystemOutput``-shaped payload.
        score: Selection-quality metrics computed from the output.
        recorder: Stage records (``e2e.http`` per call).
        e2e_ms: Scenario wall clock measured at the run boundary.
    """

    scenario: BenchmarkScenario
    output: dict[str, Any]
    score: ScenarioScore
    recorder: StageRecorder
    e2e_ms: float | None = None


async def run_e2e_scenario(
    scenario: BenchmarkScenario,
    mcp_url: str,
    call_timeout_s: float,
) -> E2ERun:
    """Call the MCP design tool once for one scenario and score it."""
    catalog = _catalog()
    winner = scenario.acceptable_primary[0]
    recorder = StageRecorder()

    total_start = time.monotonic_ns()
    async with Client(mcp_url, timeout=call_timeout_s) as client:
        call_start = time.monotonic_ns()
        result = await client.call_tool(
            "design_agent_system",
            {
                "requirements": scenario.requirements,
                "domain": scenario.domain,
            },
        )
        recorder.add(
            StageRecord(
                stage=STAGE_E2E_HTTP,
                op=OP_HTTP,
                started_ns=call_start,
                duration_ms=(time.monotonic_ns() - call_start) / 1e6,
                ok=True,
                meta={"url": mcp_url},
            )
        )
    output: dict[str, Any] = (
        result.data if hasattr(result, "data") else json.loads(str(result))
    )
    e2e_ms = round((time.monotonic_ns() - total_start) / 1e6, 3)

    selected_names = _selected_names_from_output(output)
    top_score = _top_score_from_output(output)
    score = score_scenario(
        scenario_id=scenario.scenario_id,
        primaries=scenario.acceptable_primary,
        winner_topology=str(catalog[winner]["topology"]),
        selected_names=selected_names,
        top_blended_score=top_score,
        final_pattern_name=str(output.get("final_pattern_name", "")),
        final_topology=str(output.get("final_topology", "")),
        is_fallback=bool(output.get("is_fallback", False)),
    )
    score = replace(
        score,
        confidence=max(0.0, min(1.0, float(output.get("final_quality_score", 0.0)) / 100.0)),
    )
    return E2ERun(
        scenario=scenario, output=output, score=score, recorder=recorder,
        e2e_ms=e2e_ms,
    )


def _quality_candidates(output: dict[str, Any]) -> list[Any] | None:
    """pattern_candidates list from quality metrics when shaped as expected."""
    quality: Any = output.get("quality_metrics") or {}
    if not isinstance(quality, dict):
        return None
    candidates = quality.get("pattern_candidates")
    if isinstance(candidates, list):
        return list(candidates)
    return None


def _selected_names_from_output(output: dict[str, Any]) -> list[str]:
    """Extract selected-pattern names from the wire output."""
    candidates = _quality_candidates(output)
    if candidates is not None:
        names = [
            str(c.get("name", ""))
            for c in candidates
            if isinstance(c, dict) and c.get("name")
        ]
        if names:
            return names
    final = str(output.get("final_pattern_name", ""))
    return [final] if final else []


def _top_score_from_output(output: dict[str, Any]) -> float | None:
    """Top blended score from quality metrics when present."""
    candidates = _quality_candidates(output)
    if candidates:
        first = candidates[0]
        if isinstance(first, dict) and first.get("blended_score") is not None:
            return float(first["blended_score"])
    return None


async def run_e2e_corpus(
    scenarios: list[BenchmarkScenario],
    mcp_url: str,
    call_timeout_s: float,
) -> list[E2ERun]:
    """Run every scenario over the wire."""
    return [await run_e2e_scenario(s, mcp_url, call_timeout_s) for s in scenarios]


@dataclass(frozen=True)
class E2EOutcome:
    """One scenario's wire-mode outcome, successful or failed.

    A failed call is recorded (``error`` set, zeroed score) so the arm
    completes; ``fail_fast`` restores abort-on-first-failure.
    """

    scenario: BenchmarkScenario
    output: dict[str, Any]
    score: ScenarioScore
    recorder: StageRecorder
    error: str | None = None
    e2e_ms: float | None = None


async def run_e2e_corpus_tolerant(
    scenarios: list[BenchmarkScenario],
    mcp_url: str,
    call_timeout_s: float,
    *,
    fail_fast: bool = False,
) -> list[E2EOutcome]:
    """Run the corpus over the wire, recording per-scenario failures."""
    outcomes: list[E2EOutcome] = []
    for scenario in scenarios:
        try:
            run = await run_e2e_scenario(scenario, mcp_url, call_timeout_s)
        except Exception as exc:  # noqa: BLE001 — recorded, then the arm continues
            if fail_fast:
                raise
            error = f"{type(exc).__name__}: {exc}"
            recorder = StageRecorder()
            recorder.add(
                StageRecord(
                    stage=STAGE_E2E_HTTP,
                    op=OP_HTTP,
                    started_ns=time.monotonic_ns(),
                    duration_ms=0.0,
                    ok=False,
                    meta={"scenario_id": scenario.scenario_id, "error": error},
                )
            )
            outcomes.append(
                E2EOutcome(
                    scenario=scenario,
                    output={},
                    score=score_failure(scenario.scenario_id, error),
                    recorder=recorder,
                    error=error,
                )
            )
            continue
        outcomes.append(
            E2EOutcome(
                scenario=run.scenario,
                output=run.output,
                score=run.score,
                recorder=run.recorder,
                error=None,
                e2e_ms=run.e2e_ms,
            )
        )
    return outcomes
