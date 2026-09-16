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
Agent pattern schema.

Defines the structure of a single agent pattern (e.g. react, supervisor-worker, self-rag).
"""

from pydantic import BaseModel, Field, model_validator

from src.schemas.enums import AgentDomain, AgentTopology, PatternCategory


class PatternQualityAttributes(BaseModel):
    """
    Typed quality attributes for an agent pattern (7 dimensions, 1-10 scale).

    Provides a mean() helper and quality_score property (0-100 scale)
    for deterministic scoring during the analyze phase.
    """

    reliability: float = Field(..., ge=1, le=10, description="System reliability")
    cost_efficiency: float = Field(..., ge=1, le=10, description="Cost efficiency")
    latency: float = Field(..., ge=1, le=10, description="Latency performance")
    output_quality: float = Field(..., ge=1, le=10, description="Output quality")
    observability: float = Field(..., ge=1, le=10, description="Observability")
    safety: float = Field(..., ge=1, le=10, description="Safety")
    simplicity: float = Field(..., ge=1, le=10, description="Simplicity")

    def mean(self) -> float:
        values = (
            self.reliability,
            self.cost_efficiency,
            self.latency,
            self.output_quality,
            self.observability,
            self.safety,
            self.simplicity,
        )
        return sum(values) / len(values)


class Pattern(BaseModel):
    """
    Agent pattern definition.

    Describes a named agent pattern with its context, tradeoffs,
    quality attributes, topology, and suitability domain mapping.

    Pattern JSON files in pattern/ are validated against this schema.
    """

    topology: AgentTopology = Field(
        ...,
        description="Agent topology from AgentTopology enum"
    )
    category: PatternCategory = Field(
        ...,
        description="Pattern category from PatternCategory enum"
    )
    name: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9-]*$",
        description="Pattern name, e.g. 'react', 'supervisor-worker', 'self-rag'"
    )
    context: str = Field(
        ...,
        min_length=1,
        description="When to use this pattern — problem context and forces"
    )
    benefits: list[str] = Field(
        ...,
        min_length=1,
        description="Positive outcomes and advantages this pattern provides"
    )
    tradeoffs: list[str] = Field(
        ...,
        min_length=1,
        description="Concrete costs, risks, and disadvantages this pattern introduces"
    )
    quality_attributes: PatternQualityAttributes = Field(
        ...,
        description="Typed quality metric scores (1-10 scale, 7 dimensions)"
    )
    suitable_domains: list[AgentDomain] = Field(
        default_factory=list,
        description="Problem-space domains where this pattern excels"
    )
    unsuitable_domains: list[AgentDomain] = Field(
        default_factory=list,
        description="Problem-space domains where this pattern may not fit"
    )
    use_cases: list[str] = Field(
        default_factory=list,
        description="Concrete scenarios when to use this pattern"
    )
    avoid_when: list[str] = Field(
        default_factory=list,
        description="Concrete scenarios when to avoid this pattern"
    )
    component_types: list[str] = Field(
        default_factory=list,
        description="Component types typically needed"
    )
    technology_stack: list[str] = Field(
        default_factory=list,
        description="Typical technology choices"
    )
    anti_patterns: list[str] = Field(
        default_factory=list,
        description="Common mistakes with this pattern"
    )
    migration_from: list[str] = Field(
        default_factory=list,
        description="Patterns commonly migrated from"
    )
    migration_to: list[str] = Field(
        default_factory=list,
        description="Patterns commonly migrated to"
    )
    design_principles: list[str] = Field(
        default_factory=list,
        description="Core design principles"
    )
    best_practices: list[str] = Field(
        default_factory=list,
        description="Best practices"
    )
    references: list[str] = Field(
        default_factory=list,
        description="Canonical citations (paper/blog) — one string per reference, e.g. 'Authors, Title, Year — https://url'"
    )

    @model_validator(mode="after")
    def _domains_disjoint(self) -> "Pattern":
        overlap = set(self.suitable_domains) & set(self.unsuitable_domains)
        if overlap:
            raise ValueError(
                f"Pattern '{self.name}': suitable_domains and unsuitable_domains "
                f"must be disjoint, but found overlap: {sorted(overlap)}"
            )
        return self

    @property
    def quality_score(self) -> float:
        """Quality score on 0-100 scale (mean of 7 dims × 10)."""
        return round(self.quality_attributes.mean() * 10, 1)


class ScoredPattern(Pattern):
    """Pattern enriched with two-stage analyze scores (response boundary only).

    Used only in AnalysisResult.selected_patterns to preserve score metadata
    that the pipeline injects but the base Pattern catalogue-validator rejects.
    """

    analysis_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Requirements-aware score from two-stage analyze (0-100)",
    )
    fusion_score: float | None = Field(
        default=None,
        ge=0,
        description="Stage-1 hybrid fusion score (RRF, from recall)",
    )
    fusion_score_normalized: float | None = Field(
        default=None, ge=0, le=100,
        description="Stage-1 fusion score min-max-normalized to 0-100 within the recall set",
    )
    blended_score: float | None = Field(
        default=None, ge=0, le=100,
        description="Convex blend of analysis_score and fusion_score_normalized (selection key)",
    )
