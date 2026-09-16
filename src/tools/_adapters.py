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
Tool adapters — converts internal pipeline dataclasses to typed Pydantic models.

Used at the FastMCP tool boundary to produce validated typed output.
All conversions use Pydantic lax mode (the default) to handle LLM-friendly coercion.

Pipeline dataclasses (internal, unchanged):
    AnalysisResult, AgentSystemDesign, AgentSystemEvaluation, RefinedArchitecture

Typed Pydantic models (FastMCP I/O boundary):
    AnalyzeAgentSystemOutput, GenerateAgentSystemOutput, EvaluateAgentSystemOutput,
    DesignAgentSystemOutput, plus the shared schema types they reference.

Validation contract:
    Adapter helpers raise MalformedAgentSystemOverviewError (ERR_012) when
    input data fails strict Pydantic validation.  Tool handlers map that to
    ToolError so the MCP client can retry with corrected input.
    No silent placeholder synthesis occurs at the adapter boundary.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from src.errors import MalformedAgentSystemOverviewError

if TYPE_CHECKING:
    from src.pipeline import (
        AnalysisResult as AnalysisResultDC,
    )

from src.schemas import (
    AgentSystemDesign,
    AgentSystemOverview,
    Agent,
    StateModel,
    MessageContract,
    Relationship,
)
from src.schemas.analysis import AnalysisResult, MatchedDomain
from src.schemas.patterns import ScoredPattern
from src.schemas.contracts import ToolContract

logger = logging.getLogger(__name__)


def _lint_convert[T: BaseModel](klass: type[T], data: dict[str, Any]) -> T:
    """Coerce a dict to a typed Pydantic model using lax validation."""
    return klass.model_validate(data)


def _safe_preview(data: dict[str, Any], max_len: int = 200) -> dict[str, Any]:
    """Return a redacted preview of untrusted input for logging."""
    preview: dict[str, Any] = {}
    for k, v in list(data.items())[:10]:
        if isinstance(v, str) and len(v) > max_len:
            preview[k] = v[:max_len] + "..."
        else:
            preview[k] = v
    return preview


# ─── AnalysisResult ───────────────────────────────────────────────────────────


def analysis_to_pydantic(dc: AnalysisResultDC) -> AnalysisResult:
    """
    Convert pipeline AnalysisResult dataclass to typed AnalysisResult Pydantic model.

    Handles:
    - quality_metrics: passed through directly (pipeline and boundary share the
      same typed QualityMetrics model)
    - selected_patterns: list[dict] → list[ScoredPattern] (preserves analysis_score
      and fusion_score metadata injected by the two-stage analyze phase)
    - matched_domains: list[dict] → list[MatchedDomain] (slug, fusion score and
      optional cross-encoder rerank logit per matched AgentDomain slug)
    - All other fields passed through directly (names match between DC and Pydantic)
    """
    qm = dc.quality_metrics

    patterns: list[ScoredPattern] = []
    for p in dc.selected_patterns:
        if isinstance(p, ScoredPattern):
            patterns.append(p)
        elif hasattr(p, "model_dump"):
            patterns.append(ScoredPattern.model_validate(p.model_dump()))
        elif isinstance(p, dict):
            patterns.append(_lint_convert(ScoredPattern, p))

    matched_domains = [
        MatchedDomain(
            slug=d["slug"],
            fusion_score=d["fusion_score"],
            rerank_score=d.get("rerank_score"),
        )
        for d in dc.matched_domains
    ]

    result = AnalysisResult(
        strengths=list(dc.strengths),
        weaknesses=list(dc.weaknesses),
        recommendations=list(dc.recommendations),
        quality_metrics=qm,
        recommended_topology=dc.recommended_topology,
        recommended_pattern_name=dc.recommended_pattern_name,
        selected_patterns=patterns,
        matched_domains=matched_domains,
        is_fallback=bool(dc.is_fallback),
    )
    if result.is_fallback:
        logger.warning(
            "Analysis fell back to the default pattern '%s' — no domain-matched "
            "candidate passed retrieval or the relevance floor; surfacing "
            "is_fallback=true to the MCP caller",
            result.recommended_topology,
            extra={"recommended_topology": result.recommended_topology},
        )
    return result


# ─── AgentSystemDesign ───────────────────────────────────────────────────────


def _parse_tool_contract(data: dict[str, Any]) -> ToolContract:
    """Parse a top-level tool_contracts entry into a ToolContract."""
    return ToolContract(
        tool_name=data.get("tool_name", ""),
        agent_id=data.get("agent_id", ""),
        description=data.get("description", ""),
        input_schema=data.get("input_schema"),
        output_schema=data.get("output_schema"),
        auth_required=data.get("auth_required", False),
    )


def design_from_dict(data: dict[str, Any]) -> AgentSystemDesign:
    """
    Convert a raw dict (from API/MCP input) to typed AgentSystemDesign Pydantic model.

    This is the entry point for tool input that arrives as unstructured dicts
    before being passed to the pipeline layer.

    Raises MalformedAgentSystemOverviewError (ERR_012) when the overview
    fails validation, or when the payload is not a JSON object at all
    (non-dict payloads previously escaped as raw AttributeError — found by
    the L1b boundary oracle; tests/verification/test_boundary_fuzz.py).
    """
    if not isinstance(data, dict):
        raise MalformedAgentSystemOverviewError(
            locator="payload",
            errors=[
                {
                    "type": "model_type",
                    "loc": ("payload",),
                    "msg": (
                        "Input must be a JSON object with an 'overview' key, "
                        f"got {type(data).__name__}"
                    ),
                }
            ],
        )
    agents = [_parse_agent(c) for c in data.get("agents", [])]
    relationships = [_parse_relationship(r) for r in data.get("relationships", [])]
    message_contracts = [_parse_message_contract(e) for e in data.get("message_contracts", [])]

    try:
        return AgentSystemDesign(
            overview=_parse_overview(data.get("overview", {})),
            agents=agents,
            relationships=relationships,
            quality_attributes=dict(data.get("quality_attributes", {})),
            tool_contracts=[_parse_tool_contract(c) for c in data.get("tool_contracts", [])],
            shared_state_models=[_lint_convert(StateModel, d) for d in data.get("shared_state_models", [])],
            message_contracts=message_contracts,
        )
    except ValidationError as exc:
        first_loc = exc.errors()[0]["loc"]
        if first_loc and first_loc[0] == "overview":
            locator = "overview"
        else:
            locator = str(first_loc[0]) if first_loc else "design"
        logger.warning(
            "Malformed agent system design: %s",
            exc.errors(include_url=False),
            extra={"payload_preview": _safe_preview(data)},
        )
        raise MalformedAgentSystemOverviewError(
            locator=locator,
            errors=exc.errors(),
        ) from exc


def _parse_overview(data: dict[str, Any]) -> AgentSystemOverview:
    """
    Validate and convert a raw overview dict to AgentSystemOverview.

    Raises MalformedAgentSystemOverviewError (ERR_012) when required fields
    (style, category, principles[min_length=1]) fail Pydantic validation.
    No silent fallback is synthesised — the caller (tool handler) propagates
    the error to the MCP client.
    """
    try:
        return AgentSystemOverview.model_validate(data)
    except ValidationError as exc:
        logger.warning(
            "Malformed agent system overview: %s",
            exc.errors(include_url=False),
            extra={"payload_preview": _safe_preview(data)},
        )
        raise MalformedAgentSystemOverviewError(
            locator="overview",
            errors=exc.errors(),
        ) from exc


def _parse_agent(data: dict[str, Any]) -> Agent:
    if isinstance(data, Agent):
        return data

    description = data.get("description", "")
    if not description:
        description = data.get("name", "Agent")
    responsibilities = list(data.get("responsibilities", []))
    if not responsibilities:
        responsibilities = [f"Handle {data.get('name', 'agent')} responsibilities"]

    return Agent(
        id=data.get("id", ""),
        name=data.get("name", ""),
        role=data.get("role", "executor"),
        description=description,
        responsibilities=responsibilities,
        llm_role=data.get("llm_role"),
        tools=list(data.get("tools", [])),
        memory=list(data.get("memory", [])),
        prompt_strategy=data.get("prompt_strategy"),
        technology_stack=list(data.get("technology_stack", [])),
        config_requirements=list(data.get("config_requirements", [])),
    )


def _parse_relationship(data: dict[str, Any]) -> Relationship:
    if isinstance(data, Relationship):
        return data
    return Relationship(
        source=data.get("source", ""),
        target=data.get("target", ""),
        type=data.get("type", ""),
        description=data.get("description", ""),
    )


def _parse_message_contract(data: dict[str, Any]) -> MessageContract:
    if isinstance(data, MessageContract):
        return data
    return MessageContract(
        message_name=(data.get("message_name") or data.get("event_name") or ""),
        payload_schema=data.get("payload_schema", {}),
        published_by=data.get("published_by", ""),
        consumed_by=list(data.get("consumed_by", [])),
        description=data.get("description", ""),
    )


def design_to_pydantic(dc: AgentSystemDesign | dict[str, Any]) -> AgentSystemDesign:
    """
    Convert pipeline AgentSystemDesign to typed AgentSystemDesign Pydantic model.

    If already an AgentSystemDesign, validates and returns.
    If a dict, validates as AgentSystemDesign.
    Uses lax validation — Pydantic coerces compatible types automatically.

    Raises MalformedAgentSystemOverviewError (ERR_012) when the overview
    fails validation.
    """
    if isinstance(dc, dict):
        dc = AgentSystemDesign.model_validate(dc)
    return dc

