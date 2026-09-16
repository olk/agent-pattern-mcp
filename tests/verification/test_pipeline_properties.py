# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT

"""
L2 property oracles for the design-loop control decisions
(testing-strategies §3.3; ledger families P/DL/FP — design_loop.fizz and
pipeline_control.fizz are the exhaustive peers).

  P-1  attempts never exceed max_tries (generate and evaluate both).
  DL-2 the delivered final_quality_score is the MAX of the scores seen
       across accepted attempts — a later lower score cannot displace it.
  DL-3 a CancelledError raised by an attempt stops the loop: no attempt
       may start after cancellation is observed.
  FP-2 a pre-cancelled token makes zero stage calls.
  FP-3 a token set mid-run stops the NEXT attempt; the in-flight attempt
       legitimately completes.
  DL-4 malformed attempts consume attempts and retry — they never end the
       loop early; all-malformed runs re-raise the last structured error.
  DL-5 early stop fires only at/above min_quality_score.
  FP-4 exactly one terminal outcome per run: completed | failed_malformed
       | failed_no_design.
  FP-6 a run never ends COMPLETED without a valid attempt.
  FP-7 a result is only delivered after >= 1 full attempt.

FP-3 (stage order) and FP-5 (eventual outcome, liveness) stay
fizz-owned: FP-3's witness lives in the Workflow event machinery and
FP-5 is ``bounded — not sampleable`` (ledger carries the justification).

Direction of the implication: this oracle samples schedule space;
``design_loop.fizz``/``pipeline_control.fizz`` check it exhaustively up
to bounds.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import RetrievalConfig
from src.errors import MalformedAgentSystemOverviewError
from src.pipeline import (
    AgentPatternPipeline,
    AnalysisResult,
    CancellationToken,
    PipelineResult,
)
from src.schemas import (
    Agent,
    AgentSystemDesign,
    AgentSystemEvaluation,
    AgentSystemOverview,
    EvaluationSummary,
    MetricResult,
    QualityMetrics,
)
from src.schemas.enums import AgentTopology, PatternCategory

_NEVER_EARLY_STOP = 1e9

_cancel_after_strategy: st.SearchStrategy[int | None] = st.one_of(
    st.none(), st.integers(min_value=1, max_value=4)
)


def _analysis_result() -> AnalysisResult:
    return AnalysisResult(
        strengths=["s"],
        weaknesses=["w"],
        recommendations=["r"],
        quality_metrics=QualityMetrics(
            reliability=8.0,
            cost_efficiency=8.0,
            latency=8.0,
            output_quality=8.0,
            observability=8.0,
            safety=8.0,
        ),
        recommended_topology="hierarchical",
        selected_patterns=[],
    )


def _design() -> AgentSystemDesign:
    return AgentSystemDesign(
        overview=AgentSystemOverview(
            topology=AgentTopology.HIERARCHICAL,
            category=PatternCategory.MULTI_AGENT,
            principles=["p"],
        ),
        agents=[
            Agent(id="planner", name="Planner", role="planner",
                  description="d", responsibilities=["r"])
        ],
        relationships=[],
        quality_attributes={},
        tool_contracts=[],
        shared_state_models=[],
        message_contracts=[],
    )


def _evaluation(score: float) -> AgentSystemEvaluation:
    return AgentSystemEvaluation(
        summary=EvaluationSummary(
            reasoning="scripted",
            overall_score=score,
            strengths=["s"],
            weaknesses=["w"],
            critical_findings=[],
        ),
        metrics=[MetricResult(name="overall_quality", score=score, description="")],
        risks=[],
        compliance=[],
        recommendations={},
    )


class _ScriptedPipeline(AgentPatternPipeline):
    """design_loop with scripted generate/evaluate; the REAL loop runs.

    Score consumption is keyed to the ATTEMPT number (generate_calls), so
    malformed attempts shift evaluation scores exactly like production.
    """

    def __init__(self) -> None:
        self._cancellation_token: CancellationToken | None = None
        self._retrieval_config = RetrievalConfig()
        # Reasoning disabled: _reasoning_block takes the production
        # degraded path (empty context) — no reasoning subprocess needed.
        self._reasoning_client = None
        self.generate_calls = 0
        self.evaluate_calls = 0
        self.malformed_at: frozenset[int] = frozenset()
        self.cancelled_error_at: int | None = None
        self.cancel_token_after: int | None = None
        self.score_sequence: list[float] = [50.0]

    async def generate(self, *_args: Any, **_kwargs: Any) -> AgentSystemDesign:
        self.generate_calls += 1
        if self.cancelled_error_at == self.generate_calls:
            raise asyncio.CancelledError
        if self.cancel_token_after == self.generate_calls and self._cancellation_token:
            self._cancellation_token.cancel()
        if self.generate_calls in self.malformed_at:
            raise MalformedAgentSystemOverviewError(
                locator="overview",
                errors=[
                    {
                        "loc": ("overview",),
                        "msg": "scripted malformed attempt",
                        "type": "model_type",
                    }
                ],
            )
        return _design()

    async def evaluate(self, *_args: Any, **_kwargs: Any) -> AgentSystemEvaluation:
        self.evaluate_calls += 1
        idx = min(self.generate_calls, len(self.score_sequence)) - 1
        return _evaluation(self.score_sequence[idx])


def _make(schedule: dict[str, Any]) -> _ScriptedPipeline:
    pipeline = _ScriptedPipeline()
    pipeline.malformed_at = schedule["malformed_at"]
    pipeline.cancelled_error_at = schedule["cancelled_error_at"]
    pipeline.cancel_token_after = schedule["cancel_token_after"]
    pipeline.score_sequence = schedule["score_sequence"]
    token = schedule["pre_cancelled"]
    pipeline._cancellation_token = token  # noqa: SLF001 — injection seam
    return pipeline


def _run_loop(
    pipeline: _ScriptedPipeline, max_tries: int, threshold: float
) -> PipelineResult:
    return asyncio.run(
        pipeline.design_loop(
            requirements="req",
            domain="dom",
            topology="hierarchical",
            selected_patterns=[],
            criteria="quality",
            analysis_result=_analysis_result(),
            max_tries=max_tries,
            min_quality_score=threshold,
        )
    )


def _run_terminal(
    pipeline: _ScriptedPipeline, max_tries: int, threshold: float
) -> tuple[str, int]:
    """Drive the loop to exactly one terminal outcome; tag it (FP-4)."""
    try:
        result = _run_loop(pipeline, max_tries, threshold)
    except MalformedAgentSystemOverviewError:
        return ("failed_malformed", pipeline.generate_calls)
    except RuntimeError:
        return ("failed_no_design", pipeline.generate_calls)
    return ("completed", result.attempts)


_schedule_strategy: st.SearchStrategy[dict[str, Any]] = st.fixed_dictionaries(
    {
        "malformed_at": st.sets(st.integers(min_value=1, max_value=4), max_size=3).map(
            lambda s: frozenset(s)
        ),
        "cancelled_error_at": _cancel_after_strategy,
        "cancel_token_after": _cancel_after_strategy,
        "score_sequence": st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=4,
        ),
        "pre_cancelled": st.sampled_from([None]),
    }
)


class TestP1AttemptBound:
    @given(
        schedule=_schedule_strategy,
        max_tries=st.integers(min_value=1, max_value=4),
    )
    @settings(max_examples=25, deadline=None)
    def test_attempts_never_exceed_max_tries(
        self, schedule: dict[str, Any], max_tries: int
    ) -> None:
        pipeline = _make(schedule)
        _outcome, generate_calls = _run_terminal(pipeline, max_tries, _NEVER_EARLY_STOP)
        assert generate_calls <= max_tries, "P-1 violated: generate ran past the bound"
        assert pipeline.evaluate_calls <= max_tries


class TestDL2BestScoreGuard:
    @given(
        scores=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=4,
        ),
        max_tries=st.integers(min_value=1, max_value=4),
    )
    @settings(max_examples=25, deadline=None)
    def test_delivered_score_is_max_of_seen(
        self, scores: list[float], max_tries: int
    ) -> None:
        schedule: dict[str, Any] = {
            "malformed_at": frozenset(),
            "cancelled_error_at": None,
            "cancel_token_after": None,
            "score_sequence": scores,
            "pre_cancelled": None,
        }
        pipeline = _make(schedule)
        result: PipelineResult = _run_loop(pipeline, max_tries, _NEVER_EARLY_STOP)
        seen = scores[: result.attempts]
        assert result.final_quality_score == max(seen), (
            f"DL-2: delivered {result.final_quality_score} != max {max(seen)}"
        )
        # A later lower score cannot displace the delivered best.
        assert result.final_quality_score >= min(seen)


class TestDL3CancelFreezes:
    @given(
        cancel_at=st.integers(min_value=1, max_value=4),
        max_tries=st.integers(min_value=1, max_value=4),
    )
    @settings(max_examples=20, deadline=None)
    def test_cancelled_error_stops_further_attempts(
        self, cancel_at: int, max_tries: int
    ) -> None:
        schedule: dict[str, Any] = {
            "malformed_at": frozenset(),
            "cancelled_error_at": cancel_at,
            "cancel_token_after": None,
            "score_sequence": [60.0],
            "pre_cancelled": None,
        }
        pipeline = _make(schedule)
        outcome, generate_calls = _run_terminal(pipeline, max_tries, _NEVER_EARLY_STOP)
        if cancel_at <= max_tries:
            # The cancelled attempt STARTED: nothing may run after it.
            assert generate_calls == cancel_at, (
                "DL-3: no attempt may start after cancellation is observed"
            )
            assert pipeline.evaluate_calls == cancel_at - 1
            if cancel_at == 1:
                assert outcome == "failed_no_design"
            else:
                assert outcome == "completed"
        else:
            # The max_tries bound exhausted before the cancel schedule fired.
            assert generate_calls == max_tries
            assert pipeline.evaluate_calls == max_tries
            assert outcome == "completed"

    def test_fp2_pre_cancelled_run_makes_zero_calls(self) -> None:
        schedule: dict[str, Any] = {
            "malformed_at": frozenset(),
            "cancelled_error_at": None,
            "cancel_token_after": None,
            "score_sequence": [60.0],
            "pre_cancelled": CancellationToken(),
        }
        token: CancellationToken = schedule["pre_cancelled"]
        token.cancel()
        pipeline = _make(schedule)
        assert token.cancelled()
        outcome, generate_calls = _run_terminal(pipeline, 3, _NEVER_EARLY_STOP)
        assert generate_calls == 0, "FP-2: no stage advance after observed cancellation"
        assert outcome == "failed_no_design"

    def test_token_set_mid_run_stops_next_attempt(self) -> None:
        schedule: dict[str, Any] = {
            "malformed_at": frozenset(),
            "cancelled_error_at": None,
            "cancel_token_after": 1,
            "score_sequence": [40.0, 90.0, 95.0],
            "pre_cancelled": CancellationToken(),
        }
        token: CancellationToken = schedule["pre_cancelled"]
        assert not token.cancelled()
        pipeline = _make(schedule)
        outcome, generate_calls = _run_terminal(pipeline, 3, _NEVER_EARLY_STOP)
        assert token.cancelled(), "the scripted attempt must have fired the token"
        # The token fires DURING attempt 1; attempt 2 must never start (DL-3),
        # while attempt 1 itself legitimately completes (generate + evaluate).
        assert generate_calls == 1
        assert pipeline.evaluate_calls == 1
        assert outcome == "completed"


class TestDL4MalformedContinues:
    @given(
        malformed_at=st.sets(st.integers(min_value=1, max_value=4), max_size=3).map(
            lambda s: frozenset(s)
        ),
        max_tries=st.integers(min_value=1, max_value=4),
    )
    @settings(max_examples=25, deadline=None)
    def test_malformed_attempts_retry_not_terminate(
        self, malformed_at: frozenset[int], max_tries: int
    ) -> None:
        schedule: dict[str, Any] = {
            "malformed_at": malformed_at,
            "cancelled_error_at": None,
            "cancel_token_after": None,
            "score_sequence": [55.0, 65.0, 75.0, 85.0],
            "pre_cancelled": None,
        }
        pipeline = _make(schedule)
        outcome, generate_calls = _run_terminal(pipeline, max_tries, _NEVER_EARLY_STOP)
        assert generate_calls == max_tries, (
            "DL-4: malformed attempts consume attempts, never end the loop early"
        )
        if malformed_at >= set(range(1, max_tries + 1)):
            assert outcome == "failed_malformed", (
                "all-malformed runs must re-raise the last structured error"
            )
            return
        assert outcome == "completed"
        # Fresh pipeline: counters must not leak between runs.
        pipeline2 = _make(schedule)
        result: PipelineResult = _run_loop(pipeline2, max_tries, _NEVER_EARLY_STOP)
        valid = [i for i in range(1, generate_calls + 1) if i not in malformed_at]
        assert valid, "FP-6: at least one valid attempt by construction"
        expected_best = max(
            schedule["score_sequence"][min(i, len(schedule["score_sequence"])) - 1]
            for i in valid
        )
        assert result.final_quality_score == expected_best


class TestDL5EarlyStopThreshold:
    @given(
        first_score=st.floats(
            min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False
        ),
        threshold=st.floats(
            min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False
        ),
        max_tries=st.integers(min_value=2, max_value=4),
    )
    @settings(max_examples=40, deadline=None)
    def test_early_stop_only_at_or_above_threshold(
        self, first_score: float, threshold: float, max_tries: int
    ) -> None:
        schedule: dict[str, Any] = {
            "malformed_at": frozenset(),
            "cancelled_error_at": None,
            "cancel_token_after": None,
            "score_sequence": [first_score, 0.0, 0.0, 0.0],
            "pre_cancelled": None,
        }
        pipeline = _make(schedule)
        outcome, generate_calls = _run_terminal(pipeline, max_tries, threshold)
        assert outcome == "completed"
        if first_score >= threshold:
            assert generate_calls == 1, "DL-5: early stop fires at/above threshold"
        else:
            assert generate_calls == max_tries, "DL-5: below threshold keeps retrying"


class TestFPTerminalDiscipline:
    @given(
        schedule=_schedule_strategy, max_tries=st.integers(min_value=1, max_value=4)
    )
    @settings(max_examples=30, deadline=None)
    def test_fp4_exactly_one_terminal_outcome(
        self, schedule: dict[str, Any], max_tries: int
    ) -> None:
        pipeline = _make(schedule)
        outcome, generate_calls = _run_terminal(pipeline, max_tries, _NEVER_EARLY_STOP)
        assert outcome in ("completed", "failed_malformed", "failed_no_design")
        if outcome == "completed":
            # FP-7: a result only after a full attempt ran.
            assert generate_calls >= 1
            assert pipeline.evaluate_calls >= 1
            # FP-6: never COMPLETED without a valid attempt.
            attempted = set(range(1, generate_calls + 1))
            assert attempted - set(schedule["malformed_at"]), (
                "FP-6 violation: COMPLETED despite zero valid attempts"
            )
        if outcome == "failed_no_design":
            assert generate_calls >= 1 or schedule["pre_cancelled"] is not None
