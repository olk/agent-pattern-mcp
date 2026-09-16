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
Pytest fixtures for unit tests.

Provides mocked ConfigManager to avoid file system dependencies.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_config_manager():
    """Auto-mock ConfigManager.load_config for all unit tests."""
    mock_config = {
        "generator": {
            "provider": "openai",
            "config": {
                "model": "gpt-4",
                "base_url": "",
                "api_key": None,
                "temperature": 0.1,
                "top_p": 1.0,
                "top_k": 20,
            },
        },
        "embedder": {
            "provider": "tei",
            "config": {
                "base_url": "http://localhost:8080",
                "api_key": None,
                "embed_batch_size": 16,
                "query_instruction": "Instruct: Given an AI agent pattern domain tag, retrieve the most relevant existing pattern domain from the catalogue\nQuery: ",
                "text_instruction": "",
                "max_embedder_tokens": 3000,
            }
        },
        "reranker": {
            "config": {
                "base_url": "http://localhost:8080",
                "timeout": 30.0,
                "max_batch_size": 48,
            }
        },
        "pattern_directory": "/tmp/test_patterns",
        "logging_level": "INFO",
        "logging_format": "text",
        "transport": "stdio",
        "host": "127.0.0.1",
        "port": 8051,
        "validation": {
            "max_retries": 2,
            "retry_on_fail": True,
        },
    }

    mock_cm = MagicMock()
    mock_cm.load_config.return_value = mock_config
    mock_cm.DEFAULT_CONFIG_PATH = "/tmp/test_config.json"
    with patch('src.config.ConfigManager.load_config', mock_cm.load_config):
        yield mock_cm


@pytest.fixture(autouse=True)
def mock_tei_rerank():
    """Mock TextEmbeddingInference.postprocess_nodes to avoid HTTP calls in tests.

    Reranking is now mandatory (ff4dacf) when reranker_config is present.
    Most tests don't exercise reranking logic directly, so we return nodes
    unchanged to avoid DNS/HTTP errors in the test environment.
    """
    from llama_index.postprocessor.tei_rerank import TextEmbeddingInference
    with patch.object(TextEmbeddingInference, "postprocess_nodes", lambda self, nodes, **kw: nodes):
        yield


@pytest.fixture(autouse=True)
async def jobs_store(tmp_path, monkeypatch):
    """Isolate JobsStore to a per-test tmp_path SQLite database.

    Resets the singleton between tests so jobs from one test never bleed into another.
    Requires ``asyncio_mode = "auto"`` in pyproject.toml pytest config.
    """
    from src.tools.jobs import JobsStore

    db = tmp_path / "jobs.db"
    monkeypatch.setenv("AGENT_PATTERN_JOBS_DB", str(db))
    await JobsStore.reset_for_test()
    yield await JobsStore.get_instance()
    await JobsStore.reset_for_test()
    monkeypatch.delenv("AGENT_PATTERN_JOBS_DB", raising=False)
