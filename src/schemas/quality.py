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

# QualityMetrics Pydantic Model
# FR-17: AgentPatternPipeline uses QualityMetrics for quality assessment
# IC-10: QualityMetrics type SHALL have exactly 6 properties with values in range 0-10

"""
Quality assessment metrics for agent system evaluation.

This model represents quality attributes used to score designs based on
their alignment with user priorities. Used by AgentPatternPipeline for
quality-weighted scoring.
"""

from pydantic import BaseModel, Field


class QualityMetrics(BaseModel):
    """
    Quality assessment metrics for agent system evaluation.

    Attributes:
        reliability: System reliability score (0-10)
        cost_efficiency: Cost efficiency score (0-10)
        latency: Latency performance score (0-10)
        output_quality: Output quality score (0-10)
        observability: Observability score (0-10)
        safety: Safety score (0-10)
    """

    # IC-10: 6 required properties with values in range 0-10
    reliability: float = Field(
        ...,
        description="System reliability",
        ge=0.0,
        le=10.0
    )
    cost_efficiency: float = Field(
        ...,
        description="Cost efficiency",
        ge=0.0,
        le=10.0
    )
    latency: float = Field(
        ...,
        description="Latency performance",
        ge=0.0,
        le=10.0
    )
    output_quality: float = Field(
        ...,
        description="Output quality",
        ge=0.0,
        le=10.0
    )
    observability: float = Field(
        ...,
        description="Observability",
        ge=0.0,
        le=10.0
    )
    safety: float = Field(
        ...,
        description="Safety",
        ge=0.0,
        le=10.0
    )
