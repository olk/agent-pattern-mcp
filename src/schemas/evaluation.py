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
Agent system evaluation and pipeline result schemas.

Defines quality assessment and pipeline output structures.
"""

from typing import Any

from pydantic import BaseModel, Field

from src.schemas.analysis import MatchedDomain, TopologyCandidate
from src.schemas.design import AgentSystemDesign
from src.schemas.quality import QualityMetrics


class MetricResult(BaseModel):
    """
    Individual quality metric assessment result.
    """

    name: str = Field(
        ...,
        description="Metric name (e.g. 'reliability', 'cost_efficiency')"
    )
    score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Assessment score (0-100)"
    )
    description: str = Field(
        ...,
        description="Metric description"
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Supporting findings for this metric"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations to improve this metric"
    )


class EvaluationSummary(BaseModel):
    """
    High-level evaluation summary with score and key findings.

    AC-214: The ``reasoning`` field captures the evaluator's structured thinking
    before committing to scores and recommendations, ensuring traceable rationale.
    """

    reasoning: str = Field(
        ...,
        min_length=1,
        description="Evaluator's structured reasoning: which requirements drive which scores, which patterns apply, which anti-patterns were identified, and key trade-offs accepted"
    )
    overall_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Overall agent system quality score"
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="Agent system strengths"
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Agent system weaknesses"
    )
    critical_findings: list[str] = Field(
        default_factory=list,
        description="Critical findings that must be addressed"
    )


class AgentSystemEvaluation(BaseModel):
    """
    Complete agent system evaluation result.

    Contains metric assessments, risks, compliance, and recommendations.
    """

    summary: EvaluationSummary = Field(
        ...,
        description="High-level evaluation summary"
    )
    metrics: list[MetricResult] = Field(
        ...,
        min_length=1,
        description="Per-metric assessment results"
    )
    risks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Risk assessments"
    )
    compliance: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Compliance assessments"
    )
    recommendations: dict[str, list[str]] = Field(
        ...,
        description="Recommendations keyed by area (e.g. {'reliability': [...], 'safety': [...]})"
    )


class PipelineResult(BaseModel):
    """
    Complete pipeline output combining design, evaluation, and metadata.

    Returned by the full agent system pipeline (analyze → generate → evaluate → design_loop).
    """

    design: AgentSystemDesign = Field(
        ...,
        description="AgentSystemDesign"
    )
    evaluation: AgentSystemEvaluation = Field(
        ...,
        description="AgentSystemEvaluation"
    )
    attempts: int = Field(
        ...,
        ge=1,
        description="Total generate attempts made (initial + retries)"
    )
    final_topology: str = Field(
        ...,
        description="Final agent topology (an AgentTopology value)"
    )
    final_pattern_name: str = Field(
        default="",
        description="Name of the top-scored pattern matching final_topology ('' when the topology was overridden or no patterns were scored)"
    )
    quality_metrics: QualityMetrics | None = Field(
        default=None,
        description="Aggregated quality metrics"
    )
    final_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Final quality score after best attempt"
    )
    matched_domains: list[MatchedDomain] = Field(
        default_factory=list,
        description="Top matched AgentDomain slugs from BM25+FAISS retrieval (max 5)"
    )
    is_fallback: bool = Field(
        default=False,
        description="True when retrieval produced no real candidates and used fallback"
    )
    alternative_topologies: list[TopologyCandidate] = Field(
        default_factory=list,
        description=(
            "Runner-up topologies from the analyze phase that scored below the final selected topology. "
            "Excludes the entry matching final_topology. Empty when is_fallback is True. "
            "Sorted by score descending."
        ),
    )
