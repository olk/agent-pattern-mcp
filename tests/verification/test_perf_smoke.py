# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT

"""
L10 performance smoke canary over the decision modules (testing-strategies
§3.10; verification.md perf-smoke amendment).

Rationale (AxDafny lesson): proofs guarantee functional correctness, NOT
performance — a refactor of the decision logic cannot be allowed to silently
regress latency. Budgets are deliberately coarse (regression canary, not a
benchmark): orders-of-magnitude headroom, generous multipliers over the
observed baseline so CI noise never trips them.

Skipped unless RUN_PERF=1 (the perf marker's opt-in contract). Nightly TCB
canary job runs it (see .github/workflows/verification.yml).
"""

import os
import time
from collections.abc import Callable

import pytest

from src.design_normalization import denormalize_contracts
from src.schemas import AgentSystemDesign
from src.text_validation import ensure_printable_text

ITERATIONS = 2_000
# Coarse budgets (seconds for ITERATIONS ops): >= 50x observed headroom.
BUDGET_TEXT_VALIDATION = 2.0
BUDGET_NORMALIZATION = 4.0


def _time_budgeted(name: str, fn: Callable[[], object], budget_s: float) -> None:
    start = time.perf_counter()
    for _ in range(ITERATIONS):
        fn()
    elapsed = time.perf_counter() - start
    assert elapsed < budget_s, (
        f"{name}: {elapsed:.2f}s for {ITERATIONS} ops exceeds canary budget "
        f"{budget_s}s — verified-core latency regressed; triage the refactor"
    )


@pytest.mark.perf
@pytest.mark.skipif(not os.getenv("RUN_PERF", ""), reason="RUN_PERF=1 perf canary")
class TestDecisionModulePerfSmoke:
    def test_text_validation(self) -> None:
        _time_budgeted(
            "text_validation.ensure_printable_text",
            lambda: ensure_printable_text("  design a scalable agent  ", field="value"),
            BUDGET_TEXT_VALIDATION,
        )

    def test_design_normalization(self) -> None:
        design = _sample_design()
        _time_budgeted(
            "design_normalization.denormalize_contracts",
            lambda: denormalize_contracts(design),
            BUDGET_NORMALIZATION,
        )


def _sample_design() -> AgentSystemDesign:
    from src.schemas import (
        Agent,
        AgentSystemOverview,
        AgentSystemDesign,
    )
    from src.schemas.contracts import MessageContract, StateModel, ToolContract
    from src.schemas.enums import AgentTopology, PatternCategory

    return AgentSystemDesign(
        overview=AgentSystemOverview(
            topology=AgentTopology.HIERARCHICAL,
            category=PatternCategory.MULTI_AGENT,
            principles=["single responsibility"],
        ),
        agents=[
            Agent(
                id="planner",
                name="Planner",
                role="planner",
                description="A planner",
                responsibilities=["plan"],
            )
        ],
        relationships=[],
        quality_attributes={},
        tool_contracts=[
            ToolContract(tool_name="web_search", agent_id="planner")
        ],
        shared_state_models=[
            StateModel(name="shared-state", fields=[], is_shared=True)
        ],
        message_contracts=[
            MessageContract(message_name="task.assigned", payload_schema={}, published_by="planner")
        ],
    )
