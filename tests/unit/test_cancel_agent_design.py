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
Unit tests for the cancel_agent_design tool.

Covers:
- Unknown job_id -> ToolError (ERR_404)
- Terminal-status jobs (completed / failed / cancelled) cannot be cancelled again
- Non-terminal job without a live asyncio task -> DB flag set only
- Non-terminal job with a live asyncio task -> token + task cancellation, DB flag set
- cancel_agent_design_tool factory wiring
"""

import asyncio
from typing import cast
from unittest.mock import MagicMock

import pytest
from fastmcp.exceptions import ToolError

from src.pipeline import CancellationToken
from src.tools.cancel_agent_design import (
    CancelAgentDesignTool,
    cancel_agent_design_tool,
)
from src.tools.jobs import JobStatus, JobsStore


@pytest.fixture
def store(jobs_store: JobsStore) -> JobsStore:
    """The per-test isolated JobsStore instance provided by the conftest autouse fixture."""
    return jobs_store


def _make_live_task() -> MagicMock:
    """A stand-in for a running asyncio.Task (done() is False until cancelled)."""
    task = MagicMock()
    task.done.return_value = False
    return task


def _make_token() -> MagicMock:
    """A stand-in CancellationToken that records cancel() calls."""
    token = MagicMock(spec=CancellationToken)
    token.cancel = MagicMock()
    return token


class TestCancelUnknownJob:
    async def test_cancel_unknown_job_id_raises_tool_error(self, store: JobsStore) -> None:
        """Cancelling a job_id that does not exist raises ToolError with ERR_404."""
        tool = CancelAgentDesignTool()
        with pytest.raises(ToolError, match="ERR_404"):
            await tool.cancel("no-such-job-id")


class TestCancelTerminalJobs:
    @pytest.mark.parametrize(
        ("set_terminal", "expected_status"),
        [
            ("set_completed", JobStatus.COMPLETED),
            ("set_failed", JobStatus.FAILED),
            ("set_cancelled", JobStatus.CANCELLED),
        ],
    )
    async def test_terminal_job_cannot_be_cancelled_again(
        self, store: JobsStore, set_terminal: str, expected_status: str
    ) -> None:
        """A completed/failed/cancelled job returns cancelled=False and keeps its status."""
        job_id = await store.create_job("requirements", "web")
        if set_terminal == "set_completed":
            # W0-1 guarded transitions: reach terminal status via legitimate
            # transitions (set_completed/set_failed guard on RUNNING).
            await store.set_running(job_id)
            await store.set_completed(job_id, "result")
        elif set_terminal == "set_failed":
            await store.set_running(job_id)
            await store.set_failed(job_id, "error")
        else:
            await store.set_cancelled(job_id)

        tool = CancelAgentDesignTool()
        result = await tool.cancel(job_id)

        assert result["job_id"] == job_id
        assert result["status"] == expected_status
        assert result["cancelled"] is False
        assert "cannot cancel" in result["message"]

        job = await store.get_job(job_id)
        assert job is not None
        assert job["status"] == expected_status


class TestCancelWithoutLiveTask:
    async def test_pending_job_without_task_sets_db_flag_only(self, store: JobsStore) -> None:
        """Pending job with no registered asyncio task: DB flag set, task_was_running=False."""
        job_id = await store.create_job("requirements", "web")

        tool = CancelAgentDesignTool()
        result = await tool.cancel(job_id)

        assert result["job_id"] == job_id
        assert result["status"] == JobStatus.CANCELLED
        assert result["cancelled"] is True
        assert result["task_was_running"] is False
        assert "No live asyncio.Task" in result["message"]

        assert await store.is_cancelled(job_id) is True
        job = await store.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.CANCELLED

    async def test_running_job_without_task_sets_db_flag_only(self, store: JobsStore) -> None:
        """Running job with no registered asyncio task is cancelled via DB flag only."""
        job_id = await store.create_job("requirements", "web")
        await store.set_running(job_id)

        tool = CancelAgentDesignTool()
        result = await tool.cancel(job_id)

        assert result["cancelled"] is True
        assert result["task_was_running"] is False
        assert await store.is_cancelled(job_id) is True


class TestCancelWithLiveTask:
    async def test_running_job_with_live_task_cancels_token_and_task(self, store: JobsStore) -> None:
        """Live-task path: token.cancel() and task.cancel() are invoked, DB flag set."""
        job_id = await store.create_job("requirements", "web")
        await store.set_running(job_id)

        task = _make_live_task()
        token = _make_token()
        tool = CancelAgentDesignTool(job_tasks={job_id: (task, token)})

        result = await tool.cancel(job_id)

        token.cancel.assert_called_once()
        task.cancel.assert_called_once()

        assert result["cancelled"] is True
        assert result["task_was_running"] is True
        assert result["status"] == JobStatus.CANCELLED
        assert "next cancellation checkpoint" in result["message"]

        assert await store.is_cancelled(job_id) is True

    async def test_finished_task_reports_task_was_running_false(self, store: JobsStore) -> None:
        """A registered task that already finished reports task_was_running=False."""
        job_id = await store.create_job("requirements", "web")

        task = _make_live_task()
        task.done.return_value = True
        token = _make_token()
        tool = CancelAgentDesignTool(job_tasks={job_id: (task, token)})

        result = await tool.cancel(job_id)

        token.cancel.assert_called_once()
        task.cancel.assert_called_once()
        assert result["task_was_running"] is False


class TestFactory:
    def test_factory_returns_tool_with_empty_task_registry(self) -> None:
        """cancel_agent_design_tool() wires a CancelAgentDesignTool with no live tasks."""
        tool = cancel_agent_design_tool()
        assert isinstance(tool, CancelAgentDesignTool)
        assert tool._job_tasks == {}

    def test_factory_passes_job_tasks_through(self) -> None:
        """The factory forwards the provided job_tasks mapping."""
        task = cast("asyncio.Task[None]", MagicMock())
        token = cast("CancellationToken", MagicMock())
        tasks: dict[str, tuple[asyncio.Task[None], CancellationToken]] = {"job-1": (task, token)}
        tool = cancel_agent_design_tool(job_tasks=tasks)
        assert tool._job_tasks is tasks
