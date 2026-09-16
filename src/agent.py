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
# FR-174: The system SHALL provide an AgentSystemArchitect class that encapsulates LLM interactions via LlamaIndex LiteLLM
# FR-175: The system SHALL provide a generate_structured method that accepts system_prompt, user_prompt, and response_schema and returns a validated Pydantic model
# E-9: ERR_009 - LLM provider returned error (HTTP 502, severity: error)

LLM interaction wrapper via LlamaIndex LiteLLM with generate_structured method.

A single LLM configuration (``generator``) serves every pipeline phase
(planning, generation, reflection). It carries provider, model, base_url,
api_key, temperature, top_p, top_k, and stream settings. One shared LiteLLM
client is built lazily from it and reused for all calls.

# ADR-8: LlamaIndex LiteLLM for Multi-Provider LLM Access
# Strategy Pattern (DP-2): LlamaIndex abstracts multiple providers enabling provider switching
"""

from __future__ import annotations

import logging
from typing import Any, cast

import litellm

from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.llms.litellm import LiteLLM
from pydantic import BaseModel, ValidationError

from src.config import GeneratorConfig, ServerConfig

ERROR_LLM_PROVIDER = "ERR_009"

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """
    # E-9: ERR_009 - LLM provider returned error (HTTP 502, severity: error)

    Custom exception for LLM provider errors mapped from LlamaIndex/LiteLLM exceptions.

    # logging_context: provider, error, provider_message
    """

    def __init__(self, provider: str, error: str, provider_message: str):
        """
        Initialize LLMError with logging context.

        Args:
            provider: The LLM provider name (e.g., "openai", "anthropic").
            error: The error code (e.g., "ERR_009").
            provider_message: The error message from the provider.
        """
        self.provider = provider
        self.error = error
        self.provider_message = provider_message
        super().__init__(f"LLM provider {provider} error: {error} - {provider_message}")


class AgentSystemArchitect:
    """
    # FR-174: The system SHALL provide an AgentSystemArchitect class that encapsulates LLM interactions via LlamaIndex LiteLLM

    LLM interaction wrapper using LlamaIndex LiteLLM for multi-provider support.

    A single LLM configuration (``generator``) is stored as a ``GeneratorConfig``
    instance and carries provider, model, base_url, api_key, temperature,
    top_p, top_k, and stream settings. One shared LiteLLM client is built
    lazily and reused for every ``generate_structured`` call.

    # ADR-8: LlamaIndex LiteLLM for Multi-Provider LLM Access
    # Strategy Pattern (DP-2): LlamaIndex abstracts multiple providers (OpenAI, Anthropic, Azure, etc.)

    # FR-175: generate_structured method implemented in AgentSystemArchitect
    """

    def __init__(self, config: ServerConfig):
        """
        Initialize AgentSystemArchitect with LLM configuration.

        # FR-174: AgentSystemArchitect class accepts ServerConfig parameter

        Args:
            config: ServerConfig instance containing LLM configuration.
                   Must have generator.provider, generator.config.model,
                   generator.config.temperature, etc.
        """
        litellm.suppress_debug_info = True
        litellm_level = getattr(logging, config.litellm_log_level)
        for _name in ("litellm", "LiteLLM", "httpcore", "httpcore.http11",
                      "httpx", "openai", "openai._base_client",
                      "aiosqlite", "asyncio"):
            logging.getLogger(_name).setLevel(litellm_level)
        self._generator = config.generator
        self._validation_config = config.validation
        self._llm: LiteLLM | None = None

        logger.debug(
            "AgentSystemArchitect initialized",
            extra={"generator": self._generator.provider},
        )

    def _get_llm(self) -> LiteLLM:
        """
        Get (or lazily build) the shared LiteLLM client.

        Builds the client from the single ``generator`` GeneratorConfig section on
        first use and caches it on the instance for all subsequent calls.
        """
        if self._llm is not None:
            return self._llm

        section: GeneratorConfig = self._generator
        cfg = section.config

        bare_model = cfg.model
        if "/" in bare_model:
            bare_model = bare_model.split("/", 1)[1]
        model_string = f"{section.provider}/{bare_model}"

        additional_kwargs: dict[str, Any] = {"top_p": cfg.top_p, "top_k": cfg.top_k}
        if cfg.stream:
            additional_kwargs["stream"] = True

        try:
            llm = LiteLLM(
                model=model_string,
                temperature=cfg.temperature,
                api_key=cfg.api_key,
                api_base=cfg.base_url or None,
                additional_kwargs=additional_kwargs,
            )
        except Exception as exc:
            raise LLMError(
                provider=section.provider,
                error=ERROR_LLM_PROVIDER,
                provider_message=f"failed to initialize LLM: {exc}",
            ) from exc

        self._llm = llm
        return llm

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        """
        # FR-175: The system SHALL provide a generate_structured method that accepts
        system_prompt, user_prompt, and response_schema and returns a validated Pydantic model

        Generate a structured response using LlamaIndex LiteLLM with Pydantic validation.

        Self-healing retry loop: on ValidationError, extracts error details and
        retries with a corrected prompt (up to validation.max_retries times).

        Args:
            system_prompt: The system prompt to guide the LLM behavior.
            user_prompt: The user prompt/content for the LLM.
            response_schema: A Pydantic BaseModel subclass for response validation.

        Returns:
            An instance of response_schema validated by Pydantic.

        # E-9: ERR_009 - LLM provider returned error
        """
        if self._validation_config.retry_on_fail and self._validation_config.max_retries > 0:
            async def initial_caller() -> BaseModel:
                return await self._generate_structured_once(
                    system_prompt, user_prompt, response_schema
                )

            async def repair_caller(sp: str, up: str) -> BaseModel:
                return await self._generate_structured_once(sp, up, response_schema)

            from src.validation import validate_with_retries

            return await validate_with_retries(
                initial_caller,
                repair_caller,
                response_schema,
                max_retries=self._validation_config.max_retries,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

        return await self._generate_structured_once(
            system_prompt, user_prompt, response_schema
        )

    async def _generate_structured_once(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        """Single-shot structured generation without retry."""
        llm = self._get_llm()
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
        ]

        structured_llm = llm.as_structured_llm(response_schema)
        try:
            response = await structured_llm.achat(messages)
        except ValidationError as exc:
            # The structured program re-parses the raw LLM text against the
            # schema; malformed output (unquoted keys, trailing commas,
            # code fences) surfaces here as a json_invalid ValidationError
            # carrying the raw text. Recover it before burning LLM calls in
            # the self-healing retry loop.
            from src.validation import repair_json_validation_error

            repaired = repair_json_validation_error(exc, response_schema)
            if repaired is not None:
                return repaired
            raise
        except Exception as e:
            # E-9: raw transport/provider failures (timeout, connection reset,
            # provider explosion) must surface as the structured LLMError
            # (ERR_009) — never escape raw and never hang the caller.
            raise LLMError(
                provider=self._generator.provider,
                error=ERROR_LLM_PROVIDER,
                provider_message=str(e),
            ) from e

        logger.debug(
            "generate_structured returned validated model",
            extra={
                "schema_type": response_schema.__name__,
            }
        )

        return cast(BaseModel, response.raw)



__all__ = ["AgentSystemArchitect", "LLMError", "ERROR_LLM_PROVIDER"]
