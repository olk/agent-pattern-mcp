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
Schema enumerations for MCP agent pattern system.

This module defines enumerations used across the pattern pipeline including
PatternCategory for classifying agent patterns, AgentDomain for pattern
suitability filtering, and AgentTopology for agent system topology names.
"""

from enum import Enum


# FR-19: The system SHALL support pattern categories: reasoning, tool_use, planning,
# reflection, research_synthesis, multi_agent, memory, retrieval, safety_control, observability
class PatternCategory(str, Enum):
    """
    Enumeration of agent pattern categories.

    This enum categorizes agent patterns for filtering and selection
    during the pipeline workflow. Uses str mixin for JSON serialization compatibility.

    Categories:
    - REASONING: Patterns for reasoning and inference
    - TOOL_USE: Patterns for tool usage and function calling
    - PLANNING: Patterns for task planning and decomposition
    - REFLECTION: Patterns for self-reflection and critique
    - RESEARCH_SYNTHESIS: Patterns for research and synthesis
    - MULTI_AGENT: Patterns for multi-agent coordination
    - MEMORY: Patterns for memory and state management
    - RETRIEVAL: Patterns for retrieval-augmented generation
    - SAFETY_CONTROL: Patterns for safety and control
    - OBSERVABILITY: Patterns for observability and monitoring
    """

    REASONING = "reasoning"
    TOOL_USE = "tool_use"
    PLANNING = "planning"
    REFLECTION = "reflection"
    RESEARCH_SYNTHESIS = "research_synthesis"
    MULTI_AGENT = "multi_agent"
    MEMORY = "memory"
    RETRIEVAL = "retrieval"
    SAFETY_CONTROL = "safety_control"
    OBSERVABILITY = "observability"


# AgentDomain: problem-space domain values for pattern suitability filtering.
# Used by Pattern.suitable_domains, Pattern.unsuitable_domains, DomainVectorIndex, DomainBM25Index.
class AgentDomain(str, Enum):
    """
    Enumeration of problem-space agent domains for pattern suitability filtering.

    This enum defines all valid domain values for Pattern.suitable_domains and
    Pattern.unsuitable_domains fields in pattern JSON files. It is also the source
    corpus for DomainVectorIndex (FAISS) and DomainBM25Index in the hybrid retriever.

    Values are hyphenated-lowercase problem-space descriptors.

    36 values total: 31 functional/problem-space domains (what the agent DOES
    or which vertical it serves) and 5 constraint-style domains that act as
    suitability filters rather than task descriptions (regulated-domains,
    high-stakes-outputs, cost-sensitive-workloads, latency-sensitive-tasks,
    long-horizon-tasks). Every enum value MUST appear in at least one pattern's
    suitable_domains — enforced by
    tests/unit/test_catalog.py::test_every_domain_has_at_least_one_pattern.

    Note on research-flavored domains: exploratory-research = open-ended goal
    formulation; research-reports = structured multi-source report generation;
    scientific-research = formal scientific method (hypothesis, experiment,
    literature replication); document-processing = PDF/DOCX/HTML ingestion and
    structured extraction over large document corpora.
    """

    API_AUTOMATION = "api-automation"
    AUTONOMOUS_TASK_EXECUTION = "autonomous-task-execution"
    CODE_GENERATION = "code-generation"
    COMPLEX_REASONING = "complex-reasoning"
    CONTENT_GENERATION = "content-generation"
    CONVERSATIONAL_ASSISTANTS = "conversational-assistants"
    COST_SENSITIVE_WORKLOADS = "cost-sensitive-workloads"
    CUSTOMER_SUPPORT = "customer-support"
    CYBERSECURITY = "cybersecurity"
    DATA_ANALYSIS = "data-analysis"
    DATABASE_OPERATIONS = "database-operations"
    DEVOPS = "devops"
    DOCUMENT_PROCESSING = "document-processing"
    ECOMMERCE = "e-commerce"
    EDUCATION = "education"
    ENTERPRISE_SEARCH = "enterprise-search"
    EXPLORATORY_RESEARCH = "exploratory-research"
    GUI_COMPUTER_USE = "gui-computer-use"
    HIGH_STAKES_OUTPUTS = "high-stakes-outputs"
    IT_SERVICE_MANAGEMENT = "it-service-management"
    LATENCY_SENSITIVE_TASKS = "latency-sensitive-tasks"
    LEGAL_RESEARCH = "legal-research"
    LONG_HORIZON_TASKS = "long-horizon-tasks"
    MULTI_AGENT_SYSTEMS = "multi-agent-systems"
    MULTIMODAL = "multimodal"
    PARALLEL_DATA_GATHERING = "parallel-data-gathering"
    PERSONAL_PRODUCTIVITY = "personal-productivity"
    RAG_APPLICATIONS = "rag-applications"
    REGULATED_DOMAINS = "regulated-domains"
    RESEARCH_REPORTS = "research-reports"
    SCIENTIFIC_RESEARCH = "scientific-research"
    SOFTWARE_TESTING = "software-testing"
    TOOL_USE_TASKS = "tool-use-tasks"
    TRIAL_AND_ERROR_LEARNING = "trial-and-error-learning"
    WEB_AUTOMATION = "web-automation"
    WORKFLOW_AUTOMATION = "workflow-automation"


# AgentTopology: canonical agent system topology names from pattern JSON files.
# Used as Pattern.topology and AgentSystemOverview.topology values.
class AgentTopology(str, Enum):
    """
    Enumeration of canonical agent system topology names from pattern JSON files.

    This enum defines the canonical topology names used as the topology
    field in pattern JSON files and as the AgentSystemOverview.topology value.
    Values match Pattern.topology exactly — sourced from pattern/*.json files.
    """

    EVALUATOR_LOOP = "evaluator-loop"
    GRAPH_ORCHESTRATED = "graph-orchestrated"
    HIERARCHICAL = "hierarchical"
    PARALLEL_FAN_OUT = "parallel-fan-out"
    PIPELINE = "pipeline"
    PLAN_EXECUTE = "plan-execute"
    SINGLE_AGENT_LOOP = "single-agent-loop"
    SWARM = "swarm"


_VALID_TOPOLOGY_VALUES: frozenset[str] = frozenset(t.value for t in AgentTopology)


def validate_topology_value(value: str) -> str:
    """Return ``value`` unchanged when it is a canonical AgentTopology value.

    Raises ValueError otherwise.  Used at tool boundaries so that user-supplied
    topology strings (override_topology, generate-phase topology) cannot enter
    the pipeline and silently degrade topology-specific prompt guidance to the
    generic fallback.
    """
    if value not in _VALID_TOPOLOGY_VALUES:
        raise ValueError(
            f"Unknown agent topology '{value}'; must be one of: "
            f"{', '.join(sorted(_VALID_TOPOLOGY_VALUES))}"
        )
    return value
