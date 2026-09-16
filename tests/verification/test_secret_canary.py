# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT

"""
L1 secret canary, E4-extended (Week-0 task W0-3; testing-strategies.md §3.2).

Buys the practical assurance of the Tier-E information-flow property
(secrets never reach prompts, log sinks, or persisted state) at ~1% of the
cost of a --sif proof. The canary must be able to fail: negative controls
assert that capture actually works (vacuity rule, testing-strategies §P2).

Surfaces asserted:
  1. Outbound LLM payloads (mock transport capturing every message).
  2. All log records (caplog at DEBUG).
  3. Persisted job state (E4): jobs.result / jobs.error columns and the raw
     DB file bytes — a failed or cancelled job persists its error text, and
     the DB file outlives the process.
"""

import asyncio
import logging
import secrets
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from src.agent import AgentSystemArchitect
from src.config import (
    EmbedderConfig,
    EmbedderInnerConfig,
    GeneratorConfig,
    GeneratorInnerConfig,
    ServerConfig,
)
from src.pipeline import AgentPatternPipeline, CancellationToken
from src.tools.jobs import JobStatus, JobsStore
from src.tools.submit_agent_design import SubmitAgentDesignJobTool

CANARY_KEY = "sk-canary-" + secrets.token_hex(24)
NONSECRET_MARKER = "canary-negative-control-marker-8f2c1e"


class _DummyOut(BaseModel):
    field: str = "ok"


def _canary_server_config() -> ServerConfig:
    return ServerConfig(
        generator=GeneratorConfig(
            provider="openai",
            config=GeneratorInnerConfig(model="gpt-canary", api_key=CANARY_KEY),
        ),
        embedder=EmbedderConfig(
            provider="tei",
            config=EmbedderInnerConfig(base_url="http://localhost:8080"),
        ),
    )


@pytest.fixture
def capturing_agent() -> tuple[AgentSystemArchitect, list[list[str]]]:
    """AgentSystemArchitect configured with the canary key; its LLM transport
    is replaced by a mock that captures every outbound prompt payload."""
    agent = AgentSystemArchitect(_canary_server_config())

    captured_payloads: list[list[str]] = []

    async def _capturing_achat(messages: list[Any]) -> Any:
        captured_payloads.append([str(m.content) for m in messages])
        response = MagicMock()
        response.raw = _DummyOut()
        return response

    structured = MagicMock()
    structured.achat = AsyncMock(side_effect=_capturing_achat)
    client = MagicMock()
    client.as_structured_llm = MagicMock(return_value=structured)
    agent._llm = client
    return agent, captured_payloads


class TestSecretCanary:
    @pytest.mark.asyncio
    async def test_key_reaches_config_boundary(self, capturing_agent):
        """Positive control: the canary key is actually configured — without
        this the assertions below would be vacuously green."""
        agent, _ = capturing_agent
        assert agent._generator.config.api_key == CANARY_KEY

    @pytest.mark.asyncio
    async def test_key_never_in_outbound_payloads(self, capturing_agent):
        agent, payloads = capturing_agent
        await agent.generate_structured(
            f"system prompt with {NONSECRET_MARKER}",
            f"user prompt with {NONSECRET_MARKER}",
            _DummyOut,
        )
        assert payloads, "capture must observe at least one LLM call"
        all_text = "\n".join(msg for call in payloads for msg in call)
        assert NONSECRET_MARKER in all_text, "negative control: capture works"
        assert CANARY_KEY not in all_text

    @pytest.mark.asyncio
    async def test_key_never_in_logs(self, capturing_agent, caplog):
        agent, _ = capturing_agent
        with caplog.at_level(logging.DEBUG):
            await agent.generate_structured("system", "user", _DummyOut)
        assert CANARY_KEY not in caplog.text
        assert "generate_structured returned validated model" in caplog.text, (
            "negative control: log capture works"
        )
        assert CANARY_KEY not in repr(agent._llm.mock_calls)

    @pytest.mark.asyncio
    async def test_key_never_persisted_on_failed_job(
        self, capturing_agent, jobs_store: JobsStore, jobs_db_path: str
    ):
        """E4: a failed job persists its error text — the key must not leak
        into jobs.error / jobs.result / the raw DB file bytes."""
        agent, _ = capturing_agent
        pipeline = MagicMock(spec=AgentPatternPipeline)
        pipeline.run_design = AsyncMock(side_effect=RuntimeError("provider exploded"))

        tool = SubmitAgentDesignJobTool(agent=agent, pipeline=pipeline)
        job_id = await jobs_store.create_job(
            requirements=f"build it {NONSECRET_MARKER}", domain="dom"
        )
        await asyncio.wait_for(
            tool._run_job(
                job_id, "requirements", "dom", None, None, CancellationToken()
            ), timeout=10
        )

        job = await jobs_store.get_job(job_id)
        assert job["status"] == JobStatus.FAILED
        assert "provider exploded" in job["error"], "negative control: error persisted"
        assert CANARY_KEY not in job["error"]
        assert CANARY_KEY not in (job["result"] or "")
        assert NONSECRET_MARKER not in (job["result"] or "")

        db_bytes = Path(jobs_db_path).read_bytes()
        assert CANARY_KEY.encode() not in db_bytes
        assert NONSECRET_MARKER.encode() in db_bytes, "negative control: DB capture works"

    @pytest.mark.asyncio
    async def test_key_never_persisted_on_cancelled_job(
        self, capturing_agent, jobs_store: JobsStore, jobs_db_path: str
    ):
        """E4: a cancelled job must not carry the key in persisted state either."""
        agent, _ = capturing_agent
        SubmitAgentDesignJobTool(agent=agent, pipeline=MagicMock())
        job_id = await jobs_store.create_job(requirements="req", domain="dom")
        await jobs_store.set_cancelled(job_id)

        job = await jobs_store.get_job(job_id)
        assert job["status"] == JobStatus.CANCELLED
        assert CANARY_KEY not in (job["result"] or "")
        assert CANARY_KEY not in (job["error"] or "")

        db_bytes = Path(jobs_db_path).read_bytes()
        assert CANARY_KEY.encode() not in db_bytes
