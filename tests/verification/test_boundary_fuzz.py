# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT

"""
L1b boundary fuzz over the MCP tool surface (testing-strategies §3.3).

Layer split: the SCHEMA layer (pydantic validation of tool parameters) is
asserted via TypeAdapter over the handlers' Annotated annotations; the
HANDLER layer is exercised with schema-valid but adversarial strings
(oversized, control/format characters, unicode) plus generated job ids.
Tools run in-process with mocked pipeline/agent — no transport, no LLM.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, get_args, get_origin, get_type_hints
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.exceptions import ToolError
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import TypeAdapter, ValidationError

import src.tools  # noqa: F401 — registration surface under test
from src.schemas.quality import QualityMetrics
from src.tools._adapters import design_from_dict
from src.tools.analyze import AnalyzeAgentSystemTool
from src.tools.cancel_agent_design import CancelAgentDesignTool
from src.tools.design import DesignAgentSystemTool
from src.tools.evaluate import EvaluateAgentSystemTool
from src.tools.generate import GenerateAgentSystemTool
from src.tools.get_agent_design_status import GetAgentDesignStatusTool
from src.tools.patterns import (
    GetAgentPatternTool,
    ListAgentPatternsTool,
)
from src.tools.submit_agent_design import SubmitAgentDesignJobTool

from tests.verification.strategies import any_text, clean_visible_text

StructuredError = (ToolError, ValidationError, ValueError)

_TRACEBACK_MARKERS = (
    "Traceback (most recent call last)",
    'File "',
)


def _assert_no_leak(text: str) -> None:
    for marker in _TRACEBACK_MARKERS:
        assert marker not in text, f"L1b leak ({marker!r}): {text[:300]}"


async def _invoke_bounded(
    handler: Callable[..., Any], kwargs: dict[str, Any]
) -> Any:
    """Call a tool handler, enforcing the L1b assertion template."""
    sig = inspect.signature(handler)
    call_kwargs = {
        k: v for k, v in kwargs.items() if k in sig.parameters and k != "ctx"
    }
    try:
        result = handler(**call_kwargs)
        if isinstance(result, Awaitable):
            result = await result
    except StructuredError as exc:
        _assert_no_leak(f"{type(exc).__name__}: {exc}")
        return {"__error__": type(exc).__name__}
    except Exception as exc:  # noqa: BLE001 — the L1b finding IS this branch
        pytest.fail(
            f"L1b violation: raw {type(exc).__name__} escaped the tool "
            f"boundary: {exc}"
        )
    if isinstance(result, dict):
        _assert_no_leak(str(result)[:2000])
    return result


def _mock_pipeline_result() -> Any:
    from src.pipeline import AnalysisResult as PipelineAnalysisResult

    return PipelineAnalysisResult(
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


class _AsyncPipelineMock(MagicMock):
    """Pipeline double: AsyncMock ONLY for the methods production awaits.

    The tool handlers await exactly ``analyze`` / ``generate`` /
    ``evaluate`` / ``run_design`` (verified by grep over src/tools). Every
    other attribute is a plain MagicMock so that output-mapping code which
    CALLS pipeline-result attributes without awaiting (a legitimate
    production pattern) never creates an unawaited coroutine.
    """

    _AWAITED_METHODS = frozenset({"analyze", "generate", "evaluate", "run_design"})

    def __getattr__(self, item: str) -> Any:
        if item.startswith("_"):
            raise AttributeError(item)
        if item in self._AWAITED_METHODS:
            mock_obj: Any = AsyncMock(name=item)
        else:
            mock_obj = MagicMock(name=item)
        setattr(self, item, mock_obj)
        return mock_obj


def _real_design() -> Any:
    """A real AgentSystemDesign so output mapping runs the success path."""
    from src.schemas import (
        Agent,
        AgentSystemDesign,
        AgentSystemOverview,
    )
    from src.schemas.enums import AgentTopology, PatternCategory

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


def _real_evaluation(score: float) -> Any:
    from src.schemas import (
        AgentSystemEvaluation,
        EvaluationSummary,
        MetricResult,
    )

    return AgentSystemEvaluation(
        summary=EvaluationSummary(
            reasoning="r",
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


def _real_pipeline_result() -> Any:
    """A real PipelineResult for the design/submit run_design path."""
    from src.schemas import PipelineResult, QualityMetrics

    return PipelineResult(
        design=_real_design(),
        evaluation=_real_evaluation(80.0),
        attempts=1,
        final_topology="hierarchical",
        quality_metrics=QualityMetrics(
            reliability=8.0,
            cost_efficiency=8.0,
            latency=8.0,
            output_quality=8.0,
            observability=8.0,
            safety=8.0,
        ),
    )


def _pipeline_mock() -> _AsyncPipelineMock:
    """Pipeline double for the tool handlers.

    Every awaited method returns a REAL typed result so the handlers run
    their SUCCESS path — output mapping over mock-attribute swamps would
    both weaken the fuzz claim and leak unawaited AsyncMock coroutines.
    """
    pipeline = _AsyncPipelineMock(name="pipeline")
    pipeline.analyze = AsyncMock(return_value=_mock_pipeline_result())
    pipeline.generate = AsyncMock(return_value=_real_design())
    pipeline.evaluate = AsyncMock(return_value=_real_evaluation(80.0))
    pipeline.run_design = AsyncMock(return_value=_real_pipeline_result())
    return pipeline


def _schema_rejects(annotation: object, payload: object) -> bool:
    """True when the pydantic layer rejects the payload for this annotation."""
    if get_origin(annotation) is not None and get_args(annotation):
        try:
            TypeAdapter(annotation).validate_python(payload)
        except ValidationError:
            return True
        return False
    return False


_requirements_domain: dict[str, st.SearchStrategy[object]] = {
    "requirements": st.one_of(clean_visible_text(2000), any_text(200)),
    "domain": st.one_of(clean_visible_text(150), any_text(120)),
}


class TestAnalyzeBoundary:
    @given(
        requirements=_requirements_domain["requirements"],
        domain=_requirements_domain["domain"],
    )
    @settings(max_examples=15, deadline=None)
    async def test_handler_never_leaks_raw_exceptions(
        self, requirements: str, domain: str
    ) -> None:
        tool = AnalyzeAgentSystemTool(
            agent=MagicMock(name="agent"), pipeline=_pipeline_mock()
        )
        await _invoke_bounded(
            tool.analyze, {"requirements": requirements, "domain": domain}
        )

    @given(
        bad=st.one_of(
            st.integers(),
            st.lists(st.integers(), max_size=3),
            st.none(),
        )
    )
    @settings(max_examples=10, deadline=None)
    def test_wrong_type_rejected_at_schema_layer(self, bad: object) -> None:
        hints = get_type_hints(AnalyzeAgentSystemTool.analyze, include_extras=True)
        assert _schema_rejects(hints["requirements"], bad), (
            f"schema accepted wrong-typed requirements: {bad!r}"
        )


class TestGenerateDesignBoundary:
    @given(
        requirements=_requirements_domain["requirements"],
        topology=st.one_of(clean_visible_text(40), any_text(40)),
        domain=_requirements_domain["domain"],
    )
    @settings(max_examples=8, deadline=None)
    async def test_generate_never_leaks(
        self, requirements: str, topology: str, domain: str
    ) -> None:
        tool = GenerateAgentSystemTool(
            agent=MagicMock(name="agent"), pipeline=_pipeline_mock()
        )
        await _invoke_bounded(
            tool.generate,
            {"requirements": requirements, "topology": topology, "domain": domain},
        )

    @given(
        requirements=_requirements_domain["requirements"],
        domain=_requirements_domain["domain"],
    )
    @settings(max_examples=8, deadline=None)
    async def test_design_never_leaks(self, requirements: str, domain: str) -> None:
        tool = DesignAgentSystemTool(
            agent=MagicMock(name="agent"), pipeline=_pipeline_mock()
        )
        await _invoke_bounded(
            tool.design, {"requirements": requirements, "domain": domain}
        )


class TestEvaluateBoundary:
    @given(
        garbage=st.one_of(
            st.dictionaries(st.text(max_size=8), st.integers(), max_size=3),
            st.lists(st.integers(), max_size=3),
            st.text(max_size=40),
        ),
        criteria=clean_visible_text(200),
    )
    @settings(max_examples=10, deadline=None)
    async def test_garbage_design_raises_structured_only(
        self, garbage: object, criteria: str
    ) -> None:
        tool = EvaluateAgentSystemTool(
            agent=MagicMock(name="agent"), pipeline=_pipeline_mock()
        )
        await _invoke_bounded(
            tool.evaluate,
            {
                "agent_system": garbage,
                "criteria": criteria,
                "domain": "generated-domain",
            },
        )


class TestJobTrioBoundary:
    @given(job_id=st.one_of(any_text(120), st.integers(0, 10**6)))
    @settings(max_examples=10, deadline=None)
    async def test_get_status_never_leaks(self, job_id: object) -> None:
        tool = GetAgentDesignStatusTool()
        await _invoke_bounded(tool.get_status, {"job_id": job_id})

    @given(job_id=st.one_of(any_text(120), st.integers(0, 10**6)))
    @settings(max_examples=10, deadline=None)
    async def test_cancel_never_leaks(self, job_id: object) -> None:
        tool = CancelAgentDesignTool()
        await _invoke_bounded(tool.cancel, {"job_id": job_id})

    @given(
        requirements=_requirements_domain["requirements"],
        domain=_requirements_domain["domain"],
    )
    @settings(max_examples=8, deadline=None)
    async def test_submit_never_leaks(self, requirements: str, domain: str) -> None:
        tool = SubmitAgentDesignJobTool(
            agent=MagicMock(name="agent"), pipeline=_pipeline_mock()
        )
        await _invoke_bounded(
            tool.submit_job, {"requirements": requirements, "domain": domain}
        )


class TestPatternsBoundary:
    @given(name=st.one_of(any_text(120), clean_visible_text(60)))
    @settings(max_examples=10, deadline=None)
    async def test_get_pattern_never_leaks(self, name: str) -> None:
        loader = MagicMock(name="loader")
        loader.get_by_name.return_value = {
            "name": "x", "context": "c", "category": "multi_agent",
        }
        tool = GetAgentPatternTool(pattern_loader=loader)
        await _invoke_bounded(tool.get_agent_pattern, {"name": name})

    async def test_list_patterns_never_leaks(self) -> None:
        loader = MagicMock(name="loader")
        loader.list_patterns.return_value = []
        tool = ListAgentPatternsTool(pattern_loader=loader)
        await _invoke_bounded(tool.list_agent_patterns, {})


class TestAdaptersBoundary:
    """ERR_012 boundary: malformed overviews raise the structured error —
    never KeyError/TypeError escaping raw, never a silent default."""

    @given(
        garbage=st.one_of(
            st.dictionaries(st.text(max_size=10), st.integers(), max_size=4),
            st.lists(st.integers(), max_size=4),
            st.text(max_size=40),
            st.none(),
        )
    )
    @settings(max_examples=15, deadline=None)
    def test_design_from_dict_rejects_garbage_structured(self, garbage: object) -> None:
        from src.errors import MalformedAgentSystemOverviewError

        try:
            design_from_dict(garbage)  # type: ignore[arg-type]
        except MalformedAgentSystemOverviewError as exc:
            _assert_no_leak(str(exc))
        except StructuredError:
            pass  # validation-layer rejection is structured too
        except Exception as exc:  # noqa: BLE001
            pytest.fail(
                f"L1b violation: raw {type(exc).__name__} escaped the adapter "
                f"boundary: {exc}"
            )


class TestRegistrationBoundary:
    def test_tools_package_imports_cleanly(self) -> None:
        assert hasattr(src_tools_module(), "create_all_tools")


def src_tools_module() -> object:
    import sys

    return sys.modules["src.tools"]
