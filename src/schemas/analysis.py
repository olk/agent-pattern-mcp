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
Agent system analysis result schema.

Output from the ANALYZE phase of the pipeline.
"""

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.patterns import ScoredPattern
from src.schemas.quality import QualityMetrics


# Canonical quality-attribute keys present in every pattern's quality_attributes.
# Verified uniform across the 61-pattern catalogue. Used for deterministic
# requirements-aware scoring of candidates in the analyze phase.
QUALITY_ATTRIBUTE_KEYS: tuple[str, ...] = (
    "reliability",
    "cost_efficiency",
    "latency",
    "output_quality",
    "observability",
    "safety",
    "simplicity",
)


class RequirementWeights(BaseModel):
    """Requirement priority weights (0.0-1.0) extracted from requirements.

    Produced by a single lightweight LLM call in the analyze phase. Each weight
    expresses how strongly the requirements emphasise that quality attribute.
    Consumed by ``_score_patterns`` to deterministically score each candidate
    pattern's ``quality_attributes`` against the stated priorities.

    The LLM prompt carries ONLY the requirements and these seven attribute names —
    no pattern data — keeping the call small and focused.
    """

    model_config = ConfigDict(extra="allow")

    reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    cost_efficiency: float = Field(default=0.0, ge=0.0, le=1.0)
    latency: float = Field(default=0.0, ge=0.0, le=1.0)
    output_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    observability: float = Field(default=0.0, ge=0.0, le=1.0)
    safety: float = Field(default=0.0, ge=0.0, le=1.0)
    simplicity: float = Field(default=0.0, ge=0.0, le=1.0)

    def as_dict(self) -> dict[str, float]:
        """Return the weights keyed by quality-attribute name."""
        return {k: float(getattr(self, k)) for k in QUALITY_ATTRIBUTE_KEYS}


class MatchedDomain(BaseModel):
    """
    A resolved agent domain slug from the BM25+FAISS hybrid retriever.

    Returned in tool outputs so calling agents can see which domain slugs
    were matched and how confidently (fusion score and, when reranking ran,
    cross-encoder rerank logit).
    """

    slug: str = Field(..., description="AgentDomain slug (e.g. 'customer-support', 'tool-use-tasks')")
    fusion_score: float = Field(..., description="RRF fusion score for this slug (higher = better match)")
    rerank_score: float | None = Field(
        default=None,
        description="Cross-encoder rerank logit for this slug (None when reranking did not run).",
    )


class TopologyCandidate(BaseModel):
    """A runner-up agent topology from the analyze phase.

    Surfaced in design tool outputs so calling agents can see which other
    topologies the analyzer scored highly but the pipeline did not select as
    the final topology. One entry per distinct AgentTopology among the scored
    candidates, represented by its best-scoring pattern. Excludes the final
    topology; empty when is_fallback=True.
    """

    pattern_name: str = Field(..., description="Name of the best-scoring pattern carrying this topology")
    topology: str = Field(..., description="AgentTopology value (e.g. 'hierarchical', 'single-agent-loop')")
    score: float = Field(..., description="Effective sort score (analysis_score) of the representing pattern; higher is better")


class AnalysisResult(BaseModel):
    """
    Result of agent system requirements analysis.

    Contains strengths, weaknesses, recommendations, quality metrics,
    and selected patterns from the ANALYZE phase.
    """

    strengths: list[str] = Field(
        default_factory=list,
        description="Identified agent system strengths"
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Identified agent system weaknesses"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Agent system recommendations"
    )
    quality_metrics: QualityMetrics | None = Field(
        default=None,
        description="Quality assessment metrics"
    )
    recommended_topology: str = Field(
        ...,
        description="AgentTopology value best suited for the requirements (e.g. 'hierarchical', 'single-agent-loop')"
    )
    recommended_pattern_name: str = Field(
        default="",
        description="Name of the top-scored pattern that drove the topology recommendation ('' when no patterns were scored)"
    )
    selected_patterns: list[ScoredPattern] = Field(
        default_factory=list,
        description="Patterns selected during analysis, ordered by analysis_score descending",
    )
    matched_domains: list[MatchedDomain] = Field(
        default_factory=list,
        description="Top matched AgentDomain slugs from BM25+FAISS retrieval (max 5, ordered by fusion score)"
    )
    is_fallback: bool = Field(
        default=False,
        description="True when no real domain match was found and the fallback 'react' pattern was used"
    )
    rationale: str = Field(
        default="",
        description="Rationale for the analysis and pattern selection"
    )
