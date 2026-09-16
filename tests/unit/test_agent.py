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
Unit tests for src/agent.py AgentSystemArchitect class.
"""

from src.agent import (
    ERROR_LLM_PROVIDER,
    LLMError,
    AgentSystemArchitect,
)
from src.config import ServerConfig


class ResponseSchema:
    """Test schema for generate_structured method validation."""
    name: str
    description: str
    score: float


class TestAgentSystemArchitectInit:
    """Test AgentSystemArchitect initialization."""

    def test_agent_initialization_with_valid_config(self):
        """AgentSystemArchitect accepts ServerConfig with generator and embedder."""
        config = ServerConfig(
            generator={"provider": "openai", "config": {"model": "gpt-4", "temperature": 0.7}},
            embedder={"provider": "tei", "config": {"base_url": "http://localhost:8080"}},
            reranker={"config": {"base_url": "http://localhost:8080", "timeout": 30.0}},
        )

        agent = AgentSystemArchitect(config)

        assert agent is not None
        assert agent._generator.config.temperature == 0.7
        assert agent._generator.config.model == "gpt-4"

    def test_agent_initialization_with_custom_settings(self):
        """AgentSystemArchitect stores custom LLM settings."""
        config = ServerConfig(
            generator={
                "provider": "openai",
                "config": {
                    "model": "gpt-4",
                    "temperature": 0.9,
                    "top_p": 0.9,
                    "top_k": 10,
                    "api_key": "sk-test",
                    "base_url": "https://api.openai.com/v1",
                }
            },
            embedder={"provider": "tei", "config": {"base_url": "http://localhost:8080"}},
            reranker={"config": {"base_url": "http://localhost:8080", "timeout": 30.0}},
        )

        agent = AgentSystemArchitect(config)

        assert agent._generator.config.top_p == 0.9
        assert agent._generator.config.top_k == 10
        assert agent._generator.config.api_key == "sk-test"
        assert agent._generator.config.base_url == "https://api.openai.com/v1"


class TestLLMError:
    """Test LLMError exception class."""

    def test_llm_error_attributes(self):
        """LLMError has provider, error, provider_message attributes."""
        error = LLMError(
            provider="openai",
            error="ERR_009",
            provider_message="API key invalid"
        )

        assert error.provider == "openai"
        assert error.error == "ERR_009"
        assert error.provider_message == "API key invalid"
        assert "openai" in str(error)
        assert "ERR_009" in str(error)


class TestConstants:
    """Test error constants."""

    def test_error_llm_provider_code(self):
        """ERROR_LLM_PROVIDER = 'ERR_009'."""
        assert ERROR_LLM_PROVIDER == "ERR_009"


class TestGetLLM:
    """Test _get_llm single shared client behavior."""

    def _make_config(self, model="gpt-4"):
        return ServerConfig(
            generator={"provider": "openai", "config": {"model": model, "temperature": 0.1, "api_key": "sk-test"}},
            embedder={"provider": "tei", "config": {"base_url": "http://localhost:8080"}},
            reranker={"config": {"base_url": "http://localhost:8080", "timeout": 30.0}},
        )

    def test_get_llm_returns_generator_llm(self):
        agent = AgentSystemArchitect(self._make_config(model="gpt-4"))
        llm = agent._get_llm()
        assert "gpt-4" in llm.model

    def test_get_llm_is_shared_and_cached(self):
        """_get_llm() builds exactly one LiteLLM instance, reused on every call."""
        agent = AgentSystemArchitect(self._make_config())
        llm_first = agent._get_llm()
        llm_second = agent._get_llm()
        assert llm_first is llm_second
        assert agent._llm is llm_first
