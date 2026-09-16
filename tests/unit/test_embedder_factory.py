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
Unit tests for the build_embedder factory (src/patterns/embedder.py).

The InstructionAwareEmbedding embedding paths are covered by test_vector_retriever.py;
this module covers the provider dispatch surface:
- Supported providers (openai / tei / ollama / vllm / hosted_vllm), case-insensitive
- TEI model pin (openai//data/qwen3-embedding-0.6b) vs empty model for other providers
- Forwarding of base_url / api_key / instructions / batch size
- ValueError for unsupported providers
"""

import pytest
from typing import cast

from src.patterns.embedder import (
    TEI_RERANKER_MODEL,
    InstructionAwareEmbedding,
    _normalize,
    build_embedder,
)


class TestProviderDispatch:
    @pytest.mark.parametrize("provider", ["openai", "tei", "ollama", "vllm", "hosted_vllm"])
    def test_supported_providers_construct_an_embedder(self, provider: str) -> None:
        """Every documented provider constructs an InstructionAwareEmbedding without network I/O."""
        embedder = build_embedder(
            provider=provider,
            base_url="http://localhost:8080",
            api_key=None,
            query_instruction="",
            text_instruction="",
        )
        assert isinstance(embedder, InstructionAwareEmbedding)

    def test_provider_lookup_is_case_insensitive(self) -> None:
        """Uppercase provider names are normalised before dispatch."""
        embedder = build_embedder(
            provider="TEI",
            base_url="http://localhost:8080",
            api_key=None,
            query_instruction="",
            text_instruction="",
        )
        assert isinstance(embedder, InstructionAwareEmbedding)

    def test_unsupported_provider_raises_value_error(self) -> None:
        """An unknown provider raises ValueError naming the offender."""
        with pytest.raises(ValueError, match="Unsupported embedder provider"):
            build_embedder(
                provider="huggingface",
                base_url="http://localhost:8080",
                api_key=None,
                query_instruction="",
                text_instruction="",
            )


class TestTeiModelPin:
    def test_tei_provider_pins_qwen3_model_name(self) -> None:
        """The tei provider fixes the model to the local Qwen3 variant (not overridable)."""
        embedder = build_embedder(
            provider="tei",
            base_url="http://localhost:8080",
            api_key=None,
            query_instruction="",
            text_instruction="",
        )
        assert embedder.model_name == "openai//data/qwen3-embedding-0.6b"

    @pytest.mark.parametrize("provider", ["openai", "ollama", "vllm", "hosted_vllm"])
    def test_non_tei_providers_use_empty_model_name(self, provider: str) -> None:
        """Non-tei providers leave the model name empty (set via LLM provider config)."""
        embedder = build_embedder(
            provider=provider,
            base_url="http://localhost:8080",
            api_key=None,
            query_instruction="",
            text_instruction="",
        )
        assert embedder.model_name == ""


class TestConfigForwarding:
    def test_connection_and_instruction_fields_are_forwarded(self) -> None:
        """base_url, api_key, instructions, and batch size reach the embedder."""
        embedder = build_embedder(
            provider="openai",
            base_url="http://embed-host:9999",
            api_key="secret-key",
            query_instruction="query: ",
            text_instruction="passage: ",
            embed_batch_size=32,
        )
        assert embedder.api_base == "http://embed-host:9999"
        assert embedder.api_key == "secret-key"
        assert embedder._query_instruction == "query: "
        assert embedder._text_instruction == "passage: "
        assert embedder.embed_batch_size == 32

    def test_empty_instructions_fall_back_to_empty_strings(self) -> None:
        """None-ish (empty) instruction inputs are normalised to empty strings."""
        embedder = build_embedder(
            provider="openai",
            base_url="http://localhost:8080",
            api_key=None,
            query_instruction="",
            text_instruction="",
        )
        assert embedder._query_instruction == ""
        assert embedder._text_instruction == ""


class TestNormalizeEdgeCases:
    def test_normalize_accepts_single_flat_vector(self) -> None:
        """A flat (1-D) vector is reshaped and L2-normalised (3-4-5 triangle)."""
        flat_vector = cast("list[list[float]]", [3.0, 4.0])
        result = _normalize(flat_vector)
        assert len(result) == 1
        assert result[0] == pytest.approx([0.6, 0.8])

    def test_tei_reranker_model_constant_is_stable(self) -> None:
        """The exported TEI reranker model identifier must not drift silently."""
        assert TEI_RERANKER_MODEL == "Alibaba-NLP/gte-reranker-modernbert-base"
