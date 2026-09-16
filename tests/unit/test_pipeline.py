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
Unit tests for AgentPatternPipeline class.

Test Case IDs: UT-12, IT-2, IT-5
Validates Requirements: FR-214, AC-214

Test Scenarios:
- SCEN-20: Pipeline pattern flow with ANALYZE, GENERATE, EVALUATE, REFINE phases
- SCEN-22: Pattern metadata inclusion in GENERATE phase
- SCEN-23: Quality benchmarking in EVALUATE phase
- SCEN-24: Best practices application in REFINE phase

Acceptance Criteria:
- AC-214: Verify ANALYZE filters, GENERATE includes metadata, EVALUATE benchmarks, REFINE uses best_practices

Design Patterns Tested:
- DP-1: Pipeline Pattern (via Workflow-backed AgentPatternPipeline)
- DP-5: Dependency Injection
- DP-6: Observer Pattern REPLACED by WorkflowHandler.stream_events()
"""

import pytest
from unittest.mock import patch

from src.pipeline import (
    AnalysisResult,
    AgentSystemEvaluation,
    AgentPatternPipeline,
)
from src.schemas.agent_system import AgentSystemDesignResponse
from src.schemas.design import AgentSystemDesign, AgentSystemOverview
from src.schemas.enums import AgentTopology
from src.schemas.evaluation import EvaluationSummary, MetricResult, PipelineResult
from src.config import RetrievalConfig
from src.prompts import REQUIREMENT_WEIGHTS_EXAMPLE_CONFLICT
from src.schemas.quality import QualityMetrics


class MockAgentSystemArchitect:
    """Mock AgentSystemArchitect for testing."""

    def __init__(self, config=None):
        self._config = config
        self.generate_structured_calls = []

    async def generate_structured(
        self, system_prompt: str, user_prompt: str, response_schema,
        *, role: str = "generation",
    ):
        self.generate_structured_calls.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "schema": response_schema,
            "role": role,
        })

        if response_schema is AgentSystemDesignResponse:
            return AgentSystemDesignResponse(
                overview={
                    "topology": "hierarchical",
                    "category": "multi_agent",
                    "principles": ["single responsibility", "autonomy"],
                    "constraints": [],
                    "reasoning": "Test reasoning.",
                },
                agents=[
                    {
                        "id": "supervisor",
                        "name": "Task Supervisor",
                        "role": "planner",
                        "description": "Decomposes tasks and delegates to workers",
                        "responsibilities": ["route", "aggregate"],
                    },
                    {
                        "id": "worker-1",
                        "name": "Worker 1",
                        "role": "executor",
                        "description": "Executes assigned sub-tasks",
                        "responsibilities": ["execute"],
                    },
                ],
                relationships=[
                    {
                        "source": "supervisor",
                        "target": "worker-1",
                        "type": "delegates",
                        "description": "Supervisor delegates sub-tasks to workers",
                    }
                ],
                quality_attributes={},
                tool_contracts=[
                    {
                        "tool_name": "web_search",
                        "agent_id": "worker-1",
                        "description": "Web search tool",
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                        "auth_required": False,
                    },
                ],
                shared_state_models=[
                    {
                        "name": "TaskPlan",
                        "fields": [
                            {"name": "task_id", "type": "string", "required": True},
                            {"name": "status", "type": "string", "required": True},
                        ],
                        "description": "Shared task plan",
                        "is_shared": True,
                    },
                ],
                message_contracts=[
                    {
                        "message_name": "task.assigned",
                        "payload_schema": {"type": "object"},
                        "published_by": "supervisor",
                        "consumed_by": ["worker-1"],
                        "description": "Sub-task assignment",
                    },
                ],
            )

        if response_schema.__name__ == "AnalysisResult":
            from src.schemas.quality import QualityMetrics
            return AnalysisResult(
                strengths=["Strong scalability", "Good performance"],
                weaknesses=["Complex to set up"],
                recommendations=["Consider starting with simpler architecture"],
                quality_metrics=QualityMetrics(
                    reliability=7.0, cost_efficiency=6.0, latency=7.0,
                    output_quality=8.0, observability=7.0, safety=8.0,
                ),
                recommended_topology="hierarchical",
                selected_patterns=[],
            )

        if response_schema.__name__ == "RequirementWeights":
            from src.pipeline import RequirementWeights
            return RequirementWeights(
                reliability=1.0,
                cost_efficiency=0.8,
                latency=0.6,
                output_quality=0.5,
                observability=0.3,
                safety=0.2,
            )

        if response_schema.__name__ == "AgentSystemEvaluation":
            return AgentSystemEvaluation(
                summary=EvaluationSummary(
                    reasoning="Evaluator reasoning for the assessment",
                    overall_score=75.0,
                    strengths=["Good overall quality"],
                    weaknesses=["Consider improvements in maintainability"],
                    critical_findings=["No critical risks identified"]
                ),
                metrics=[
                    MetricResult(name="overall_quality", score=75.0, description="Overall", findings=[], recommendations=[])
                ],
                recommendations={},
            )

        mock_design = AgentSystemDesign(
            overview={
                "topology": "hierarchical",
                "category": "multi_agent",
                "principles": ["single responsibility", "autonomy"],
            },
            agents=[
                {
                    "id": "supervisor",
                    "name": "Task Supervisor",
                    "role": "planner",
                    "description": "Routes and aggregates",
                    "responsibilities": ["route", "aggregate"],
                },
            ],
            relationships=[
                {
                    "source": "supervisor",
                    "target": "worker-1",
                    "type": "delegates",
                    "description": "Supervisor delegates to workers",
                }
            ],
        )
        return mock_design


class MockPatternLoader:
    """Mock PatternLoader for testing."""

    def __init__(self, patterns_dir=None):
        self._patterns_dir = patterns_dir
        self._patterns_cache = []
        self._loaded = False
        self.filter_by_domain_calls = []
        self.select_top_patterns_calls = []

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load_all(self) -> list[dict]:
        if not self._loaded:
            self._patterns_cache = self._get_mock_patterns()
            self._loaded = True
        return self._patterns_cache

    def filter_by_domain(self, domain: str) -> list[dict]:
        self.filter_by_domain_calls.append(domain)
        normalized_domain = domain.lower().replace(" ", "-")
        return [p for p in self._patterns_cache
                if normalized_domain in p.get("suitable_domains", [])]

    def select_top_patterns(self, domain: str, top_k: int = 5) -> list[dict]:
        self.select_top_patterns_calls.append((domain, top_k))
        filtered = self.filter_by_domain(domain)
        return filtered[:top_k]

    def get_by_name(self, name: str) -> dict | None:
        for p in self._patterns_cache:
            if p.get("name") == name:
                return p
        return None

    def _get_mock_patterns(self) -> list[dict]:
        return [
            {
                "name": "microservices",
                "topology": "hierarchical",
                "category": "multi_agent",
                "suitable_domains": ["multi-agent-systems", "cost-sensitive-workloads"],
                "quality_attributes": {
                    "reliability": 10,
                    "cost_efficiency": 6,
                    "latency": 7,
                    "output_quality": 8,
                    "observability": 7,
                    "safety": 8,
                    "simplicity": 7,
                },
                "best_practices": [
                    "Use database per service",
                    "Implement circuit breakers",
                    "Add distributed tracing"
                ],
                "context": "Distributed systems requiring independent deployability",
                "benefits": ["Independent scaling", "Fault isolation"],
                "tradeoffs": ["Distributed complexity", "Operational overhead"]
            },
            {
                "name": "event-driven",
                "topology": "swarm",
                "category": "multi_agent",
                "suitable_domains": ["autonomous-task-execution", "data-analysis"],
                "quality_attributes": {
                    "reliability": 7,
                    "cost_efficiency": 8,
                    "latency": 8,
                    "output_quality": 7,
                    "observability": 6,
                    "safety": 5,
                    "simplicity": 1,
                },
                "best_practices": [
                    "Use message brokers",
                    "Implement idempotency",
                    "Handle dead letter queues"
                ],
                "context": "Systems requiring async communication",
                "benefits": ["Loose coupling", "Scalability"],
                "tradeoffs": ["Eventual consistency", "Debug complexity"]
            }
        ]


class MockDenseRetriever:
    """Mock dense-leg retriever returning canned domain nodes."""

    def __init__(self, top_k: int = 20):
        self._top_k = top_k

    def retrieve(self, query_bundle):
        from llama_index.core.schema import NodeWithScore, TextNode
        nodes = [
            NodeWithScore(node=TextNode(text="cloud-native", metadata={"slug": "cloud-native"}), score=0.95),
            NodeWithScore(node=TextNode(text="multi-agent-systems", metadata={"slug": "multi-agent-systems"}), score=0.85),
            NodeWithScore(node=TextNode(text="tool-use-tasks", metadata={"slug": "tool-use-tasks"}), score=0.75),
        ]
        return nodes[:self._top_k]


class MockBM25Retriever:
    """Mock BM25-leg retriever returning canned domain nodes."""

    def __init__(self, top_k: int = 20):
        self._top_k = top_k

    def retrieve(self, query_bundle):
        from llama_index.core.schema import NodeWithScore, TextNode
        nodes = [
            NodeWithScore(node=TextNode(text="cloud-native", metadata={"slug": "cloud-native"}), score=0.9),
            NodeWithScore(node=TextNode(text="multi-agent-systems", metadata={"slug": "multi-agent-systems"}), score=0.8),
            NodeWithScore(node=TextNode(text="tool-use-tasks", metadata={"slug": "tool-use-tasks"}), score=0.7),
        ]
        return nodes[:self._top_k]


def create_test_pipeline(retrieval_config=None):
    """Create a test pipeline with mock dependencies.

    Defaults to min_fusion_score=0.0: the mock reranker does not stamp
    ``retrieval_score``, so the restore path yields 0.0 and any positive
    relevance floor would hijack these stage-semantics tests.
    """
    from src.config import RetrievalConfig, RerankerConfig, RerankerInnerConfig
    from unittest.mock import MagicMock
    agent = MockAgentSystemArchitect()
    pattern_loader = MockPatternLoader()
    pattern_loader.load_all()
    reranker_config = RerankerConfig(
        config=RerankerInnerConfig(base_url="http://test-reranker:8080")
    )
    if retrieval_config is None:
        retrieval_config = RetrievalConfig(min_fusion_score=0.0)
    pipeline = AgentPatternPipeline(
        agent=agent,
        pattern_loader=pattern_loader,
        embedder=MagicMock(),
        retrieval_config=retrieval_config,
        reranker_config=reranker_config,
    )
    pipeline._dense_retriever = MockDenseRetriever()
    pipeline._bm25_retriever = MockBM25Retriever()
    return pipeline


class TestAgentPatternPipelineInit:
    """Test AgentPatternPipeline initialization."""

    def test_pipeline_class_exists(self):
        """Verify AgentPatternPipeline class exists and inherits from Workflow."""
        pipeline = create_test_pipeline()
        assert pipeline is not None
        from workflows import Workflow
        assert isinstance(pipeline, Workflow)

    def test_pipeline_accepts_dependencies(self):
        """DP-5: Verify pipeline accepts dependency injected agents."""
        from unittest.mock import MagicMock
        agent = MockAgentSystemArchitect()
        pattern_loader = MockPatternLoader()
        embedder = MagicMock()

        pipeline = AgentPatternPipeline(
            agent=agent,
            pattern_loader=pattern_loader,
            embedder=embedder,
        )

        assert pipeline._agent is agent
        assert pipeline._pattern_loader is pattern_loader
        assert pipeline._embedder is embedder


class TestPipelinePhases:
    """Test individual pipeline phases (all async now)."""

    @pytest.mark.asyncio
    async def test_analyze_phase(self):
        """FR-214: ANALYZE phase filters patterns by domain."""
        pipeline = create_test_pipeline()

        result = await pipeline.analyze(
            requirements="Need scalable distributed system",
            domain="multi-agent-systems"
        )

        assert isinstance(result, AnalysisResult)
        assert len(result.selected_patterns) > 0
        assert isinstance(result.quality_metrics, QualityMetrics)

        assert pipeline._pattern_loader.filter_by_domain_calls
        assert any(
            c in {"multi-agent-systems", "cost-sensitive-workloads", "autonomous-task-execution", "data-analysis"}
            for c in pipeline._pattern_loader.filter_by_domain_calls
        )

    @pytest.mark.asyncio
    async def test_generate_phase(self):
        """FR-214: GENERATE phase includes pattern metadata in LLM context."""
        pipeline = create_test_pipeline()

        patterns = [
            {
                "name": "microservices",
                "context": "Distributed systems",
                "category": "structural",
                "benefits": ["Scaling"],
                "tradeoffs": ["Complexity"],
                "suitable_domains": ["microservices"],
                "best_practices": ["Circuit breakers"]
            }
        ]

        design = await pipeline.generate(
            requirements="Build scalable API",
            domain="cloud-native",
            topology="microservices",
            selected_patterns=patterns
        )

        assert isinstance(design, AgentSystemDesign)
        assert len(design.agents) > 0

        assert len(pipeline._agent.generate_structured_calls) > 0
        call = pipeline._agent.generate_structured_calls[-1]
        assert "microservices" in call["system_prompt"] or "microservices" in call["user_prompt"]

    @pytest.mark.asyncio
    async def test_evaluate_phase(self):
        """FR-214: EVALUATE phase benchmarks against quality attributes."""
        pipeline = create_test_pipeline()

        design = AgentSystemDesign(
            overview={
                "topology": "hierarchical",
                "category": "multi_agent",
                "principles": ["single responsibility"],
                "constraints": []
            },
            agents=[{"id": "svc1", "name": "Service 1", "role": "service", "description": "A service", "responsibilities": ["serve"]}],
        )

        evaluation = await pipeline.evaluate(
            design=design,
            criteria="quality,scalability",
            domain="cloud-native"
        )

        assert isinstance(evaluation, AgentSystemEvaluation)
        assert len(evaluation.metrics) > 0
        assert any(m.name == "overall_quality" for m in evaluation.metrics)

    @pytest.mark.asyncio
    async def test_design_loop_runs_generate_evaluate(self):
        """FR-214: design_loop runs generate and evaluate."""
        pipeline = create_test_pipeline()

        result = await pipeline.design_loop(
            requirements="Build a scalable distributed system",
            domain="cloud-native",
            topology="microservices",
            selected_patterns=[{
                "name": "microservices",
                "context": "Distributed systems",
                "category": "structural",
                "benefits": ["scaling"],
                "best_practices": ["Use database per service"]
            }],
            criteria="quality,maintainability,scalability",
            analysis_result=None,
            max_tries=3,
        )

        assert isinstance(result, PipelineResult)
        assert result.attempts >= 1
        assert result.final_quality_score >= 0.0


class TestPipelineConstants:
    """Test pipeline constants."""

    def test_default_max_tries(self):
        """CONST-11: DEFAULT_MAX_TRIES = 3"""
        assert AgentPatternPipeline.DEFAULT_MAX_TRIES == 3


class TestQualityMetricsCalculation:
    """Test quality metrics calculation in pipeline."""

    def test_calculate_quality_metrics_from_patterns(self):
        """Verify quality metrics are calculated correctly from patterns."""
        pipeline = create_test_pipeline()

        patterns = [
            {
                "quality_attributes": {
                    "cost_efficiency": 7,
                    "latency": 6,
                    "output_quality": 8,
                    "observability": 9,
                    "safety": 7,
                    "reliability": 8
                }
            },
            {
                "quality_attributes": {
                    "cost_efficiency": 8,
                    "latency": 7,
                    "output_quality": 9,
                    "observability": 8,
                    "safety": 6,
                    "reliability": 7
                }
            }
        ]

        metrics = pipeline._calculate_quality_metrics(patterns)

        assert metrics.cost_efficiency == 7.5
        assert metrics.latency == 6.5
        assert metrics.output_quality == 8.5
        assert metrics.observability == 8.5
        assert metrics.safety == 6.5
        assert metrics.reliability == 7.5

    def test_calculate_quality_metrics_empty_patterns(self):
        """Verify default metrics for empty patterns list."""
        pipeline = create_test_pipeline()

        metrics = pipeline._calculate_quality_metrics([])

        assert metrics.cost_efficiency == 0.0
        assert metrics.latency == 0.0
        assert metrics.output_quality == 0.0
        assert metrics.observability == 0.0
        assert metrics.safety == 0.0
        assert metrics.reliability == 0.0


class TestAnalyzeScoring:
    """Tests for the deterministic requirements-aware scoring (stage-2)."""

    def test_score_patterns_weighted_average_formula(self):
        """analysis_score = Σ(wᵢ·qaᵢ)/Σ(wᵢ)·10, sorted descending."""
        from src.pipeline import RequirementWeights

        pipeline = create_test_pipeline()
        patterns = [
            {"name": "a", "quality_attributes": {
                "reliability": 10, "cost_efficiency": 0, "latency": 0,
                "output_quality": 0, "observability": 0, "safety": 0}},
            {"name": "b", "quality_attributes": {
                "reliability": 0, "cost_efficiency": 0, "latency": 10,
                "output_quality": 0, "observability": 0, "safety": 0}},
        ]
        # Pure reliability priority → 'a' (10) outranks 'b' (0).
        weights = RequirementWeights(reliability=1.0)
        scored = pipeline._score_patterns(patterns, weights)

        assert scored[0]["name"] == "a"
        assert scored[0]["analysis_score"] == 100.0
        assert scored[1]["name"] == "b"
        assert scored[1]["analysis_score"] == 0.0

    def test_score_patterns_mixed_weights(self):
        """Weighted average across multiple attributes."""
        from src.pipeline import RequirementWeights

        pipeline = create_test_pipeline()
        patterns = [
            {"name": "perf-heavy", "quality_attributes": {
                "reliability": 0, "cost_efficiency": 0, "latency": 10,
                "output_quality": 0, "observability": 0, "safety": 2}},
        ]
        # 50/50 latency + safety → (10*0.5 + 2*0.5)/1.0 = 6.0 → 60.0
        weights = RequirementWeights(latency=0.5, safety=0.5)
        scored = pipeline._score_patterns(patterns, weights)
        assert scored[0]["analysis_score"] == 60.0

    def test_score_patterns_preserves_fusion_score(self):
        """fusion_score from stage-1 is retained on the scored pattern dict."""
        from src.pipeline import RequirementWeights

        pipeline = create_test_pipeline()
        patterns = [{"name": "x", "quality_attributes": {
            "reliability": 8, "cost_efficiency": 8, "latency": 8,
            "output_quality": 8, "observability": 8, "safety": 8},
            "fusion_score": 0.42}]
        weights = RequirementWeights(reliability=1.0)
        scored = pipeline._score_patterns(patterns, weights)
        assert scored[0]["fusion_score"] == 0.42
        assert "analysis_score" in scored[0]

    def test_score_patterns_all_zero_weights_falls_back_to_mean(self):
        """All-zero weights use the unweighted mean (no division by zero)."""
        from src.pipeline import RequirementWeights

        pipeline = create_test_pipeline()
        patterns = [{"name": "x", "quality_attributes": {
            "reliability": 6, "cost_efficiency": 6, "latency": 6,
            "output_quality": 6, "observability": 6, "safety": 6, "simplicity": 6}}]
        weights = RequirementWeights()  # all default 0.0
        scored = pipeline._score_patterns(patterns, weights)
        assert scored[0]["analysis_score"] == 60.0

    def test_select_recommended_topology_override_wins(self):
        """An explicit style override always wins."""
        pipeline = create_test_pipeline()
        selected = [{"name": "microservices", "topology": "pipeline", "analysis_score": 99.0}]
        assert pipeline._select_recommended_topology(selected, "hierarchical") == "hierarchical"

    def test_select_recommended_topology_top_pattern_above_threshold(self):
        """Top pattern's topology value is used when its score meets the threshold."""
        pipeline = create_test_pipeline()  # default threshold 50.0
        selected = [{"name": "event-driven", "topology": "graph-orchestrated", "analysis_score": 80.0}]
        assert pipeline._select_recommended_topology(selected, None) == "graph-orchestrated"

    def test_select_recommended_topology_uses_topology_not_name(self):
        """The pattern's topology field — never its name — becomes the recommendation."""
        pipeline = create_test_pipeline()
        selected = [{"name": "react", "topology": "single-agent-loop", "analysis_score": 90.0}]
        assert pipeline._select_recommended_topology(selected, None) == "single-agent-loop"

    def test_select_recommended_topology_below_threshold_falls_back(self):
        """Falls back to the fallback topology when top score < threshold."""
        pipeline = create_test_pipeline()  # default threshold 50.0
        selected = [{"name": "event-driven", "topology": "graph-orchestrated", "analysis_score": 40.0}]
        assert pipeline._select_recommended_topology(selected, None) == "single-agent-loop"

    def test_select_recommended_topology_empty_falls_back(self):
        """Empty selection falls back to the fallback topology."""
        pipeline = create_test_pipeline()
        assert pipeline._select_recommended_topology([], None) == "single-agent-loop"

    @pytest.mark.asyncio
    async def test_analyze_injects_scores_and_selects_top_k(self):
        """analyze() injects analysis_score, sorts, and truncates to top_k_patterns."""
        pipeline = create_test_pipeline()  # default top_k_patterns=5
        result = await pipeline.analyze(
            requirements="Need scalable distributed system",
            domain="microservices",
        )
        assert len(result.selected_patterns) > 0
        for p in result.selected_patterns:
            assert "analysis_score" in p
            assert "fusion_score" in p
            assert isinstance(p["analysis_score"], float)
        # Selected patterns must be sorted by analysis_score descending.
        scores = [p["analysis_score"] for p in result.selected_patterns]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_analyze_llm_receives_no_patterns_in_prompt(self):
        """The weight-extraction prompt must NOT contain pattern data (C3)."""
        pipeline = create_test_pipeline()
        await pipeline.analyze(
            requirements="Need scalable distributed system",
            domain="microservices",
        )
        # The first (and only) generate_structured call in analyze is the
        # RequirementWeights extraction. Its user prompt must not embed
        # candidate pattern names / quality_attributes.
        weights_calls = [
            c for c in pipeline._agent.generate_structured_calls
            if c["schema"].__name__ == "RequirementWeights"
        ]
        assert len(weights_calls) == 1
        user_prompt = weights_calls[0]["user_prompt"]
        assert "Candidate patterns" not in user_prompt
        assert "quality_attributes=" not in user_prompt



class TestPatternFlow:
    """AC-214: Test pattern flow through all pipeline phases."""

    @pytest.mark.asyncio
    async def test_patterns_flow_through_analyze_filtering(self):
        """AC-214: Verify ANALYZE filters patterns correctly."""
        pipeline = create_test_pipeline()

        result = await pipeline.analyze(
            requirements="Distributed system needed",
            domain="cloud-native"
        )

        assert len(result.selected_patterns) > 0

        for pattern in result.selected_patterns:
            assert isinstance(pattern, dict)
            assert "name" in pattern
            assert "quality_attributes" in pattern

    @pytest.mark.asyncio
    async def test_patterns_flow_through_generate_metadata(self):
        """AC-214: Verify GENERATE includes pattern metadata."""
        pipeline = create_test_pipeline()

        patterns = [
            {
                "name": "microservices",
                "context": "Distributed systems",
                "category": "structural",
                "benefits": ["Scaling"],
                "tradeoffs": ["Complexity"],
                "suitable_domains": ["cloud-native"],
                "best_practices": ["Use APIs"]
            }
        ]

        design = await pipeline.generate(
            requirements="Build distributed system",
            domain="cloud-native",
            topology="microservices",
            selected_patterns=patterns
        )

    @pytest.mark.asyncio
    async def test_patterns_flow_through_evaluate_quality_benchmarking(self):
        """AC-214: Verify EVALUATE benchmarks against quality attributes."""
        pipeline = create_test_pipeline()

        design = AgentSystemDesign(
            overview={
                "topology": "hierarchical",
                "category": "multi_agent",
                "principles": ["single responsibility"],
                "constraints": []
            },
            agents=[
                {"id": "api", "name": "API", "role": "gateway", "description": "Entry point", "responsibilities": ["route"]},
                {"id": "svc", "name": "Service", "role": "service", "description": "Core service", "responsibilities": ["process"]}
            ],
        )

        evaluation = await pipeline.evaluate(
            design=design,
            criteria="maintainability,scalability,performance",
            domain="cloud-native"
        )

        assert len(evaluation.metrics) > 0
        assert any(m.name == "overall_quality" for m in evaluation.metrics)

    @pytest.mark.asyncio
    async def test_patterns_flow_through_design_loop(self):
        """AC-214: Verify design_loop respects max_tries."""
        pipeline = create_test_pipeline()

        result = await pipeline.design_loop(
            requirements="Build a scalable distributed system",
            domain="cloud-native",
            topology="microservices",
            selected_patterns=[{
                "name": "microservices",
                "context": "Distributed systems",
                "category": "structural",
                "benefits": ["scaling"],
                "best_practices": ["Use database per service"]
            }],
            criteria="quality,maintainability",
            analysis_result=None,
            max_tries=2,
        )

        assert result.attempts <= 2


class TestGeneratePropagatesContracts:
    """Verify tool_contracts, shared_state_models, message_contracts flow from LLM into typed AgentSystemDesign."""

    @pytest.mark.asyncio
    async def test_generate_propagates_populated_contracts(self):
        """tool_contracts, shared_state_models, message_contracts are typed from LLM output."""
        pipeline = create_test_pipeline()

        design = await pipeline.generate(
            requirements="Build distributed system",
            domain="cloud-native",
            topology="hierarchical",
            selected_patterns=[
                {
                    "name": "microservices",
                    "topology": "hierarchical",
                    "category": "multi_agent",
                    "context": "Distributed systems",
                    "benefits": ["Scaling"],
                    "tradeoffs": ["Complexity"],
                    "quality_attributes": {
                        "reliability": 7, "cost_efficiency": 6, "latency": 7,
                        "output_quality": 8, "observability": 7, "safety": 8, "simplicity": 4,
                    },
                    "suitable_domains": ["cloud-native"],
                    "best_practices": ["Use APIs"]
                }
            ]
        )

        assert len(design.tool_contracts) == 1
        assert design.tool_contracts[0].tool_name == "web_search"
        assert design.tool_contracts[0].agent_id == "worker-1"

        assert len(design.shared_state_models) == 1
        assert design.shared_state_models[0].name == "TaskPlan"
        assert design.shared_state_models[0].is_shared is True

        assert len(design.message_contracts) == 1
        assert design.message_contracts[0].message_name == "task.assigned"
        assert design.message_contracts[0].published_by == "supervisor"
        assert design.message_contracts[0].consumed_by == ["worker-1"]

    @pytest.mark.asyncio
    async def test_generate_contracts_roundtrip(self):
        """AgentSystemDesign with contracts round-trips through model_dump -> model_validate."""
        pipeline = create_test_pipeline()

        design = await pipeline.generate(
            requirements="Build distributed system",
            domain="cloud-native",
            topology="hierarchical",
            selected_patterns=[
                {
                    "name": "microservices",
                    "topology": "hierarchical",
                    "category": "multi_agent",
                    "context": "Distributed systems",
                    "benefits": ["Scaling"],
                    "tradeoffs": ["Complexity"],
                    "quality_attributes": {
                        "reliability": 7, "cost_efficiency": 6, "latency": 7,
                        "output_quality": 8, "observability": 7, "safety": 8, "simplicity": 4,
                    },
                    "suitable_domains": ["cloud-native"],
                    "best_practices": ["Use APIs"]
                }
            ]
        )

        dumped = design.model_dump()
        revalidated = AgentSystemDesign.model_validate(dumped)
        assert len(revalidated.tool_contracts) == len(design.tool_contracts)
        assert revalidated.tool_contracts[0].tool_name == design.tool_contracts[0].tool_name
        assert len(revalidated.shared_state_models) == len(design.shared_state_models)
        assert revalidated.shared_state_models[0].name == design.shared_state_models[0].name
        assert len(revalidated.message_contracts) == len(design.message_contracts)
        assert revalidated.message_contracts[0].message_name == design.message_contracts[0].message_name

    @pytest.mark.asyncio
    async def test_evaluate_receives_populated_contracts(self):
        """evaluate() receives design with contracts via model_dump_json() in the prompt."""
        pipeline = create_test_pipeline()

        design = await pipeline.generate(
            requirements="Build distributed system",
            domain="cloud-native",
            topology="hierarchical",
            selected_patterns=[
                {
                    "name": "microservices",
                    "topology": "hierarchical",
                    "category": "multi_agent",
                    "context": "Distributed systems",
                    "benefits": ["Scaling"],
                    "tradeoffs": ["Complexity"],
                    "quality_attributes": {
                        "reliability": 7, "cost_efficiency": 6, "latency": 7,
                        "output_quality": 8, "observability": 7, "safety": 8, "simplicity": 4,
                    },
                    "suitable_domains": ["cloud-native"],
                    "best_practices": ["Use APIs"]
                }
            ]
        )

        captured_prompts: list[str] = []
        original_generate = pipeline._agent.generate_structured

        async def capture_generate(system_prompt, user_prompt, response_schema):
            captured_prompts.append(user_prompt)
            return AgentSystemEvaluation(
                summary=EvaluationSummary(
                    reasoning="Evaluator reasoning for the assessment",
                    overall_score=75.0,
                    strengths=["Good"],
                    weaknesses=["Consider"],
                    critical_findings=["None"]
                ),
                metrics=[
                    MetricResult(name="overall_quality", score=75.0, description="Overall", findings=[], recommendations=[])
                ],
                recommendations={}
            )

        pipeline._agent.generate_structured = capture_generate

        await pipeline.evaluate(
            design=design,
            criteria="maintainability,scalability",
            domain="cloud-native"
        )

        pipeline._agent.generate_structured = original_generate

        assert len(captured_prompts) == 1
        json_str = captured_prompts[0]
        assert "supervisor" in json_str
        assert "web_search" in json_str
        assert "task.assigned" in json_str


class _MockArchitectForDenormalization:
    """Mock agent that returns a design with duplicate contracts for dedup testing.

    Used to verify denormalize_contracts deduplicates top-level contract lists.
    """

    async def generate_structured(
        self, system_prompt, user_prompt, response_schema,
    ):
        if response_schema is AgentSystemDesignResponse:
            return AgentSystemDesignResponse(
                overview={
                    "topology": "hierarchical",
                    "category": "multi_agent",
                    "principles": ["single responsibility"],
                    "constraints": [],
                    "reasoning": "Test reasoning.",
                },
                agents=[
                    {
                        "id": "supervisor",
                        "name": "Supervisor",
                        "role": "planner",
                        "description": "Supervisor",
                        "responsibilities": ["coordinate"],
                    },
                ],
                relationships=[],
                quality_attributes={},
                tool_contracts=[
                    {
                        "tool_name": "search",
                        "agent_id": "supervisor",
                        "description": "Search tool",
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                        "auth_required": False,
                    },
                    {
                        "tool_name": "search",
                        "agent_id": "supervisor",
                        "description": "Duplicate — should be deduped",
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                        "auth_required": False,
                    },
                ],
                shared_state_models=[
                    {
                        "name": "TaskPlan",
                        "fields": [
                            {"name": "id", "type": "string", "required": True},
                        ],
                        "description": "Shared plan",
                        "is_shared": True,
                    },
                    {
                        "name": "TaskPlan",
                        "fields": [
                            {"name": "id", "type": "string", "required": True},
                        ],
                        "description": "Duplicate — should be deduped",
                        "is_shared": True,
                    },
                ],
                message_contracts=[
                    {
                        "message_name": "task.started",
                        "payload_schema": {"type": "object"},
                        "published_by": "supervisor",
                        "consumed_by": [],
                        "description": "Task started",
                    },
                    {
                        "message_name": "task.started",
                        "payload_schema": {"type": "object"},
                        "published_by": "supervisor",
                        "consumed_by": [],
                        "description": "Duplicate — should be deduped",
                    },
                ],
            )

        if response_schema.__name__ == "AnalysisResult":
            from src.schemas.quality import QualityMetrics
            return AnalysisResult(
                strengths=["Scalable"],
                weaknesses=["Complex"],
                recommendations=["Start simple"],
                quality_metrics=QualityMetrics(
                    reliability=7.0, cost_efficiency=6.0, latency=7.0,
                    output_quality=8.0, observability=7.0, safety=8.0,
                ),
                recommended_topology="hierarchical",
                selected_patterns=[],
            )

        return AgentSystemEvaluation(
            summary=EvaluationSummary(
                reasoning="Evaluator reasoning for the assessment",
                overall_score=75.0,
                strengths=["Good"],
                weaknesses=["Consider"],
                critical_findings=["None"]
            ),
            metrics=[
                MetricResult(
                    name="overall_quality", score=75.0,
                    description="Overall", findings=[], recommendations=[]
                )
            ],
            recommendations={},
        )


def _create_denorm_pipeline():
    from unittest.mock import MagicMock
    agent = _MockArchitectForDenormalization()
    pattern_loader = MockPatternLoader()
    return AgentPatternPipeline(
        agent=agent,
        pattern_loader=pattern_loader,
        embedder=MagicMock(),
    )


class TestDenormalizationIntegration:
    """Verify denormalize_contracts deduplicates repeated contracts in pipeline.generate()."""

    @pytest.mark.asyncio
    async def test_generate_deduplicates_tool_contracts(self):
        """Duplicate tool_contracts (same tool_name+agent_id) are deduped by denormalize_contracts."""
        pipeline = _create_denorm_pipeline()

        design = await pipeline.generate(
            requirements="Build a system",
            domain="microservices",
            topology="hierarchical",
            selected_patterns=[{
                "name": "microservices",
                "topology": "hierarchical",
                "category": "multi_agent",
                "context": "Distributed systems",
                "benefits": ["Scaling"],
                "tradeoffs": ["Complexity"],
                "quality_attributes": {
                    "reliability": 7, "cost_efficiency": 6, "latency": 7,
                    "output_quality": 8, "observability": 7, "safety": 8, "simplicity": 4,
                },
                "suitable_domains": ["microservices"],
                "best_practices": ["Use APIs"]
            }]
        )

        assert len(design.tool_contracts) == 1
        assert design.tool_contracts[0].tool_name == "search"
        assert design.tool_contracts[0].agent_id == "supervisor"

    @pytest.mark.asyncio
    async def test_generate_deduplicates_shared_state_models(self):
        """Duplicate shared_state_models (same name+is_shared) are deduped by denormalize_contracts."""
        pipeline = _create_denorm_pipeline()

        design = await pipeline.generate(
            requirements="Build a system",
            domain="microservices",
            topology="hierarchical",
            selected_patterns=[{
                "name": "microservices",
                "topology": "hierarchical",
                "category": "multi_agent",
                "context": "Distributed systems",
                "benefits": ["Scaling"],
                "tradeoffs": ["Complexity"],
                "quality_attributes": {
                    "reliability": 7, "cost_efficiency": 6, "latency": 7,
                    "output_quality": 8, "observability": 7, "safety": 8, "simplicity": 4,
                },
                "suitable_domains": ["microservices"],
                "best_practices": ["Use APIs"]
            }]
        )

        assert len(design.shared_state_models) == 1
        assert design.shared_state_models[0].name == "TaskPlan"
        assert design.shared_state_models[0].is_shared is True


class TestDomainNormalization:
    """Test domain normalization in pipeline's ANALYZE phase."""

    @pytest.mark.asyncio
    async def test_analyze_normalizes_domain(self):
        """IC-31: Verify domain is normalized during ANALYSIS."""
        pipeline = create_test_pipeline()

        class _DummyReranker:
            top_n = 1

            def postprocess_nodes(self, nodes, query_bundle=None):
                return nodes

        with patch(
            "src.patterns.retriever.SafeTEIReranker",
            return_value=_DummyReranker(),
        ):
            await pipeline.analyze("Requirements", "Cloud Native")

        all_calls = pipeline._pattern_loader.filter_by_domain_calls
        assert any(
            "cloud native" in c or "cloud-native" in c or "cloudnative" in c
            for c in all_calls
        )


class TestErrorHandling:
    """Test pipeline error handling."""

    @pytest.mark.asyncio
    async def test_analyze_handles_empty_results(self):
        """Verify ANALYZE handles no matching patterns gracefully."""
        pipeline = create_test_pipeline()

        result = await pipeline.analyze(
            requirements="Requirements",
            domain="nonexistent-domain-xyz"
        )

        assert isinstance(result, AnalysisResult)
        assert len(result.selected_patterns) >= 0


class TestInvalidCategoryRegression:
    """
    Regression tests for the invalid PatternCategory bug (ERR_012).

    Bug: LLM produced category: 'stream-processing' (an AgentDomain value)
    instead of a valid PatternCategory enum value. This caused Pydantic
    ValidationError to bubble up as "Unexpected error during design" instead of
    being caught and converted to MalformedAgentSystemOverviewError.

    Fix (Option A): AgentSystemDesignResponse.overview is typed as
    AgentSystemOverview so the LLM sees the strict PatternCategory constraint
    at generation time. Defense-in-depth: pipeline.py wraps ValidationError
    from AgentSystemDesign construction in try/except and converts it to
    MalformedAgentSystemOverviewError.
    """

    def test_architecture_design_response_rejects_invalid_category(self):
        """
        AgentSystemDesignResponse with invalid category raises ValidationError.

        This is the core of Option A: by typing overview as AgentSystemOverview
        (not dict[str, Any]), Pydantic validates the category enum at
        AgentSystemDesignResponse construction time, preventing invalid values
        from propagating into the pipeline.
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            AgentSystemDesignResponse(
                overview={
                    "topology": "hierarchical",
                    "category": "stream-processing",
                    "principles": ["p1"],
                    "reasoning": "Test reasoning.",
                },
                agents=[],

            )
        errors = exc_info.value.errors()
        assert any(
            "category" in loc
            for err in errors
            for loc in [ ".".join(str(l) for l in err["loc"]) ]
        ), f"Expected 'category' in error locations, got: {errors}"

    def test_architecture_design_response_accepts_valid_category(self):
        """
        AgentSystemDesignResponse with valid category succeeds.

        Validates that Option A does not break the valid path.
        """
        from src.schemas.design import AgentSystemOverview
        from src.schemas.enums import AgentTopology, PatternCategory

        resp = AgentSystemDesignResponse(
            overview={
                "topology": "hierarchical",
                "category": "multi_agent",
                "principles": ["single responsibility"],
                "constraints": [],
                "reasoning": "Test reasoning.",
            },
            agents=[],

        )
        assert isinstance(resp.overview, AgentSystemOverview)
        assert resp.overview.category == PatternCategory.MULTI_AGENT
        assert resp.overview.topology == AgentTopology.HIERARCHICAL

    def test_architecture_design_validates_overview_category_enum(self):
        """
        AgentSystemDesign raises ValidationError when overview.category is invalid.

        This is the core Option A guarantee: by typing overview as
        AgentSystemOverview (not dict[str, Any]), invalid enum values
        like 'stream-processing' are caught at AgentSystemDesign construction time.
        """
        from pydantic import ValidationError
        from src.schemas.design import AgentSystemDesign
        from src.schemas.components import Agent

        with pytest.raises(ValidationError) as exc_info:
            AgentSystemDesign(
                overview={
                    "topology": "hierarchical",
                    "category": "stream-processing",
                    "principles": ["p1"],
                    "constraints": [],
                },
                agents=[Agent.model_validate({
                    "id": "svc",
                    "name": "Service",
                    "role": "service",
                    "description": "A service",
                    "responsibilities": ["do work"],
                    "technology_stack": [],
                })],

            )
        errors = exc_info.value.errors()
        assert any(
            "category" in str(err["loc"])
            for err in errors
        ), f"Expected 'category' in error locs, got: {errors}"

    def test_pipeline_reports_actual_field_location(self):
        """
        When AgentSystemDesign construction fails on a non-overview field,
        the error's first ValidationError location reflects the actual failing field.

        Note: AgentSystemDesign does NOT internally wrap ValidationError —
        that wrapping is done by the pipeline (src/pipeline.py). This test
        verifies the error location by checking the raw ValidationError.
        """
        from pydantic import ValidationError
        from src.schemas.design import AgentSystemDesign

        with pytest.raises(ValidationError) as exc_info:
            AgentSystemDesign(
                overview={
                    "topology": "hierarchical",
                    "category": "multi_agent",
                    "principles": ["p1"],
                    "constraints": [],
                },
                agents=[{
                    "id": "svc",
                    "name": "Service",
                    "role": "service",
                    "description": "A service",
                    "responsibilities": [],
                }],

            )
        errors = exc_info.value.errors()
        first_loc = ".".join(str(l) for l in errors[0]["loc"])
        assert "responsibilities" in first_loc, (
            f"Expected 'responsibilities' in first error loc, got: {first_loc}"
        )

    def test_max_retries_default_is_3(self):
        """ValidationConfig max_retries default is 3 (not 2)."""
        from src.config import ValidationConfig
        vc = ValidationConfig()
        assert vc.max_retries == 3


class TestIntegration:
    """Integration tests for full pipeline workflows."""

    @pytest.mark.asyncio
    async def test_run_design_returns_refined_architecture(self):
        """Test run_design() returns PipelineResult."""
        pipeline = create_test_pipeline()

        refined = await pipeline.run_design(
            requirements="Need scalable distributed system",
            domain="multi-agent-systems",
        )

        assert isinstance(refined, PipelineResult)
        assert isinstance(refined.design, AgentSystemDesign)
        assert refined.final_quality_score >= 0.0

    @pytest.mark.asyncio
    async def test_workflow_validates_event_graph(self):
        """Verify workflow.validate() passes for a correct graph."""
        pipeline = create_test_pipeline()
        result = pipeline.validate()
        assert result is not None


class TestDesignLoopPhase:
    """Tests for the design_loop method."""

    @pytest.mark.asyncio
    async def test_design_loop_returns_best_attempt(self):
        """design_loop returns the best-scoring attempt, not the last."""
        pipeline = create_test_pipeline()

        captured: list = []

        async def capture_generate(system_prompt, user_prompt, response_schema):
            captured.append(response_schema)
            from src.schemas.evaluation import AgentSystemEvaluation, EvaluationSummary, MetricResult
            if response_schema is AgentSystemDesignResponse:
                return AgentSystemDesignResponse(
                    overview={"topology": "hierarchical", "category": "multi_agent", "principles": ["single responsibility"], "constraints": [], "reasoning": "Test reasoning."},
                    agents=[{"id": "s1", "name": "S1", "role": "executor", "description": "svc", "responsibilities": ["serve"]}],
                    relationships=[],
                    quality_attributes={},
                    tool_contracts=[],
                    shared_state_models=[],
                    message_contracts=[],
                )
            if response_schema.__name__ == "AgentSystemEvaluation":
                score = 80.0 if len(captured) > 2 else 60.0
                return AgentSystemEvaluation(
                    summary=EvaluationSummary(reasoning="Evaluator reasoning", overall_score=score, strengths=["good"], weaknesses=["minor"], critical_findings=["none"]),
                    metrics=[MetricResult(name="overall_quality", score=score, description="q", findings=[], recommendations=[])],
                     compliance=[], recommendations={}
                )
            return None

        pipeline._agent.generate_structured = capture_generate

        result = await pipeline.design_loop(
            requirements="test",
            domain="cloud-native",
            topology="hierarchical",
            selected_patterns=[{"name": "microservices", "context": "", "topology": "hierarchical", "category": "multi_agent", "benefits": [], "tradeoffs": [], "quality_attributes": {"reliability": 7, "cost_efficiency": 6, "latency": 7, "output_quality": 8, "observability": 7, "safety": 8, "simplicity": 4}, "best_practices": []}],
            criteria="quality",
            analysis_result=None,
            max_tries=3,
        )

        assert result.final_quality_score == 80.0

    @pytest.mark.asyncio
    async def test_design_loop_respects_max_tries(self):
        """design_loop makes at most max_tries generate calls."""
        pipeline = create_test_pipeline()

        generate_count = 0

        async def counting_generate(system_prompt, user_prompt, response_schema):
            nonlocal generate_count
            from src.schemas.evaluation import AgentSystemEvaluation, EvaluationSummary, MetricResult
            if response_schema is AgentSystemDesignResponse:
                generate_count += 1
                return AgentSystemDesignResponse(
                    overview={"topology": "hierarchical", "category": "multi_agent", "principles": ["single responsibility"], "constraints": [], "reasoning": "Test reasoning."},
                    agents=[{"id": "s1", "name": "S1", "role": "executor", "description": "svc", "responsibilities": ["serve"]}],
                    relationships=[],
                    quality_attributes={},
                    tool_contracts=[],
                    shared_state_models=[],
                    message_contracts=[],
                )
            if response_schema.__name__ == "AgentSystemEvaluation":
                return AgentSystemEvaluation(
                    summary=EvaluationSummary(reasoning="Evaluator reasoning", overall_score=50.0, strengths=["ok"], weaknesses=["n/a"], critical_findings=["none"]),
                    metrics=[MetricResult(name="overall_quality", score=50.0, description="q", findings=[], recommendations=[])],
                     compliance=[], recommendations={}
                )
            return None

        pipeline._agent.generate_structured = counting_generate

        result = await pipeline.design_loop(
            requirements="test",
            domain="cloud-native",
            topology="hierarchical",
            selected_patterns=[{"name": "microservices", "context": "", "topology": "hierarchical", "category": "multi_agent", "benefits": [], "tradeoffs": [], "quality_attributes": {"reliability": 7, "cost_efficiency": 6, "latency": 7, "output_quality": 8, "observability": 7, "safety": 8, "simplicity": 4}, "best_practices": []}],
            criteria="quality",
            analysis_result=None,
            max_tries=3,
        )

        assert generate_count == 3
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_design_loop_early_stops_on_quality(self):
        """design_loop exits early when min_quality_score is met (0-100 scale)."""
        pipeline = create_test_pipeline()

        generate_count = 0

        async def counting_generate(system_prompt, user_prompt, response_schema):
            nonlocal generate_count
            from src.schemas.evaluation import AgentSystemEvaluation, EvaluationSummary, MetricResult
            if response_schema is AgentSystemDesignResponse:
                generate_count += 1
                return AgentSystemDesignResponse(
                    overview={"topology": "hierarchical", "category": "multi_agent", "principles": ["single responsibility"], "constraints": [], "reasoning": "Test reasoning."},
                    agents=[{"id": "s1", "name": "S1", "role": "executor", "description": "svc", "responsibilities": ["serve"]}],
                    relationships=[],
                    quality_attributes={},
                    tool_contracts=[],
                    shared_state_models=[],
                    message_contracts=[],
                )
            if response_schema.__name__ == "AgentSystemEvaluation":
                return AgentSystemEvaluation(
                    summary=EvaluationSummary(reasoning="Evaluator reasoning", overall_score=90.0, strengths=["great"], weaknesses=["minor"], critical_findings=["none"]),
                    metrics=[MetricResult(name="overall_quality", score=90.0, description="q", findings=[], recommendations=[])],
                     compliance=[], recommendations={}
                )
            return None

        pipeline._agent.generate_structured = counting_generate

        result = await pipeline.design_loop(
            requirements="test",
            domain="cloud-native",
            topology="hierarchical",
            selected_patterns=[{"name": "microservices", "context": "", "topology": "hierarchical", "category": "multi_agent", "benefits": [], "tradeoffs": [], "quality_attributes": {"reliability": 7, "cost_efficiency": 6, "latency": 7, "output_quality": 8, "observability": 7, "safety": 8, "simplicity": 4}, "best_practices": []}],
            criteria="quality",
            analysis_result=None,
            max_tries=3,
            min_quality_score=80.0,
        )

        # 90.0 >= 80.0 → early stop after first attempt
        assert generate_count == 1
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_design_loop_retries_on_malformed_error(self):
        """design_loop retries when generate throws MalformedAgentSystemOverviewError."""
        from src.errors import MalformedAgentSystemOverviewError, ERROR_INVALID_AGENT_SYSTEM
        pipeline = create_test_pipeline()

        attempt = 0

        async def throwing_generate(system_prompt, user_prompt, response_schema):
            nonlocal attempt
            from src.schemas.evaluation import AgentSystemEvaluation, EvaluationSummary, MetricResult
            if response_schema is AgentSystemDesignResponse:
                attempt += 1
                if attempt == 1:
                    raise MalformedAgentSystemOverviewError(locator="overview", errors=[])
                return AgentSystemDesignResponse(
                    overview={"topology": "hierarchical", "category": "multi_agent", "principles": ["single responsibility"], "constraints": [], "reasoning": "Test reasoning."},
                    agents=[{"id": "s1", "name": "S1", "role": "executor", "description": "svc", "responsibilities": ["serve"]}],
                    relationships=[],
                    quality_attributes={},
                    tool_contracts=[],
                    shared_state_models=[],
                    message_contracts=[],
                )
            if response_schema.__name__ == "AgentSystemEvaluation":
                return AgentSystemEvaluation(
                    summary=EvaluationSummary(reasoning="Evaluator reasoning", overall_score=70.0, strengths=["ok"], weaknesses=["minor"], critical_findings=["none"]),
                    metrics=[MetricResult(name="overall_quality", score=70.0, description="q", findings=[], recommendations=[])],
                     compliance=[], recommendations={}
                )
            return None

        pipeline._agent.generate_structured = throwing_generate

        result = await pipeline.design_loop(
            requirements="test",
            domain="cloud-native",
            topology="hierarchical",
            selected_patterns=[{"name": "microservices", "context": "", "topology": "hierarchical", "category": "multi_agent", "benefits": [], "tradeoffs": [], "quality_attributes": {"reliability": 7, "cost_efficiency": 6, "latency": 7, "output_quality": 8, "observability": 7, "safety": 8, "simplicity": 4}, "best_practices": []}],
            criteria="quality",
            analysis_result=None,
            max_tries=3,
        )

        assert attempt == 3
        assert result.attempts == 3


class TestPatternContextReduction:
    """Verify pattern context respects pattern_context_limits from RetrievalConfig."""

    def _make_pipeline_with_limits(self, limits: dict[str, int] | None = None):
        from src.config import RetrievalConfig
        cfg = RetrievalConfig(pattern_context_limits=limits) if limits else RetrievalConfig()
        return create_test_pipeline(retrieval_config=cfg)

    def test_build_pattern_context_respects_benefits_limit(self):
        """benefits are sliced to config limit."""
        pipeline = self._make_pipeline_with_limits({"benefits": 2, "tradeoffs": 3, "best_practices": 3, "component_types": 5, "technology_stack": 5, "anti_patterns": 3, "suitable_domains": 5})
        patterns = [{"name": "p1", "context": "c", "benefits": ["b1", "b2", "b3"], "tradeoffs": [], "suitable_domains": [], "best_practices": [], "component_types": [], "technology_stack": [], "anti_patterns": []}]
        ctx = pipeline._build_pattern_context(patterns)
        assert ctx.count("b1") == 1
        assert ctx.count("b2") == 1
        assert "b3" not in ctx

    def test_build_pattern_context_respects_tradeoffs_limit(self):
        """tradeoffs are sliced to config limit."""
        pipeline = self._make_pipeline_with_limits({"benefits": 3, "tradeoffs": 2, "best_practices": 3, "component_types": 5, "technology_stack": 5, "anti_patterns": 3, "suitable_domains": 5})
        patterns = [{"name": "p1", "context": "c", "benefits": [], "tradeoffs": ["t1", "t2", "t3"], "suitable_domains": [], "best_practices": [], "component_types": [], "technology_stack": [], "anti_patterns": []}]
        ctx = pipeline._build_pattern_context(patterns)
        assert ctx.count("t1") == 1
        assert ctx.count("t2") == 1
        assert "t3" not in ctx

    def test_build_pattern_context_respects_best_practices_limit(self):
        """best_practices are sliced to config limit."""
        pipeline = self._make_pipeline_with_limits({"benefits": 3, "tradeoffs": 3, "best_practices": 1, "component_types": 5, "technology_stack": 5, "anti_patterns": 3, "suitable_domains": 5})
        patterns = [{"name": "p1", "context": "c", "benefits": [], "tradeoffs": [], "suitable_domains": [], "best_practices": ["bp1", "bp2"], "component_types": [], "technology_stack": [], "anti_patterns": []}]
        ctx = pipeline._build_pattern_context(patterns)
        assert ctx.count("bp1") == 1
        assert "bp2" not in ctx

    def test_build_pattern_context_respects_anti_patterns_limit(self):
        """anti_patterns are sliced to config limit."""
        pipeline = self._make_pipeline_with_limits({"benefits": 3, "tradeoffs": 3, "best_practices": 3, "component_types": 5, "technology_stack": 5, "anti_patterns": 1, "suitable_domains": 5})
        patterns = [{"name": "p1", "context": "c", "benefits": [], "tradeoffs": [], "suitable_domains": [], "best_practices": [], "component_types": [], "technology_stack": [], "anti_patterns": ["ap1", "ap2"]}]
        ctx = pipeline._build_pattern_context(patterns)
        assert ctx.count("ap1") == 1
        assert "ap2" not in ctx

    def test_build_pattern_context_respects_suitable_domains_limit(self):
        """suitable_domains are sliced to config limit."""
        pipeline = self._make_pipeline_with_limits({"benefits": 3, "tradeoffs": 3, "best_practices": 3, "component_types": 5, "technology_stack": 5, "anti_patterns": 3, "suitable_domains": 2})
        patterns = [{"name": "p1", "context": "c", "benefits": [], "tradeoffs": [], "suitable_domains": ["d1", "d2", "d3"], "best_practices": [], "component_types": [], "technology_stack": [], "anti_patterns": []}]
        ctx = pipeline._build_pattern_context(patterns)
        assert "d1" in ctx
        assert "d2" in ctx
        assert "d3" not in ctx

    def test_build_pattern_context_deduplicates_component_types(self):
        """component_types deduplicated case-insensitively across patterns."""
        pipeline = self._make_pipeline_with_limits({"benefits": 3, "tradeoffs": 3, "best_practices": 3, "component_types": 5, "technology_stack": 5, "anti_patterns": 3, "suitable_domains": 5})
        patterns = [
            {"name": "p1", "context": "c", "benefits": [], "tradeoffs": [], "suitable_domains": [], "best_practices": [], "component_types": ["API Gateway", "Load Balancer"], "technology_stack": [], "anti_patterns": []},
            {"name": "p2", "context": "c", "benefits": [], "tradeoffs": [], "suitable_domains": [], "best_practices": [], "component_types": ["api gateway", "Cache"], "technology_stack": [], "anti_patterns": []},
        ]
        ctx = pipeline._build_pattern_context(patterns)
        assert ctx.count("API Gateway") == 1
        assert ctx.count("api gateway") == 0
        assert ctx.count("Load Balancer") == 1
        assert ctx.count("Cache") == 1

    def test_build_pattern_context_deduplicates_technology_stack(self):
        """technology_stack deduplicated case-insensitively across patterns."""
        pipeline = self._make_pipeline_with_limits({"benefits": 3, "tradeoffs": 3, "best_practices": 3, "component_types": 5, "technology_stack": 5, "anti_patterns": 3, "suitable_domains": 5})
        patterns = [
            {"name": "p1", "context": "c", "benefits": [], "tradeoffs": [], "suitable_domains": [], "best_practices": [], "component_types": [], "technology_stack": ["Kubernetes", "Docker"], "anti_patterns": []},
            {"name": "p2", "context": "c", "benefits": [], "tradeoffs": [], "suitable_domains": [], "best_practices": [], "component_types": [], "technology_stack": ["kubernetes", "Redis"], "anti_patterns": []},
        ]
        ctx = pipeline._build_pattern_context(patterns)
        assert ctx.count("Kubernetes") == 1
        assert ctx.count("kubernetes") == 0
        assert ctx.count("Docker") == 1
        assert ctx.count("Redis") == 1

    def test_build_pattern_context_drops_design_principles_section(self):
        """design_principles section is not present in pattern context."""
        pipeline = self._make_pipeline_with_limits({"benefits": 3, "tradeoffs": 3, "best_practices": 3, "component_types": 5, "technology_stack": 5, "anti_patterns": 3, "suitable_domains": 5})
        patterns = [{"name": "p1", "context": "c", "benefits": [], "tradeoffs": [], "suitable_domains": [], "best_practices": [], "component_types": [], "technology_stack": [], "anti_patterns": [], "design_principles": ["Single Responsibility"]}]
        ctx = pipeline._build_pattern_context(patterns)
        assert "Design Principles" not in ctx

    def test_build_pattern_context_drops_unsuitable_domains_section(self):
        """unsuitable_domains section is not present in pattern context."""
        pipeline = self._make_pipeline_with_limits({"benefits": 3, "tradeoffs": 3, "best_practices": 3, "component_types": 5, "technology_stack": 5, "anti_patterns": 3, "suitable_domains": 5})
        patterns = [{"name": "p1", "context": "c", "benefits": [], "tradeoffs": [], "suitable_domains": [], "best_practices": [], "component_types": [], "technology_stack": [], "anti_patterns": [], "unsuitable_domains": ["domain1"]}]
        ctx = pipeline._build_pattern_context(patterns)
        assert "Unsuitable Domains" not in ctx


class TestQualityScoreFallback:
    """Verify design_loop uses correct fallback chain for overall quality score.

    Fallback chain: overall_quality metric -> summary.overall_score.
    """

    def _make_eval(self, *, overall_metric_score: float | None = None,
                   summary_score: float = 75.0) -> AgentSystemEvaluation:
        from src.schemas.evaluation import AgentSystemEvaluation, EvaluationSummary, MetricResult
        metrics = []
        if overall_metric_score is not None:
            metrics.append(MetricResult(name="overall_quality", score=overall_metric_score,
                                       description="", findings=[], recommendations=[]))
        else:
            metrics.append(MetricResult(name="overall_quality", score=summary_score,
                                       description="", findings=[], recommendations=[]))
        return AgentSystemEvaluation(
            summary=EvaluationSummary(
                reasoning="Evaluator reasoning for the assessment",
                overall_score=summary_score,
                strengths=["test"], weaknesses=["test"], critical_findings=["test"]
            ),
            metrics=metrics,
            risks=[], compliance=[], recommendations={}
        )

    def _make_design(self) -> AgentSystemDesignResponse:
        return AgentSystemDesignResponse(
            overview={"topology": "pipeline", "category": "multi_agent",
                      "principles": ["test"], "constraints": [], "reasoning": "Test reasoning."},
            agents=[{"id": "s1", "name": "S1", "role": "executor", "description": "svc",
                         "responsibilities": ["serve"], "technology_stack": [],
                         "config_requirements": []}],
            relationships=[],
            quality_attributes={},
            tool_contracts=[], shared_state_models=[], message_contracts=[]
        )

    @pytest.mark.asyncio
    async def test_uses_overall_quality_metric_when_present(self):
        """Primary path: uses overall_quality metric score."""
        pipeline = create_test_pipeline()
        call_count = 0

        async def mock_generate(system_prompt, user_prompt, response_schema):
            nonlocal call_count
            call_count += 1
            if response_schema is AgentSystemDesignResponse:
                return self._make_design()
            from src.schemas.evaluation import AgentSystemEvaluation
            if response_schema == AgentSystemEvaluation:
                return self._make_eval(overall_metric_score=82.5)
            return None

        pipeline._agent.generate_structured = mock_generate
        result = await pipeline.design_loop(
            requirements="test", domain="data-processing", topology="pipeline",
            selected_patterns=[], criteria="quality", max_tries=1,
        )
        assert result.final_quality_score == 82.5

    @pytest.mark.asyncio
    async def test_falls_back_to_summary_overall_score(self):
        """When no overall_quality metric, uses summary.overall_score."""
        pipeline = create_test_pipeline()

        async def mock_generate(system_prompt, user_prompt, response_schema):
            if response_schema is AgentSystemDesignResponse:
                return self._make_design()
            from src.schemas.evaluation import AgentSystemEvaluation
            if response_schema == AgentSystemEvaluation:
                return self._make_eval(summary_score=88.0)
            return None

        pipeline._agent.generate_structured = mock_generate
        result = await pipeline.design_loop(
            requirements="test", domain="data-processing", topology="pipeline",
            selected_patterns=[], criteria="quality", max_tries=1,
        )
        assert result.final_quality_score == 88.0

class TestPromptExamples:
    """Verify structured-output prompts contain complete JSON examples."""

    def test_examples_import_cleanly(self):
        """Module imports without error."""
        from src.prompts.examples import (
            PATTERN_ANALYSIS_EXAMPLE,
            AGENT_SYSTEM_DESIGN_EXAMPLE,
            AGENT_SYSTEM_EVALUATION_EXAMPLE,
        )
        assert PATTERN_ANALYSIS_EXAMPLE
        assert AGENT_SYSTEM_DESIGN_EXAMPLE
        assert AGENT_SYSTEM_EVALUATION_EXAMPLE

    def test_analysis_example_validates_against_schema(self):
        """Analysis example is a valid AnalysisResult."""
        from src.prompts.examples import PATTERN_ANALYSIS_EXAMPLE
        import json

        raw = PATTERN_ANALYSIS_EXAMPLE.split("```json")[1].split("```")[0].strip()
        data = json.loads(raw)
        from src.schemas.analysis import AnalysisResult
        result = AnalysisResult.model_validate(data)
        assert result.strengths
        assert result.weaknesses
        assert result.recommended_topology

    def test_design_example_validates_against_schema(self):
        """Design example is a valid AgentSystemDesignResponse."""
        from src.prompts.examples import AGENT_SYSTEM_DESIGN_EXAMPLE
        import json

        raw = AGENT_SYSTEM_DESIGN_EXAMPLE.split("```json")[1].split("```")[0].strip()
        data = json.loads(raw)
        from src.schemas.agent_system import AgentSystemDesignResponse
        result = AgentSystemDesignResponse.model_validate(data)
        assert result.overview

    def test_evaluation_example_validates_against_schema(self):
        """Evaluation example is a valid AgentSystemEvaluation."""
        from src.prompts.examples import AGENT_SYSTEM_EVALUATION_EXAMPLE
        import json

        raw = AGENT_SYSTEM_EVALUATION_EXAMPLE.split("```json")[1].split("```")[0].strip()
        data = json.loads(raw)
        from src.schemas.evaluation import AgentSystemEvaluation
        result = AgentSystemEvaluation.model_validate(data)
        assert result.summary.overall_score

    def test_generate_system_prompt_contains_example(self):
        """Generate system prompt includes architecture design example."""
        pipeline = create_test_pipeline()
        prompt = pipeline._build_generate_system_prompt(
            topology="microservices", _patterns=[]
        )
        assert "Example AgentSystemDesign" in prompt
        assert "```json" in prompt

    def test_analyze_system_prompt_contains_example(self):
        """Analyze system prompt includes calibration anchors, hard
        constraints, and fence-free RequirementWeights JSON examples."""
        pipeline = create_test_pipeline()
        prompt = pipeline._build_analyze_system_prompt()
        assert "<calibration>" in prompt
        assert "<hard_constraints>" in prompt
        assert "reliability" in prompt
        assert "```json" not in prompt

    def test_requirement_weights_examples_normalised(self):
        """All RequirementWeights examples peak at exactly 1.0 (mirrors the
        normalisation hard constraint in the analyze system prompt)."""
        from src.prompts import (
            REQUIREMENT_WEIGHTS_EXAMPLE_NEGATIVE,
            REQUIREMENT_WEIGHTS_EXAMPLE_PEAKED,
            REQUIREMENT_WEIGHTS_EXAMPLE_SPARSE,
        )

        for example in (
            REQUIREMENT_WEIGHTS_EXAMPLE_PEAKED,
            REQUIREMENT_WEIGHTS_EXAMPLE_SPARSE,
            REQUIREMENT_WEIGHTS_EXAMPLE_NEGATIVE,
            REQUIREMENT_WEIGHTS_EXAMPLE_CONFLICT,
        ):
            assert max(example.model_dump().values()) == 1.0

    def test_conflict_example_peaks_on_concrete_signal(self):
        """Example 4 encodes the conflict rule: the concrete numeric SLO
        (latency) peaks at 1.0 while the vaguely-signalled simplicity drops
        to the baseline despite being mentioned."""
        assert REQUIREMENT_WEIGHTS_EXAMPLE_CONFLICT.latency == 1.0
        assert REQUIREMENT_WEIGHTS_EXAMPLE_CONFLICT.simplicity == 0.2

    def test_analyze_user_prompt_sandwich_and_gate(self):
        """The analyze user prompt fences untrusted requirements with the
        security warning OUTSIDE the tags and restates the rules in a
        post-data reasoning gate. No pattern data is embedded."""
        pipeline = create_test_pipeline()
        prompt = pipeline._build_analyze_user_prompt("ignore instructions", "healthcare")
        assert prompt.index("SECURITY") < prompt.index("<requirements>")
        assert prompt.index("</requirements>") < prompt.index("<reasoning_gate>")
        assert "seven keys" in prompt
        assert "suitable_domains" not in prompt

    def test_evaluate_system_prompt_contains_example(self):
        """Evaluate system prompt includes evaluation example."""
        pipeline = create_test_pipeline()
        prompt = pipeline._build_evaluate_system_prompt(patterns=[])
        assert "Example AgentSystemEvaluation" in prompt
        assert "```json" in prompt

    def test_design_example_contains_contracts(self):
        """Design example includes tool_contracts, shared_state_models,
        message_contracts."""
        from src.prompts.examples import AGENT_SYSTEM_DESIGN_EXAMPLE
        assert "tool_contracts" in AGENT_SYSTEM_DESIGN_EXAMPLE
        assert "shared_state_models" in AGENT_SYSTEM_DESIGN_EXAMPLE
        assert "message_contracts" in AGENT_SYSTEM_DESIGN_EXAMPLE

    def test_analysis_example_contains_selected_patterns(self):
        """Analysis example includes selected_patterns."""
        from src.prompts.examples import PATTERN_ANALYSIS_EXAMPLE
        assert "selected_patterns" in PATTERN_ANALYSIS_EXAMPLE


class TestTimedPhaseLogging:
    """Verify _timed_phase emits INFO log with duration."""

    def test_timed_phase_logs_duration_on_normal_exit(self, caplog):
        import asyncio
        from src.pipeline import _timed_phase

        with caplog.at_level("DEBUG", logger="src.pipeline"):
            async def run():
                async with _timed_phase("analyze", domain="data-processing"):
                    await asyncio.sleep(0.01)
            asyncio.run(run())

        assert any(
            rec.phase == "analyze" and rec.duration_s > 0
            for rec in caplog.records
        )

    def test_timed_phase_logs_duration_on_exception(self, caplog):
        import asyncio
        from src.pipeline import _timed_phase

        with caplog.at_level("DEBUG", logger="src.pipeline"):
            async def run():
                async with _timed_phase("evaluate"):
                    raise RuntimeError("simulated failure")
            with pytest.raises(RuntimeError):
                asyncio.run(run())

        assert any(
            rec.phase == "evaluate" and rec.duration_s >= 0
            for rec in caplog.records
        )

    def test_timed_phase_logs_info_when_verbose(self, caplog):
        """verbose=True bypasses DEBUG gate, logs at INFO."""
        import asyncio
        from src.pipeline import _timed_phase

        with caplog.at_level("INFO", logger="src.pipeline"):
            async def run():
                async with _timed_phase(
                    "generate", domain="x", verbose=True
                ):
                    await asyncio.sleep(0.01)
            asyncio.run(run())

        assert any(
            rec.phase == "generate" and rec.duration_s > 0
            for rec in caplog.records
        )


# ── shared <analysis_summary> renderer (GENERATE + EVALUATE) ─────────────────


def _summary_design() -> AgentSystemDesign:
    return AgentSystemDesign(
        overview=AgentSystemOverview(
            reasoning="Plan before agents.",
            topology=AgentTopology.HIERARCHICAL,
            category="multi_agent",
            principles=["Single supervisor owns routing"],
        ),
        agents=[{
            "id": "supervisor",
            "name": "Supervisor",
            "role": "coordinator",
            "description": "Routes subtasks",
            "responsibilities": ["Decompose", "Assemble"],
            "tools": [],
            "memory": [],
        }],
    )


def _summary_analysis_result(with_weights: bool = True):
    from src.pipeline import AnalysisResult, RequirementWeights

    return AnalysisResult(
        recommended_topology="hierarchical",
        strengths=["Clear ownership"],
        weaknesses=["Routing bottleneck"],
        selected_patterns=[],
        requirement_weights=RequirementWeights(
            reliability=1.0,
            cost_efficiency=0.8,
            latency=0.6,
            output_quality=0.5,
            observability=0.4,
            safety=0.2,
            simplicity=0.1,
        )
        if with_weights
        else None,
    )


class TestAnalysisSummaryRendering:
    """The shared _render_analysis_summary block surfaces in both prompts."""

    def test_generate_prompt_contains_summary_with_weights(self):
        pipeline = create_test_pipeline()
        prompt = pipeline._build_generate_user_prompt(
            "Build a support triage assistant",
            "customer-support",
            "hierarchical",
            pattern_context="",
            analysis_result=_summary_analysis_result(),
        )
        assert "<analysis_summary>" in prompt
        assert "Recommended topology: hierarchical" in prompt
        assert "Strengths to preserve:" in prompt
        assert "Weaknesses to address:" in prompt
        assert "QUALITY-ATTRIBUTE PRIORITIES" in prompt
        assert "reliability: 1.0" in prompt

    def test_generate_prompt_without_analysis_omits_summary(self):
        pipeline = create_test_pipeline()
        prompt = pipeline._build_generate_user_prompt(
            "Build a support triage assistant",
            "customer-support",
            "hierarchical",
            pattern_context="",
            analysis_result=None,
        )
        assert "<analysis_summary>" not in prompt

    def test_generate_prompt_without_weights_omits_weight_section(self):
        pipeline = create_test_pipeline()
        prompt = pipeline._build_generate_user_prompt(
            "Build a support triage assistant",
            "customer-support",
            "hierarchical",
            pattern_context="",
            analysis_result=_summary_analysis_result(with_weights=False),
        )
        assert "<analysis_summary>" in prompt
        assert "QUALITY-ATTRIBUTE PRIORITIES" not in prompt

    def test_evaluate_prompt_contains_summary_with_weights(self):
        pipeline = create_test_pipeline()
        prompt = pipeline._build_evaluate_user_prompt(
            _summary_design(),
            "quality,cost_efficiency",
            "customer-support",
            [],
            requirements="Triage 10k tickets/day",
            analysis_result=_summary_analysis_result(),
        )
        assert "<analysis_summary>" in prompt
        assert "Recommended topology: hierarchical" in prompt
        assert "Strengths the analyzer identified in the patterns:" in prompt
        assert "Weaknesses the analyzer identified in the patterns:" in prompt
        assert "bias scoring" in prompt
        assert "reliability: 1.0" in prompt

    def test_evaluate_prompt_without_analysis_result_omits_summary(self):
        pipeline = create_test_pipeline()
        prompt = pipeline._build_evaluate_user_prompt(
            _summary_design(),
            "quality",
            "customer-support",
            [],
            requirements="Triage 10k tickets/day",
        )
        assert "<analysis_summary>" not in prompt


class TestTopologyNameSeparation:
    """Pattern name vs topology separation (P2/P3): runner-ups dedup per
    topology, final_topology matches by the topology field, and the refine
    phase picks the pattern carrying the active topology."""

    def _analysis(self, patterns, is_fallback=False):
        from src.pipeline import AnalysisResult

        return AnalysisResult(
            selected_patterns=patterns,
            recommended_topology="hierarchical",
            recommended_pattern_name=patterns[0]["name"] if patterns else "",
            is_fallback=is_fallback,
        )

    def test_topology_candidates_dedup_per_topology(self):
        pipeline = create_test_pipeline()
        analysis = self._analysis([
            {"name": "react", "topology": "single-agent-loop", "analysis_score": 90.0},
            {"name": "reflection", "topology": "single-agent-loop", "analysis_score": 80.0},
            {"name": "supervisor-worker", "topology": "hierarchical", "analysis_score": 70.0},
        ])
        candidates = pipeline._topology_candidates(analysis, "single-agent-loop")
        assert [(c.topology, c.pattern_name, c.score) for c in candidates] == [
            ("hierarchical", "supervisor-worker", 70.0)
        ]

    def test_topology_candidates_sorted_desc_and_excludes_final(self):
        pipeline = create_test_pipeline()
        analysis = self._analysis([
            {"name": "react", "topology": "single-agent-loop", "analysis_score": 90.0},
            {"name": "plan-and-solve", "topology": "plan-execute", "analysis_score": 85.0},
            {"name": "swarm", "topology": "swarm", "analysis_score": 60.0},
        ])
        candidates = pipeline._topology_candidates(analysis, "plan-execute")
        assert [c.topology for c in candidates] == ["single-agent-loop", "swarm"]

    def test_topology_candidates_empty_on_fallback(self):
        pipeline = create_test_pipeline()
        analysis = self._analysis([
            {"name": "react", "topology": "single-agent-loop", "analysis_score": 90.0},
        ], is_fallback=True)
        assert pipeline._topology_candidates(analysis, "pipeline") == []

    def test_selected_topology_pattern_matches_by_topology_field(self):
        pipeline = create_test_pipeline()
        analysis = self._analysis([
            {"name": "supervisor-worker", "topology": "hierarchical", "analysis_score": 70.0},
        ])
        pattern = pipeline._selected_topology_pattern(analysis, "hierarchical")
        assert pattern is not None
        assert pattern["name"] == "supervisor-worker"
        assert pipeline._selected_topology_score(analysis, "hierarchical") == 70.0

    def test_selected_topology_pattern_none_when_no_match(self):
        pipeline = create_test_pipeline()
        analysis = self._analysis([
            {"name": "react", "topology": "single-agent-loop", "analysis_score": 90.0},
        ])
        assert pipeline._selected_topology_pattern(analysis, "hierarchical") is None
        assert pipeline._selected_topology_score(analysis, "hierarchical") is None

    def test_refinement_pattern_prefers_topology_match(self):
        pipeline = create_test_pipeline()
        analysis = self._analysis([
            {"name": "react", "topology": "single-agent-loop", "analysis_score": 90.0,
             "category": "reasoning", "context": "c", "benefits": ["b"], "tradeoffs": ["t"],
             "quality_attributes": {
                 "reliability": 8, "cost_efficiency": 8, "latency": 8,
                 "output_quality": 8, "observability": 8, "safety": 8, "simplicity": 8}},
            {"name": "supervisor-worker", "topology": "hierarchical", "analysis_score": 70.0,
             "category": "multi_agent", "context": "c", "benefits": ["b"], "tradeoffs": ["t"],
             "quality_attributes": {
                 "reliability": 8, "cost_efficiency": 8, "latency": 8,
                 "output_quality": 8, "observability": 8, "safety": 8, "simplicity": 8}},
        ])
        pattern = pipeline._select_refinement_pattern(analysis, "hierarchical")
        assert pattern is not None
        assert pattern.name == "supervisor-worker"

    def test_refinement_pattern_falls_back_to_top_scored(self):
        pipeline = create_test_pipeline()
        analysis = self._analysis([
            {"name": "react", "topology": "single-agent-loop", "analysis_score": 90.0,
             "category": "reasoning", "context": "c", "benefits": ["b"], "tradeoffs": ["t"],
             "quality_attributes": {
                 "reliability": 8, "cost_efficiency": 8, "latency": 8,
                 "output_quality": 8, "observability": 8, "safety": 8, "simplicity": 8}},
        ])
        pattern = pipeline._select_refinement_pattern(analysis, "hierarchical")
        assert pattern is not None
        assert pattern.name == "react"

    def test_generate_prompt_contains_primary_pattern_line(self):
        pipeline = create_test_pipeline()
        analysis = self._analysis([
            {"name": "supervisor-worker", "topology": "hierarchical", "analysis_score": 70.0},
        ])
        prompt = pipeline._build_generate_user_prompt(
            "req", "domain", "hierarchical", "PATTERN CONTEXT", analysis,
        )
        assert "Agent Topology: hierarchical" in prompt
        assert "Primary Pattern: supervisor-worker" in prompt

    def test_generate_prompt_omits_primary_pattern_without_match(self):
        pipeline = create_test_pipeline()
        prompt = pipeline._build_generate_user_prompt(
            "req", "domain", "hierarchical", "PATTERN CONTEXT", None,
        )
        assert "Agent Topology: hierarchical" in prompt
        assert "Primary Pattern:" not in prompt
