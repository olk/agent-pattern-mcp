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

"""GENERATE-phase prompt-quality regression benchmark.

Two execution modes:

Recorded mode (default, offline, CI-safe)
    Validates structurally against golden designs in ``tests/regression/golden/``.
    Fixtures without a golden file are skipped. Assertions:
      1. overview.reasoning is populated (reason-before-commit contract)
      2. cross-reference integrity: every relationship.source/target,
         ToolContract.agent_id, and MessageContract.published_by/consumed_by
         resolves to an existing agent id
      3. requirement traceability: every ``required_capabilities`` keyword of a
         fixture appears in at least one agent's name/description/
         responsibilities
      4. scoring honesty: no quality attribute scored above 9/10
      5. delivered topology matches one of the fixture's expected topologies

Live mode (opt-in; requires a working config.json + LLM endpoint)
    AGENT_BENCH_LLM=1 uv run pytest tests/regression -m llm -v
    Runs the real pipeline per fixture and applies assertions 1-5 plus the
    exact-topology check. Capture goldens for the recorded mode with:
    AGENT_BENCH_LLM=1 AGENT_BENCH_CAPTURE=1 uv run pytest tests/regression -m llm -v

Baseline workflow (plan v2 validation flow):
    1. Capture goldens against the CURRENT code  -> baseline
    2. Apply prompt/schema changes               -> capture again elsewhere
    3. Diff structural assertion results and quality between runs
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).parent / "golden"


# ─── Fixtures ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BenchFixture:
    """One benchmark requirement set.

    ``required_capabilities`` keywords are matched case-insensitively as
    substrings against each agent's name, description, and
    responsibilities — every keyword must land on at least one agent.
    """

    name: str
    domain: str
    primary_pattern: str
    expected_topologies: frozenset[str]
    requirements: str
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)


FIXTURES: tuple[BenchFixture, ...] = (
    BenchFixture(
        name="customer-support-triage",
        domain="customer-support",
        primary_pattern="routing",
        expected_topologies=frozenset({"hierarchical", "parallel-fan-out"}),
        requirements=(
            "Customer-support triage agent: classify incoming tickets, draft "
            "replies with citations from the knowledge base, and escalate "
            "billing disputes to a human reviewer. 50k tickets/day, every "
            "action must be traceable for compliance."
        ),
        required_capabilities=("ticket", "classif", "escalat"),
    ),
    BenchFixture(
        name="deep-research-assistant",
        domain="exploratory-research",
        primary_pattern="plan-and-solve",
        expected_topologies=frozenset({"plan-execute", "hierarchical"}),
        requirements=(
            "Deep-research assistant: decompose an open question, search many "
            "sources in parallel, cross-check contradicting claims, and "
            "produce a cited report with confidence labels. Report quality "
            "outweighs token cost."
        ),
        required_capabilities=("research", "search", "report"),
    ),
    BenchFixture(
        name="code-change-agent",
        domain="code-generation",
        primary_pattern="code-agent",
        expected_topologies=frozenset({"single-agent-loop"}),
        requirements=(
            "Autonomous code-change agent for a monorepo: read an issue, edit "
            "code, run the test suite, and iterate on failures until green or "
            "a step budget is exhausted. Unsafe commands must be blocked."
        ),
        required_capabilities=("test", "edit", "command"),
    ),
    BenchFixture(
        name="grounded-qa-assistant",
        domain="rag-applications",
        primary_pattern="corrective-rag",
        expected_topologies=frozenset({"single-agent-loop", "evaluator-loop"}),
        requirements=(
            "Grounded QA assistant over a large document corpus with "
            "per-answer citations. Retrieved chunks are graded for relevance "
            "and the query is re-issued when insufficient. Hallucinated "
            "answers are unacceptable in this regulated domain."
        ),
        required_capabilities=("retriev", "grade", "citation"),
    ),
    BenchFixture(
        name="critical-decision-agent",
        domain="high-stakes-outputs",
        primary_pattern="tree-of-thoughts",
        expected_topologies=frozenset({"evaluator-loop", "graph-orchestrated"}),
        requirements=(
            "Trading-signal assistant: generate analysis only, every output "
            "passes a compliance check before display, a hard kill-switch "
            "halts all activity on anomalous behavior, and full decision "
            "traces are archived for the auditor."
        ),
        required_capabilities=("compliance", "kill", "trace"),
    ),
    BenchFixture(
        name="long-horizon-task-agent",
        domain="autonomous-task-execution",
        primary_pattern="supervisor-worker",
        expected_topologies=frozenset({"hierarchical", "plan-execute"}),
        requirements=(
            "Long-horizon task agent: a supervisor decomposes a project into "
            "subtasks, stateless workers execute each subtask with isolated "
            "context, and checkpointing lets the run resume after "
            "interruption without losing completed work."
        ),
        required_capabilities=("subtask", "worker", "checkpoint"),
    ),
    BenchFixture(
        name="content-pipeline-agent",
        domain="content-generation",
        primary_pattern="prompt-chaining",
        expected_topologies=frozenset({"pipeline", "parallel-fan-out"}),
        requirements=(
            "Content pipeline agent: outline, draft, fact-check, and polish "
            "articles in a fixed sequence; each stage transforms the previous "
            "stage's output and stores intermediate artifacts so any stage "
            "can be re-run independently."
        ),
        required_capabilities=("draft", "fact", "artifact"),
    ),
    BenchFixture(
        name="resilient-ops-agent",
        domain="devops",
        primary_pattern="self-heal-loop",
        expected_topologies=frozenset({"evaluator-loop", "single-agent-loop"}),
        requirements=(
            "Resilient ops agent: watch service health, diagnose regressions "
            "from logs and metrics, attempt a remediation play, and verify "
            "recovery — retrying with an escalated strategy when the first "
            "remediation fails. Human approval is required for destructive "
            "actions."
        ),
        required_capabilities=("health", "remediat", "approval"),
    ),
)


# ─── Shared assertion helpers ───────────────────────────────────────────────


def _agent_ids(design) -> set[str]:
    return {a.id for a in design.agents}


def _capability_text(design, agent) -> str:
    return " ".join(
        [agent.name, agent.description, *agent.responsibilities]
    ).lower()


def assert_structural_quality(design, fixture: BenchFixture) -> None:
    """Assertions 1-5 (reasoning, cross-refs, traceability, honesty, topology)."""
    # 1. reasoning populated (reason-before-commit contract)
    assert design.overview.reasoning.strip(), "overview.reasoning must be populated"

    ids = _agent_ids(design)
    assert ids, "design must contain agents"

    # 2. cross-reference integrity
    for rel in design.relationships:
        assert rel.source in ids, f"orphan relationship source: {rel.source}"
        assert rel.target in ids, f"orphan relationship target: {rel.target}"
    for tc in design.tool_contracts:
        assert tc.agent_id in ids, f"orphan tool contract: {tc.agent_id}"
    for mc in design.message_contracts:
        assert mc.published_by in ids, f"orphan message publisher: {mc.published_by}"
        for consumer in mc.consumed_by:
            assert consumer in ids, f"orphan message consumer: {consumer}"
    for sm in design.shared_state_models:
        for owner in getattr(sm, "owner_ids", []) or []:
            assert owner in ids, f"orphan state model owner: {owner}"

    # 3. requirement traceability
    for capability in fixture.required_capabilities:
        hits = [
            a for a in design.agents if capability in _capability_text(design, a)
        ]
        assert hits, (
            f"capability '{capability}' traces to no agent "
            f"(capabilities checked: {fixture.required_capabilities})"
        )

    # 4. scoring honesty: nothing above 9/10
    for attr, value in design.quality_attributes.items():
        try:
            score = float(str(value).split("/")[0])
        except ValueError:
            continue
        assert score <= 9.0, f"quality attribute '{attr}' inflated: {value}"

    # 5. topology within expectation
    assert design.overview.topology.value in fixture.expected_topologies, (
        f"topology {design.overview.topology.value!r} not in expected "
        f"{sorted(fixture.expected_topologies)}"
    )


# ─── Recorded mode (offline) ────────────────────────────────────────────────


def _load_golden(fixture: BenchFixture):
    golden_path = GOLDEN_DIR / f"{fixture.name}.json"
    if not golden_path.exists():
        return None
    from src.schemas.design import AgentSystemDesign

    return AgentSystemDesign.model_validate(json.loads(golden_path.read_text()))


@pytest.mark.parametrize(
    "fixture", FIXTURES, ids=lambda f: f.name
)
def test_golden_design_structural_quality(fixture: BenchFixture):
    """Recorded mode: validate a captured golden design structurally."""
    design = _load_golden(fixture)
    if design is None:
        pytest.skip(
            f"no golden for {fixture.name!r} — capture with "
            "AGENT_BENCH_LLM=1 AGENT_BENCH_CAPTURE=1 uv run pytest tests/regression -m llm"
        )
    assert_structural_quality(design, fixture)


def test_golden_coverage_report():
    """Transparency: report how many fixtures currently have goldens."""
    have = [f.name for f in FIXTURES if (GOLDEN_DIR / f"{f.name}.json").exists()]
    missing = [f.name for f in FIXTURES if f.name not in have]
    print(f"\nGolden coverage: {len(have)}/{len(FIXTURES)} (missing: {missing or 'none'})")


# ─── Live mode (opt-in) ─────────────────────────────────────────────────────


def _build_live_pipeline():
    """Build a real AgentPatternPipeline from the deployed config.

    generate() never touches the retrieval legs, so they are left
    unbuilt — no TEI dependency for the GENERATE-only benchmark.
    """
    from src.agent import AgentSystemArchitect
    from src.config import ConfigManager, RetrievalConfig, RerankerConfig, ServerConfig
    from src.patterns.loader import PatternLoader
    from src.pipeline import AgentPatternPipeline

    cfg = ConfigManager.load_config()
    server_cfg = ServerConfig.model_validate(cfg)
    agent = AgentSystemArchitect(server_cfg)
    retrieval = RetrievalConfig(**cfg.get("retrieval", {}))
    reranker = RerankerConfig(**cfg.get("reranker", {}))
    return AgentPatternPipeline(
        agent=agent,
        pattern_loader=PatternLoader(),
        embedder=server_cfg.embedder,
        retrieval_config=retrieval,
        reranker_config=reranker,
    )


def _select_patterns(pipeline, fixture: BenchFixture) -> list[dict]:
    """Select the fixture's primary pattern as generation context."""
    for pattern in pipeline._pattern_loader.load_all():
        if pattern.get("name") == fixture.primary_pattern:
            return [pattern]
    pytest.skip(f"pattern {fixture.primary_pattern!r} not found in pattern directory")


@pytest.mark.llm
@pytest.mark.skipif(
    not os.getenv("AGENT_BENCH_LLM", ""),
    reason="AGENT_BENCH_LLM=1 to run live GENERATE benchmark (requires config + LLM)",
)
@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.name)
def test_live_generate_quality(fixture: BenchFixture):
    """Live mode: run the real GENERATE phase and assert structural quality."""
    capture = bool(os.getenv("AGENT_BENCH_CAPTURE", ""))

    try:
        pipeline = _build_live_pipeline()
    except Exception as exc:  # config missing/invalid → skip, not fail
        pytest.skip(f"cannot build live pipeline: {exc}")

    selected = _select_patterns(pipeline, fixture)

    design = asyncio.run(
        pipeline.generate(
            requirements=fixture.requirements,
            domain=fixture.domain,
            topology=fixture.primary_pattern,
            selected_patterns=selected,
        )
    )

    assert_structural_quality(design, fixture)

    if capture:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        out = GOLDEN_DIR / f"{fixture.name}.json"
        out.write_text(design.model_dump_json(indent=2) + "\n")
        print(f"captured golden: {out}")
