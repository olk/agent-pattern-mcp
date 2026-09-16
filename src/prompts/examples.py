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

"""Hand-crafted few-shot examples for agent pattern pipeline prompts.

These examples are instantiated at import time to catch schema drift.
If a schema changes, importing this module raises ValidationError immediately.

Each example is rendered as a labelled JSON block via ``_fmt`` so it can be
embedded directly in LLM system prompts.
"""

from pydantic import BaseModel

from src.schemas import (
    AgentSystemDesign,
    AgentSystemDesignResponse,
    AgentSystemEvaluation,
    AgentSystemOverviewWire,
    AgentTopology,
    PatternCategory,
)
from src.schemas.analysis import AnalysisResult
from src.schemas.patterns import PatternQualityAttributes, ScoredPattern
from src.schemas.quality import QualityMetrics


def _fmt(label: str, obj: BaseModel) -> str:
    """Render any Pydantic model as 'label + ```json block'."""
    return f"**{label}:**\n```json\n{obj.model_dump_json(indent=2)}\n```"


# ──────────────────────────────────────────────────────────────────────────────
# AGENT_SYSTEM_DESIGN_EXAMPLE
# ──────────────────────────────────────────────────────────────────────────────

AGENT_SYSTEM_DESIGN_EXAMPLE = _fmt(
    "Example AgentSystemDesign response",
    AgentSystemDesignResponse(
        overview=AgentSystemOverviewWire(
            reasoning=(
                "The requirements specify a multi-step task pipeline where each step "
                "requires specialized tooling (web search, code execution). A hierarchical "
                "topology best fits: a supervisor decomposes user requests into sub-tasks, "
                "delegates to specialized workers, and aggregates results. Workers are "
                "kept stateless and communicate only via the supervisor to avoid shared "
                "mutable state. Trade-off accepted: the supervisor is a potential bottleneck "
                "but acceptable for this task complexity."
            ),
            topology=AgentTopology.HIERARCHICAL,
            category=PatternCategory.MULTI_AGENT,
            principles=[
                "Single responsibility: each agent has a clear, focused role",
                "Hierarchical delegation: supervisor decomposes tasks and routes to specialists",
                "Explicit contracts: tool use and message passing are formally defined",
            ],
            constraints=[
                "Must not make unbounded tool calls without supervisor approval for high-stakes actions",
                "Workers cannot modify shared state directly — only via message contracts",
            ],
            score=8.2,
        ),
        agents=[
            {
                "id": "supervisor",
                "name": "Task Supervisor",
                "role": "planner",
                "description": "Decomposes user requests into sub-tasks and delegates to appropriate workers",
                "responsibilities": [
                    "Parse user intent and extract task parameters",
                    "Route sub-tasks to specialized workers",
                    "Aggregate worker results into coherent response",
                ],
                "llm_role": "planning",
                "tools": ["task_router"],
                "memory": ["context_window"],
                "prompt_strategy": ["chain-of-thought decomposition"],
                "technology_stack": ["LiteLLM/gpt-4o-mini"],
                "config_requirements": ["temperature=0.3 for deterministic routing"],
            },
            {
                "id": "web-search-worker",
                "name": "Web Search Worker",
                "role": "retriever",
                "description": "Performs web searches and returns structured results",
                "responsibilities": [
                    "Execute web searches with query reformulation",
                    "Filter and rank results by relevance",
                    "Return structured JSON with titles, URLs, and snippets",
                ],
                "llm_role": "generation",
                "tools": ["web_search", "url_fetcher"],
                "memory": [],
                "technology_stack": ["LiteLLM/gpt-4o-mini", "SerpAPI"],
                "config_requirements": ["temperature=0.2 for factual retrieval"],
            },
            {
                "id": "code-executor-worker",
                "name": "Code Executor Worker",
                "role": "executor",
                "description": "Writes, executes, and validates code in a sandboxed environment",
                "responsibilities": [
                    "Generate code from natural language task descriptions",
                    "Execute code in sandbox and capture output",
                    "Validate output correctness against test cases",
                ],
                "llm_role": "generation",
                "tools": ["code_runner", "test_runner"],
                "memory": [],
                "technology_stack": ["LiteLLM/gpt-4o", "Docker sandbox"],
                "config_requirements": ["timeout=30s per execution"],
            },
        ],
        relationships=[
            {
                "source": "supervisor",
                "target": "web-search-worker",
                "type": "delegates",
                "description": "Supervisor sends search sub-tasks and receives structured search results",
            },
            {
                "source": "supervisor",
                "target": "code-executor-worker",
                "type": "delegates",
                "description": "Supervisor sends code execution sub-tasks and receives results",
            },
            {
                "source": "web-search-worker",
                "target": "supervisor",
                "type": "feeds",
                "description": "Worker returns search results to supervisor for aggregation",
            },
            {
                "source": "code-executor-worker",
                "target": "supervisor",
                "type": "feeds",
                "description": "Worker returns execution results to supervisor for aggregation",
            },
        ],
        quality_attributes={
            "reliability": 8.5,
            "cost_efficiency": 7.0,
            "latency": 6.0,
            "output_quality": 8.5,
            "observability": 9.0,
            "safety": 8.0,
        },
        tool_contracts=[
            {
                "tool_name": "web_search",
                "agent_id": "web-search-worker",
                "description": "Search the web for information",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
                "output_schema": {"type": "object"},
                "auth_required": False,
            },
            {
                "tool_name": "code_runner",
                "agent_id": "code-executor-worker",
                "description": "Execute Python code in sandbox",
                "input_schema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}}},
                "output_schema": {"type": "object"},
                "auth_required": True,
            },
        ],
        shared_state_models=[
            {
                "name": "TaskPlan",
                "fields": [
                    {"name": "task_id", "type": "string", "required": True},
                    {"name": "sub_tasks", "type": "list", "required": True},
                    {"name": "status", "type": "string", "required": True},
                ],
                "description": "Shared task decomposition plan visible to supervisor and workers",
                "is_shared": True,
            },
        ],
        message_contracts=[
            {
                "message_name": "task.assigned",
                "payload_schema": {"type": "object"},
                "published_by": "supervisor",
                "consumed_by": ["web-search-worker", "code-executor-worker"],
                "description": "Notifies a worker of a new sub-task assignment",
            },
            {
                "message_name": "result.ready",
                "payload_schema": {"type": "object"},
                "published_by": "web-search-worker",
                "consumed_by": ["supervisor"],
                "description": "Returns search results to supervisor",
            },
        ],
    ),
)


# ──────────────────────────────────────────────────────────────────────────────
# AGENT_SYSTEM_EVALUATION_EXAMPLE
# ──────────────────────────────────────────────────────────────────────────────

_evaluation = AgentSystemEvaluation.model_validate({
    "summary": {
        "reasoning": (
            "The hierarchical supervisor-worker topology matches the requirement for "
            "specialized tooling. The clear role separation and explicit tool contracts "
            "address the multi-step task pipeline requirement. Supervisor aggregation "
            "ensures coherent outputs. Key trade-off accepted: the supervisor is a "
            "single point of failure, which is acceptable given the task complexity. "
            "Anti-pattern identified: no checkpoint/resumption creates risk for long tasks."
        ),
        "overall_score": 82.0,
        "strengths": [
            "Clear role separation between supervisor and workers reduces confusion",
            "Explicit tool contracts prevent unauthorized tool use",
            "Shared TaskPlan state ensures all agents work from the same task decomposition",
            "Observability is high: decision log captures every delegation and result",
        ],
        "weaknesses": [
            "Supervisor is a single point of failure — if it crashes, the whole task is lost",
            "No checkpoint/resumption mechanism for long-running tasks",
            "Workers are stateless between messages — no episodic memory of prior attempts",
        ],
        "critical_findings": [
            "No human-in-the-loop for high-stakes tool calls (e.g., code execution with auth_required=True)",
            "No step budget on workers — a malicious prompt could trigger infinite loops",
        ],
    },
    "metrics": [
        {
            "name": "reliability",
            "score": 78,
            "description": "Reliability of the supervisor-worker topology under failure conditions",
            "findings": [
                "Supervisor single point of failure reduces reliability score",
                "Workers can fail independently without cascading to supervisor",
            ],
            "recommendations": [
                "Add checkpoint/resumption for supervisor state",
                "Consider adding a secondary supervisor for critical tasks",
            ],
        },
        {
            "name": "cost_efficiency",
            "score": 75,
            "description": "Cost per task given the LLM calls required",
            "findings": [
                "Supervisor makes one planning call per task",
                "Workers each make one generation call per sub-task",
            ],
            "recommendations": [
                "Cache common sub-task results to reduce LLM calls",
                "Consider prompt caching for repeated task patterns",
            ],
        },
        {
            "name": "latency",
            "score": 70,
            "description": "End-to-end latency from user request to final response",
            "findings": [
                "Sequential delegation adds one round-trip per worker",
                "Workers can process in parallel if supervisor sends concurrently",
            ],
            "recommendations": [
                "Enable concurrent task delegation to workers",
                "Use streaming responses for long-running tasks",
            ],
        },
        {
            "name": "output_quality",
            "score": 88,
            "description": "Quality of the final aggregated response",
            "findings": [
                "Supervisor aggregation improves coherence",
                "Specialized workers produce higher quality outputs than generalists",
            ],
            "recommendations": [
                "Add a critic agent to evaluate worker outputs before aggregation",
            ],
        },
        {
            "name": "observability",
            "score": 92,
            "description": "Ease of debugging and auditing agent decisions",
            "findings": [
                "Explicit message contracts make the data flow traceable",
                "Decision log pattern captures reasoning trace",
            ],
            "recommendations": [
                "Emit structured trace events for each message and tool call",
            ],
        },
        {
            "name": "safety",
            "score": 72,
            "description": "Safety controls around tool use and resource consumption",
            "findings": [
                "No human-in-the-loop for high-stakes actions",
                "No step budget prevents runaway loops",
            ],
            "recommendations": [
                "Add human-in-the-loop approval for auth_required tools",
                "Implement step budgets per worker",
            ],
        },
    ],
    "risks": [
        {
            "risk": "Supervisor crash loses in-flight task state",
            "severity": "high",
            "mitigation": "Add checkpoint/resumption or run supervisor in a durable execution environment",
        },
        {
            "risk": "Infinite delegation loop from circular task dependencies",
            "severity": "medium",
            "mitigation": "Add max delegation depth guard and step budgets",
        },
    ],
    "compliance": [],
    "recommendations": {
        "short_term": [
            "Add step budgets to workers",
            "Add human-in-the-loop for tools with auth_required=True",
        ],
        "long_term": [
            "Implement agent resumption pattern for supervisor state durability",
            "Add episodic memory to workers for cross-task learning",
        ],
    },
})

AGENT_SYSTEM_EVALUATION_EXAMPLE = _fmt("Example AgentSystemEvaluation", _evaluation)


# ──────────────────────────────────────────────────────────────────────────────
# PATTERN_ANALYSIS_EXAMPLE
# ──────────────────────────────────────────────────────────────────────────────

_qa = PatternQualityAttributes(
    reliability=8.0, cost_efficiency=7.0, latency=6.0,
    output_quality=8.5, observability=9.0, safety=8.0, simplicity=7.0,
)
_sp = ScoredPattern(
    topology=AgentTopology.HIERARCHICAL,
    category=PatternCategory.MULTI_AGENT,
    name="supervisor-worker",
    context="Complex tasks requiring specialized sub-agents with a central coordinator",
    benefits=[
        "Clear separation of concerns via dedicated supervisor",
        "Scalability through parallel worker agents",
        "Observability: decision log captures every delegation and result",
    ],
    tradeoffs=[
        "Supervisor is a single point of failure",
        "Additional latency from delegation round-trips",
        "Complexity in handling partial failures",
    ],
    quality_attributes=_qa,
    suitable_domains=[],
    unsuitable_domains=[],
    use_cases=["Multi-step reasoning tasks", "Research synthesis"],
    avoid_when=["Simple single-step tasks where overhead is excessive"],
    component_types=["supervisor", "worker"],
    technology_stack=["LiteLLM/gpt-4o-mini", "SerpAPI"],
    anti_patterns=["Monolithic agent with no supervision"],
    migration_from=["single-agent-loop"],
    migration_to=[],
    design_principles=["Delegation over direct execution"],
    best_practices=["Use decision logs for traceability"],
    analysis_score=82.5,
    fusion_score=0.91,
    fusion_score_normalized=91.0,
    blended_score=85.75,
)
_analysis = AnalysisResult(
    strengths=[
        "Hierarchical structure provides clear role separation",
        "Explicit tool contracts prevent unauthorized tool use",
        "Decision log enables full traceability of agent reasoning",
    ],
    weaknesses=[
        "Supervisor is a single point of failure",
        "No checkpoint/resumption mechanism for long-running tasks",
        "Workers are stateless between messages",
    ],
    recommendations=[
        "Add a secondary supervisor for critical paths",
        "Implement step budgets per worker to prevent runaway loops",
        "Consider a checkpoint/resumption mechanism for long-running tasks",
    ],
    quality_metrics=QualityMetrics(
        reliability=8.0, cost_efficiency=7.0, latency=6.0,
        output_quality=8.5, observability=9.0, safety=8.0,
    ),
    recommended_topology="hierarchical",
    selected_patterns=[_sp],
    rationale="The hierarchical supervisor-worker pattern best balances the requirements for specialized sub-agents with centralized coordination, providing both scalability and observability.",
)

PATTERN_ANALYSIS_EXAMPLE = _fmt("Example AnalysisResult", _analysis)


# ──────────────────────────────────────────────────────────────────────────────
# REQUIREMENT_WEIGHTS_EXAMPLE
# ──────────────────────────────────────────────────────────────────────────────

from src.schemas.analysis import RequirementWeights

_REQUIREMENT_WEIGHTS = RequirementWeights(
    reliability=0.8,
    cost_efficiency=0.6,
    latency=0.9,
    output_quality=1.0,
    observability=0.3,
    safety=0.5,
    simplicity=0.4,
)

REQUIREMENT_WEIGHTS_EXAMPLE = _fmt("Example RequirementWeights", _REQUIREMENT_WEIGHTS)

# ──────────────────────────────────────────────────────────────────────────────
# REQUIREMENT_WEIGHTS calibration examples (fe68250 lineage)
# ──────────────────────────────────────────────────────────────────────────────
# Rendered WITHOUT markdown fences inside the ANALYZE system prompt: the model
# must not echo fences into its structured output. Each example peaks at
# exactly 1.0 to mirror the normalisation hard constraint in the prompt.

# Peaked priorities. Requirements excerpt: "High-volume customer-support
# automation platform: 1M conversations/day, 99.99% uptime, regulated health
# data (HIPAA), p95 first-token latency < 500ms."
REQUIREMENT_WEIGHTS_EXAMPLE_PEAKED = RequirementWeights(
    reliability=0.9,
    cost_efficiency=0.3,
    latency=1.0,
    output_quality=0.7,
    observability=0.4,
    safety=0.9,
    simplicity=0.3,
)

# Sparse, low-signal requirements: max still normalised to 1.0; unmentioned
# attributes sit at the 0.1-0.2 implicit baseline. Requirements excerpt:
# "Small internal FAQ lookup agent for our team."
REQUIREMENT_WEIGHTS_EXAMPLE_SPARSE = RequirementWeights(
    reliability=0.2,
    cost_efficiency=0.3,
    latency=0.2,
    output_quality=0.3,
    observability=0.2,
    safety=0.2,
    simplicity=1.0,
)

# Explicit anti-requirement: 0.0 only for explicitly excluded attributes.
# Requirements excerpt: "Fully local, deterministic rule-based router agent.
# Explicitly no external API calls and no learning loop; single-user desktop
# deployment."
REQUIREMENT_WEIGHTS_EXAMPLE_NEGATIVE = RequirementWeights(
    reliability=0.3,
    cost_efficiency=0.0,
    latency=0.3,
    output_quality=0.4,
    observability=0.3,
    safety=0.3,
    simplicity=1.0,
)

# Conflict resolution: a concrete numeric SLO wins over a vague adjective.
# Requirements excerpt: "Customer-support automation handling 1M
# conversations/day with horizontal scale-out, p95 first-token latency
# < 500ms. Small startup team of 4 engineers; ship MVP in 3 months."
# Rationale: latency carries hard numeric signals ("1M conversations/day",
# "p95 < 500ms"); simplicity carries only vague signals ("small team",
# "ship in 3 months"). Per the conflict rule, the concrete signal dominates:
# latency peaks at 1.0 and simplicity drops to the baseline despite being
# mentioned. The design phase reconciles the tension — the weights must not
# blur it.
REQUIREMENT_WEIGHTS_EXAMPLE_CONFLICT = RequirementWeights(
    reliability=0.3,
    cost_efficiency=0.2,
    latency=1.0,
    output_quality=0.7,
    observability=0.2,
    safety=0.2,
    simplicity=0.2,
)
