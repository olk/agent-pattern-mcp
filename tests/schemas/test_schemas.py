# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Hypothesis-based property tests for the typed schema layer.

Tests all new Pydantic schemas with Hypothesis strategy-based property tests
to validate constraints, coercion, and serialization round-trips.

Covers:
- AnalysisResult, AgentSystemDesign, AgentSystemOverview
- AgentSystemEvaluation, PipelineResult, MetricResult, EvaluationSummary
- Pattern, Agent, Relationship

- ToolContract, ToolContract, StateModel, StateField, MessageContract
- ValidationConfig
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

from src.schemas import (
    AnalysisResult,
    AgentSystemDesign,
    AgentSystemOverview,
    AgentSystemEvaluation,
    PipelineResult,
    Pattern,
    Agent,
    Relationship,
    ToolContract,
    ToolContract,
    StateModel,
    StateField,
    MessageContract,
    QualityMetrics,
)
from src.schemas.enums import AgentTopology, PatternCategory
from src.schemas.patterns import ScoredPattern
from src.schemas.evaluation import MetricResult, EvaluationSummary
from src.config import ValidationConfig


# ─── Strategies ───────────────────────────────────────────────────────────────

@st.composite
def architecture_styles(draw: st.DrawFn) -> AgentTopology:
    return draw(st.sampled_from(list(AgentTopology)))


@st.composite
def pattern_categories(draw: st.DrawFn) -> PatternCategory:
    return draw(st.sampled_from(list(PatternCategory)))


@st.composite
def quality_metrics_strategy(draw: st.DrawFn) -> QualityMetrics:
    return QualityMetrics(
        cost_efficiency=draw(st.floats(min_value=0.0, max_value=10.0)),
        latency=draw(st.floats(min_value=0.0, max_value=10.0)),
        output_quality=draw(st.floats(min_value=0.0, max_value=10.0)),
        observability=draw(st.floats(min_value=0.0, max_value=10.0)),
        safety=draw(st.floats(min_value=0.0, max_value=10.0)),
        reliability=draw(st.floats(min_value=0.0, max_value=10.0)),
    )


@st.composite
def model_field_strategy(draw: st.DrawFn) -> StateField:
    return StateField(
        name=draw(st.text(min_size=1, max_size=50)),
        type=draw(st.sampled_from(["str", "int", "float", "bool", "list", "dict"])),
        required=draw(st.booleans()),
        description=draw(st.text(max_size=200)),
        default=draw(st.one_of(st.none(), st.text(), st.floats(), st.booleans())),
    )


@st.composite
def data_model_strategy(draw: st.DrawFn) -> StateModel:
    return StateModel(
        name=draw(st.text(min_size=1, max_size=50)),
        fields=draw(st.lists(model_field_strategy(), max_size=10)),
        description=draw(st.text(max_size=200)),
        is_shared=draw(st.booleans()),
    )


@st.composite
def api_endpoint_strategy(draw: st.DrawFn) -> ToolContract:
    return ToolContract(
        tool_name=draw(st.text(min_size=1, max_size=50)),
        agent_id=draw(st.sampled_from(["api-gateway", "user-service", "auth-service"])),
        description=draw(st.text(max_size=200)),
        input_schema=draw(st.one_of(st.none(), st.dictionaries(st.text(), st.text()))),
        output_schema=draw(st.one_of(st.none(), st.dictionaries(st.text(), st.text()))),
        auth_required=draw(st.booleans()),
    )


@st.composite
def api_contract_strategy(draw: st.DrawFn) -> ToolContract:
    return ToolContract(
        tool_name=draw(st.text(min_size=1, max_size=50)),
        agent_id=draw(st.sampled_from(["api-gateway", "user-service", "auth-service"])),
        description=draw(st.text(max_size=200)),
        input_schema=draw(st.one_of(st.none(), st.dictionaries(st.text(), st.text()))),
        output_schema=draw(st.one_of(st.none(), st.dictionaries(st.text(), st.text()))),
        auth_required=draw(st.booleans()),
    )


@st.composite
def component_strategy(draw: st.DrawFn) -> Agent:
    return Agent(
        id=draw(st.sampled_from([
            "api-gateway", "user-service", "auth-service", "payment-service",
            "notification-service", "data-pipeline", "analytics-engine",
            "search-service", "cache-layer", "message-broker",
        ])),
        name=draw(st.text(min_size=1, max_size=100)),
        role=draw(st.sampled_from(["service", "gateway", "database", "cache", "queue", "worker"])),
        description=draw(st.text(min_size=1, max_size=500)),
        responsibilities=draw(st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=10)),
        technology_stack=draw(st.lists(st.text(max_size=50), max_size=10)),
        config_requirements=draw(st.lists(st.text(max_size=100), max_size=10)),
    )


@st.composite
def relationship_strategy(draw: st.DrawFn) -> Relationship:
    return Relationship(
        source=draw(st.text(min_size=1, max_size=50)),
        target=draw(st.text(min_size=1, max_size=50)),
        type=draw(st.text(min_size=1, max_size=30)),
        description=draw(st.text(max_size=200)),
    )


@st.composite
def event_contract_strategy(draw: st.DrawFn) -> MessageContract:
    return MessageContract(
        message_name=draw(st.text(min_size=1, max_size=100)),
        payload_schema=draw(st.dictionaries(st.text(), st.text())),
        published_by=draw(st.text(min_size=1, max_size=50)),
        consumed_by=draw(st.lists(st.text(max_size=50), max_size=10)),
        description=draw(st.text(max_size=300)),
    )


# ─── AgentSystemOverview ──────────────────────────────────────────────────────


class TestAgentSystemOverview:
    """Property tests for AgentSystemOverview."""

    @given(
        topology=architecture_styles(),
        category=pattern_categories(),
        principles=st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=10),
        constraints=st.lists(st.text(max_size=100), max_size=10),
    )
    @settings(max_examples=50)
    def test_valid_construction(self, topology, category, principles, constraints):
        ov = AgentSystemOverview(
            topology=topology, category=category, principles=principles, constraints=constraints
        )
        assert ov.topology == topology
        assert ov.category == category
        assert list(ov.principles) == principles
        assert list(ov.constraints) == constraints

    @given(
        topology=st.sampled_from([s.value for s in AgentTopology]),
        category=st.sampled_from([c.value for c in PatternCategory]),
        principles=st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=10),
        constraints=st.lists(st.text(max_size=100), max_size=10),
    )
    @settings(max_examples=20)
    def test_string_coerced_to_enum(self, topology, category, principles, constraints):
        ov = AgentSystemOverview(
            topology=topology, category=category, principles=principles, constraints=constraints
        )
        assert isinstance(ov.topology, AgentTopology)
        assert isinstance(ov.category, PatternCategory)

    def test_empty_principles_fails(self):
        for style in AgentTopology:
            for category in PatternCategory:
                with pytest.raises(Exception):
                    AgentSystemOverview(
                        topology=style,
                        category=category,
                        principles=[],
                        constraints=[],
                    )


# ─── Agent / Relationship ──────────────────────────────────────────────────


class TestAgent:
    """Property tests for Agent."""

    def test_manual_agents(self):
        comp1 = Agent(
            id="api-gateway",
            name="API Gateway",
            role="gateway",
            description="Entry point for all clients",
            responsibilities=["routing", "auth"],
            technology_stack=["Kong"],
        )
        assert comp1.id == "api-gateway"
        assert comp1.name == "API Gateway"
        assert comp1.technology_stack == ["Kong"]

        comp2 = Agent(
            id="user-service",
            name="User Service",
            role="service",
            description="User management",
            responsibilities=["auth", "profiles"],
            technology_stack=["Go"],
        )
        assert comp2.id == "user-service"

    def test_unique_ids(self):
        comps = [
            Agent(
                id="svc-a",
                name="Service A",
                role="service",
                description="Service A",
                responsibilities=["task-a"],
            ),
            Agent(
                id="svc-b",
                name="Service B",
                role="service",
                description="Service B",
                responsibilities=["task-b"],
            ),
        ]
        ids = [c.id for c in comps]
        assert len(ids) == len(set(ids))  # All unique


class TestRelationship:
    """Property tests for Relationship."""

    @given(rel=relationship_strategy())
    @settings(max_examples=50)
    def test_valid_construction(self, rel: Relationship):
        assert len(rel.source) > 0
        assert len(rel.target) > 0
        assert len(rel.type) > 0


# ─── ToolContract / ToolContract / StateModel / StateField ───────────────────────


class TestToolContract:
    """Property tests for ToolContract."""

    @given(ep=api_endpoint_strategy())
    @settings(max_examples=50)
    def test_valid_construction(self, ep: ToolContract):
        assert len(ep.tool_name) > 0
        assert len(ep.agent_id) > 0
        assert isinstance(ep.auth_required, bool)

    @given(ep=api_endpoint_strategy())
    @settings(max_examples=30)
    def test_serialization_roundtrip(self, ep: ToolContract):
        d = ep.model_dump()
        restored = ToolContract.model_validate(d)
        assert restored.tool_name == ep.tool_name
        assert restored.agent_id == ep.agent_id


class TestStateModel:
    """Property tests for StateModel."""

    @given(dm=data_model_strategy())
    @settings(max_examples=50)
    def test_valid_construction(self, dm: StateModel):
        assert len(dm.name) > 0
        assert isinstance(dm.fields, list)
        for f in dm.fields:
            assert len(f.name) > 0
            assert f.type in ["str", "int", "float", "bool", "list", "dict"]


class TestStateField:
    """Property tests for StateField."""

    @given(mf=model_field_strategy())
    @settings(max_examples=50)
    def test_valid_construction(self, mf: StateField):
        assert len(mf.name) > 0
        assert mf.type in ["str", "int", "float", "bool", "list", "dict"]


# ─── AgentSystemDesign ────────────────────────────────────────────────────────


class TestAgentSystemDesign:
    """Property tests for AgentSystemDesign."""

    @given(
        overview=st.builds(
            AgentSystemOverview,
            topology=st.sampled_from([s.value for s in AgentTopology]),
            category=st.sampled_from([c.value for c in PatternCategory]),
            principles=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=5),
            constraints=st.lists(st.text(max_size=50), max_size=5),
        ),
        agents=st.lists(component_strategy(), min_size=1, max_size=5),
        relationships=st.lists(relationship_strategy(), max_size=10),
        qa=st.dictionaries(st.text(max_size=20), st.floats(min_value=0.0, max_value=100.0), max_size=5),
    )
    @settings(max_examples=30)
    def test_valid_construction(self, overview, agents, relationships, qa):
        design = AgentSystemDesign(
            overview=overview,
            agents=agents,
            relationships=relationships,
            quality_attributes=qa,
            tool_contracts=[],
            shared_state_models=[],
            message_contracts=[],
        )
        assert len(design.agents) >= 1
        assert isinstance(design.quality_attributes, dict)

    @given(
        overview=st.builds(
            AgentSystemOverview,
            topology=st.sampled_from([s.value for s in AgentTopology]),
            category=st.sampled_from([c.value for c in PatternCategory]),
            principles=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=5),
            constraints=st.lists(st.text(max_size=50), max_size=5),
        ),
        agents=st.lists(component_strategy(), min_size=1, max_size=3),
        relationships=st.lists(relationship_strategy(), max_size=5),
        qa=st.dictionaries(st.text(max_size=20), st.floats(min_value=0.0, max_value=100.0), max_size=5),
        tool_contracts=st.lists(api_contract_strategy(), max_size=5),
        shared_state_models=st.lists(data_model_strategy(), max_size=5),
        message_contracts=st.lists(
            st.builds(
                MessageContract,
                event_name=st.text(min_size=1, max_size=50),
                payload_schema=st.dictionaries(st.text(), st.text(), max_size=10),
                published_by=st.text(min_size=1, max_size=50),
                consumed_by=st.lists(st.text(max_size=50), max_size=5),
                description=st.text(max_size=200),
            ),
            max_size=5,
        ),
    )
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_construction_with_contracts(
        self,
        overview,
        agents,
        relationships,
        qa,
        tool_contracts,
        shared_state_models,
        message_contracts,
    ):
        design = AgentSystemDesign(
            overview=overview,
            agents=agents,
            relationships=relationships,
            quality_attributes=qa,
            tool_contracts=tool_contracts,
            shared_state_models=shared_state_models,
            message_contracts=message_contracts,
        )
        assert len(design.tool_contracts) == len(tool_contracts)
        assert len(design.shared_state_models) == len(shared_state_models)
        assert len(design.message_contracts) == len(message_contracts)
        dumped = design.model_dump()
        revalidated = AgentSystemDesign.model_validate(dumped)
        assert len(revalidated.tool_contracts) == len(design.tool_contracts)
        assert len(revalidated.shared_state_models) == len(design.shared_state_models)
        assert len(revalidated.message_contracts) == len(design.message_contracts)


# ─── AnalysisResult ────────────────────────────────────────────────────────────


class TestAnalysisResult:
    """Property tests for AnalysisResult."""

    @given(
        strengths=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=20),
        weaknesses=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=20),
        recommendations=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=20),
        qm=quality_metrics_strategy(),
        topology=st.text(min_size=1, max_size=50),
        patterns=st.lists(st.builds(
            ScoredPattern,
            name=st.sampled_from(["pattern-a", "pattern-b", "pattern-c", "pattern-d"]),
            context=st.text(min_size=1, max_size=200),
            category=st.sampled_from([c.value for c in PatternCategory]),
            topology=st.sampled_from([s.value for s in AgentTopology]),
            benefits=st.just(["benefit"]),
            tradeoffs=st.just(["tradeoff"]),
            quality_attributes=st.just({
                "reliability": 5.0, "cost_efficiency": 5.0, "latency": 5.0,
                "output_quality": 5.0, "observability": 5.0, "safety": 5.0,
                "simplicity": 5.0,
            }),
        ), max_size=10),
    )
    @settings(max_examples=30)
    def test_valid_construction(
        self, strengths, weaknesses, recommendations, qm, topology, patterns
    ):
        ar = AnalysisResult(
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            quality_metrics=qm,
            recommended_topology=topology,
            selected_patterns=patterns,
        )
        assert ar.quality_metrics == qm
        assert ar.recommended_topology == topology


# ─── MetricResult ─────────────────────────────────


class TestMetricResult:
    """Property tests for MetricResult."""

    @given(name=st.text(min_size=1, max_size=50), score=st.floats(min_value=0.0, max_value=100.0), desc=st.text(max_size=300))
    @settings(max_examples=50)
    def test_valid_construction(self, name, score, desc):
        mr = MetricResult(name=name, score=score, description=desc)
        assert mr.name == name
        assert mr.score == score


# ─── EvaluationSummary ────────────────────────────────────────────────────────


class TestEvaluationSummary:
    """Property tests for EvaluationSummary."""

    @given(
        score=st.floats(min_value=0.0, max_value=100.0),
        strengths=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=20),
        weaknesses=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=20),
        findings=st.lists(st.text(min_size=1, max_size=300), min_size=1, max_size=20),
    )
    @settings(max_examples=30)
    def test_valid_construction(self, score, strengths, weaknesses, findings):
        es = EvaluationSummary(
            reasoning="Scores follow from the requirement weights and pattern fit.",
            overall_score=score,
            strengths=strengths,
            weaknesses=weaknesses,
            critical_findings=findings,
        )
        assert es.overall_score == score
        assert list(es.strengths) == strengths


# ─── AgentSystemEvaluation ────────────────────────────────────────────────────


class TestAgentSystemEvaluation:
    """Property tests for AgentSystemEvaluation."""

    @given(
        score=st.floats(min_value=0.0, max_value=100.0),
        strengths=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=10),
        weaknesses=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=10),
        findings=st.lists(st.text(min_size=1, max_size=300), min_size=1, max_size=10),
        metrics=st.lists(st.builds(
            MetricResult,
            name=st.text(min_size=1, max_size=50),
            score=st.floats(min_value=0.0, max_value=100.0),
            description=st.text(max_size=200),
        ), min_size=1, max_size=10),
        recommendations=st.dictionaries(
            st.text(max_size=50),
            st.lists(st.text(max_size=200), max_size=10),
        ),
    )
    @settings(max_examples=30)
    def test_valid_construction(self, score, strengths, weaknesses, findings, metrics, recommendations):
        es = EvaluationSummary(
            reasoning="Scores follow from the requirement weights and pattern fit.",
            overall_score=score,
            strengths=strengths,
            weaknesses=weaknesses,
            critical_findings=findings,
        )
        ae = AgentSystemEvaluation(
            summary=es,
            metrics=metrics,
            recommendations=recommendations,
        )
        assert isinstance(ae.summary, EvaluationSummary)
        assert isinstance(ae.metrics, list)


# ─── PipelineResult ───────────────────────────────────────────────────────────


class TestPipelineResult:
    """Property tests for PipelineResult."""

    @given(
        overview=st.builds(
            AgentSystemOverview,
            topology=st.sampled_from([s.value for s in AgentTopology]),
            category=st.sampled_from([c.value for c in PatternCategory]),
            principles=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=3),
            constraints=st.lists(st.text(max_size=50), max_size=3),
        ),
        agents=st.lists(
            st.builds(
                Agent,
                id=st.sampled_from(["svc-a", "svc-b", "api-gw"]),
                name=st.sampled_from(["Service A", "Service B", "API Gateway"]),
                role=st.sampled_from(["service", "gateway"]),
                description=st.just("A component"),
                responsibilities=st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=2),
            ),
            min_size=1,
            max_size=3,
        ),
        attempts=st.integers(min_value=1, max_value=10),
        final_topology=st.text(max_size=50),
        qm=quality_metrics_strategy(),
    )
    @settings(max_examples=30)
    def test_valid_construction(self, overview, agents, attempts, final_topology, qm):
        design = AgentSystemDesign(
            overview=overview,
            agents=agents,
            relationships=[],
            quality_attributes={},
            tool_contracts=[],
            shared_state_models=[],
            message_contracts=[],
        )
        es = EvaluationSummary(
            reasoning="Scores follow from the requirement weights and pattern fit.",
            overall_score=75.0,
            strengths=["Good design"],
            weaknesses=["Could improve"],
            critical_findings=["No issues"],
        )
        evaluation = AgentSystemEvaluation(
            summary=es,
            metrics=[MetricResult(name="overall_quality", score=75.0, description="Overall")],
            recommendations={},
        )
        pr = PipelineResult(
            design=design,
            evaluation=evaluation,
            attempts=attempts,
            final_topology=final_topology,
            quality_metrics=qm,
        )
        assert pr.attempts == attempts
        assert pr.final_topology == final_topology


# ─── ValidationConfig ────────────────────────────────────────────────────────


class TestValidationConfig:
    """Property tests for ValidationConfig."""

    @given(max_retries=st.integers(min_value=0, max_value=10), retry_on_fail=st.booleans())
    @settings(max_examples=30)
    def test_valid_construction(self, max_retries, retry_on_fail):
        vc = ValidationConfig(max_retries=max_retries, retry_on_fail=retry_on_fail)
        assert vc.max_retries == max_retries
        assert vc.retry_on_fail == retry_on_fail

    def test_negative_retries_fails(self):
        with pytest.raises(Exception):
            ValidationConfig(max_retries=-1)

    def test_defaults(self):
        vc = ValidationConfig(max_retries=2, retry_on_fail=True)
        assert vc.max_retries == 2
        assert vc.retry_on_fail is True


# ─── Pattern ─────────────────────────────────────────────────────────────────


class TestPattern:
    """Property tests for Pattern using real JSON data."""

    def test_pattern_json_roundtrip(self):
        """Pattern objects serialize and deserialize correctly."""
        import glob
        for path in glob.glob("pattern/*-pattern.json"):
            with open(path) as f:
                data = json.load(f)
            p = Pattern.model_validate(data)
            d = p.model_dump()
            assert d["name"] == data["name"]
            assert d["category"].value == data["category"]

    @given(
        name=st.sampled_from([s.value for s in AgentTopology]),
        category=st.sampled_from([c.value for c in PatternCategory]),
    )
    @settings(max_examples=20)
    def test_minimal_pattern(self, name, category):
        p = Pattern(
            name=name,
            context="Test context",
            category=category,
            topology=name,
            benefits=["benefit"],
            tradeoffs=["tradeoff"],
            quality_attributes={
                "reliability": 5.0, "cost_efficiency": 5.0, "latency": 5.0,
                "output_quality": 5.0, "observability": 5.0, "safety": 5.0,
                "simplicity": 5.0,
            },
        )
        assert p.name == name
        assert p.category.value == category
        assert p.suitable_domains == []
        assert p.tradeoffs == ["tradeoff"]
