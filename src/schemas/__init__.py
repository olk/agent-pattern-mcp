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
Schema package — Pydantic v2 models for MCP agent pattern system.

Exports all typed schemas for FastMCP tool I/O boundaries and validation.

Modules:
- enums: PatternCategory, AgentDomain, AgentTopology
- quality: QualityMetrics
- contracts: StateField, StateModel, ToolContract, MessageContract
- components: Agent, Relationship
- evaluation: MetricResult, EvaluationSummary, AgentSystemEvaluation, PipelineResult
- patterns: Pattern, ScoredPattern, PatternQualityAttributes
- design: AgentSystemOverview, AgentSystemDesign
- analysis: AnalysisResult, RequirementWeights, QUALITY_ATTRIBUTE_KEYS
- agent_system: AgentSystemOverviewWire (LLM-facing overview, reasoning required)
               AgentSystemDesignResponse (LLM wire schema — dict-based, lax validation)
               AgentSystemDesignResponseWire (lean wire schema for generation)
"""

from src.schemas.analysis import (
    QUALITY_ATTRIBUTE_KEYS,
    AnalysisResult,
    RequirementWeights,
)
from src.schemas.agent_system import (
    AgentSystemDesignResponse,
    AgentSystemDesignResponseWire,
    AgentSystemOverviewWire,
)
from src.schemas.contracts import (
    MessageContract,
    StateField,
    StateModel,
    ToolContract,
)
from src.schemas.components import Agent, Relationship

from src.schemas.design import AgentSystemDesign, AgentSystemOverview
from src.schemas.enums import (
    AgentDomain,
    AgentTopology,
    PatternCategory,
)
from src.schemas.evaluation import (
    AgentSystemEvaluation,
    EvaluationSummary,
    MetricResult,
    PipelineResult,
)
from src.schemas.patterns import Pattern, PatternQualityAttributes, ScoredPattern
from src.schemas.quality import QualityMetrics

__all__ = [
    # enums
    "AgentDomain",
    "AgentTopology",
    "PatternCategory",
    # quality
    "QualityMetrics",
    # contracts
    "MessageContract",
    "StateField",
    "StateModel",
    "ToolContract",
    # components
    "Agent",
    "Relationship",
    # evaluation
    "AgentSystemEvaluation",
    "EvaluationSummary",
    "MetricResult",
    "PipelineResult",
    # patterns
    "Pattern",
    "PatternQualityAttributes",
    # design
    "AgentSystemDesign",
    "AgentSystemOverview",
    "AgentSystemOverviewWire",
    "ScoredPattern",
    # analysis
    "AnalysisResult",
    "RequirementWeights",
    "QUALITY_ATTRIBUTE_KEYS",
    # agent_system (LLM wire schema)
    "AgentSystemDesignResponse",
    "AgentSystemDesignResponseWire",
]
