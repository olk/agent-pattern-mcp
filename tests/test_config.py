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

"""Tests for configuration loading and env-var expansion."""

import os

import pytest

from src.config import ConfigManager, ServerConfig, RetrievalConfig
from src.config_expansion import expand_env, expand_env_in_obj
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _clear_cache():
    ConfigManager.clear_cache()
    yield
    ConfigManager.clear_cache()


def test_load_config_real_file():
    os.environ["GENERATOR_API_KEY"] = "test-key"
    config_dict = ConfigManager.load_config("config/config.json")
    config = ServerConfig.model_validate(config_dict)
    assert config.generator.provider == "openai"
    assert config.port == 8051
    assert config.transport == "streamable-http"
    assert config.pattern_directory.endswith("agent-pattern-mcp/pattern")


def test_removed_llm_sections_rejected_planner():
    os.environ["GENERATOR_API_KEY"] = "test-key"
    cfg = dict(ConfigManager.load_config("config/config.json"))
    cfg["planner"] = {"provider": "openai", "config": {"model": "gpt-4"}}
    with pytest.raises(ValidationError, match="removed LLM section"):
        ServerConfig.model_validate(cfg)


def test_removed_llm_sections_rejected_reflector():
    os.environ["GENERATOR_API_KEY"] = "test-key"
    cfg = dict(ConfigManager.load_config("config/config.json"))
    cfg["reflector"] = {"provider": "openai", "config": {"model": "gpt-4"}}
    with pytest.raises(ValidationError, match="removed LLM section"):
        ServerConfig.model_validate(cfg)


def test_removed_llm_sections_message_wins_over_missing_reranker():
    """Friendly rejection message fires when legacy LLM sections are present.

    _reject_removed_llm_sections is the only mode="before" validator;
    pydantic v2 runs it before field validation, so the rejection message
    wins over any later validation noise.
    """
    cfg = {
        "generator": {"provider": "openai", "config": {"model": "gpt-4", "api_key": None}},
        "planner": {"provider": "openai", "config": {"model": "gpt-4", "api_key": None}},
        "reflector": {"provider": "openai", "config": {"model": "gpt-4", "api_key": None}},
        "embedder": {"provider": "tei", "config": {"base_url": "http://localhost:8080", "api_key": None}},
    }
    with pytest.raises(ValidationError, match="removed LLM section"):
        ServerConfig.model_validate(cfg)


def test_legacy_generator_roles_key_rejected():
    os.environ["GENERATOR_API_KEY"] = "test-key"
    cfg = {
        "generator": {
            "provider": "openai",
            "config": {"model": "gpt-4", "api_key": None},
            "roles": {},
        },
        "embedder": {"provider": "tei", "config": {"base_url": "http://localhost:8080", "api_key": None}},
        "reranker": {"config": {"base_url": "http://localhost:8080", "timeout": 30.0}},
    }
    with pytest.raises(ValidationError):
        ServerConfig.model_validate(cfg)


def test_validation_config():
    os.environ["GENERATOR_API_KEY"] = "test-key"
    config_dict = ConfigManager.load_config("config/config.json")
    config = ServerConfig.model_validate(config_dict)
    assert config.validation.max_retries == 2
    assert config.validation.retry_on_fail is True


def test_retrieval_config():
    os.environ["GENERATOR_API_KEY"] = "test-key"
    config_dict = ConfigManager.load_config("config/config.json")
    config = ServerConfig.model_validate(config_dict)
    assert config.retrieval is not None
    # retrieval.mode removed by the fusion-mode lock (1f1cf2f lineage):
    # stage-1 fusion is pinned to FUSION_MODES.RELATIVE_SCORE in
    # src/patterns/retriever.py and is no longer config-exposable.
    assert not hasattr(config.retrieval, "mode")
    assert config.retrieval.topology_score_threshold == 50.0
    # enable_reranking removed by ff4dacf (reranking now mandatory)


def test_expand_env_with_default():
    assert expand_env("{env:MISSING_VAR:-fallback}") == "fallback"


def test_expand_env_without_default():
    assert expand_env("{env:MISSING_VAR}") == ""


def test_expand_env_in_obj():
    obj = {"key": "{env:TEST_VAR:-default}", "nested": {"inner": "{env:OTHER:-other}"}}
    result = expand_env_in_obj(obj)
    assert result["key"] == "default"
    assert result["nested"]["inner"] == "other"


def test_expand_env_with_existing_var():
    os.environ["EXISTING_VAR"] = "real_value"
    try:
        assert expand_env("{env:EXISTING_VAR}") == "real_value"
        assert expand_env("{env:EXISTING_VAR:-fallback}") == "real_value"
    finally:
        del os.environ["EXISTING_VAR"]


class TestMigrationValidator:
    """Tests for top-level reranker handling (post-3fe1e0b strict behavior)."""

    def test_reranker_missing_gets_default(self):
        """Config without reranker validates with the TEI default base_url."""
        cfg = {
            "generator": {"provider": "openai", "config": {"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"}},
            "embedder": {"provider": "tei", "config": {"base_url": "http://localhost:8080"}},
        }
        result = ServerConfig.model_validate(cfg)
        assert result.reranker is not None
        assert result.reranker.config is not None
        assert result.reranker.config.base_url == "http://pattern-tei-rerank:8080"

    def test_reranker_new_format_passes(self):
        """New top-level reranker format passes validation."""
        cfg = {
            "generator": {"provider": "openai", "config": {"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"}},
            "embedder": {"provider": "tei", "config": {"base_url": "http://localhost:8080"}},
            "reranker": {"config": {"base_url": "http://rerank:8080", "timeout": 30.0}},
        }
        result = ServerConfig.model_validate(cfg)
        assert result.reranker is not None
        assert result.reranker.config is not None
        assert result.reranker.config.base_url == "http://rerank:8080"

    def test_legacy_retrieval_reranker_rejected(self):
        """Legacy nested retrieval.reranker is rejected (BREAKING, 3fe1e0b).

        The auto-migration shim is gone; extra="forbid" on RetrievalConfig
        rejects the unknown nested `reranker` key with an actionable error.
        """
        cfg = {
            "generator": {"provider": "openai", "config": {"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"}},
            "embedder": {"provider": "tei", "config": {"base_url": "http://localhost:8080"}},
            "retrieval": {
                "reranker": {"enabled": True, "config": {"base_url": "http://rerank:8080", "timeout": 30.0}}
            },
        }
        with pytest.raises(ValidationError, match="reranker"):
            ServerConfig.model_validate(cfg)

    def test_empty_reranker_base_url_raises(self):
        """Reranker with empty base_url raises ValueError (post-3fe1e0b behavior).

        ServerConfig._check_reranker_configured rejects an explicitly
        configured reranker whose config.base_url is empty.
        """
        cfg = {
            "generator": {"provider": "openai", "config": {"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"}},
            "embedder": {"provider": "tei", "config": {"base_url": "http://localhost:8080"}},
            "reranker": {"config": {"base_url": "", "timeout": 30.0}},
        }
        with pytest.raises(ValidationError, match="base_url"):
            ServerConfig.model_validate(cfg)


class TestMinFusionScoreScaleInteraction:
    """Stage-1 + slug-cut are locked: gate always sees the blend
    (max ≈ 2/60).  Any positive min_fusion_score above the blend's
    theoretical maximum would reject every query.  The
    ServerConfig validator (and the field's `le=RANK_FUSION_BLEND_MAX`
    constraint) catch this.

    Ported from architecture-pattern-mcp 1f1cf2f.
    """

    @staticmethod
    def _server(**overrides) -> "ServerConfig":
        kwargs = {
            "generator": {"provider": "openai", "config": {"model": "gpt-4"}},
            "embedder": {"provider": "tei", "config": {"base_url": "http://x"}},
            "reranker": {"config": {"base_url": "http://x"}},
            "retrieval": {"min_fusion_score": 0.25},
        }
        kwargs.update(overrides)
        return ServerConfig(**kwargs)

    def test_field_validator_rejects_floor_above_blend_max(self) -> None:
        """Field-level le=RANK_FUSION_BLEND_MAX rejects values like 0.25."""
        from src.config import RANK_FUSION_BLEND_MAX
        with pytest.raises(ValidationError):
            RetrievalConfig(min_fusion_score=RANK_FUSION_BLEND_MAX + 1e-9)

    def test_default_floor_is_zero(self) -> None:
        """Default min_fusion_score is 0.0 (gate disabled)."""
        assert RetrievalConfig().min_fusion_score == 0.0

    def test_floor_at_blend_max_accepted(self) -> None:
        """Floor exactly at RANK_FUSION_BLEND_MAX (theoretical max) is the upper bound."""
        from src.config import RANK_FUSION_BLEND_MAX
        cfg = RetrievalConfig(min_fusion_score=RANK_FUSION_BLEND_MAX)
        assert cfg.min_fusion_score == RANK_FUSION_BLEND_MAX

    def test_floor_just_above_blend_max_rejected(self) -> None:
        """One ulp above the blend maximum fails the field validator."""
        from src.config import RANK_FUSION_BLEND_MAX
        with pytest.raises(ValidationError):
            RetrievalConfig(min_fusion_score=RANK_FUSION_BLEND_MAX * (1 + 1e-9))

    def test_server_validator_rejects_legacy_floor(self) -> None:
        """A leftover min_fusion_score=0.25 from pre-lock configs fails the
        field's le=RANK_FUSION_BLEND_MAX constraint even through ServerConfig
        (issue #3 lineage)."""
        with pytest.raises(ValidationError, match="min_fusion_score"):
            self._server()

    def test_removed_mode_field_rejected(self) -> None:
        """The fusion mode is no longer config-exposable: RetrievalConfig's
        extra="forbid" rejects the removed `mode` key (hard operator failure)."""
        with pytest.raises(ValidationError):
            RetrievalConfig(mode="reciprocal_rerank")  # type: ignore[call-arg]

    def test_removed_rerank_selection_field_rejected(self) -> None:
        """The slug-cut strategy is locked: `rerank_selection` fails startup."""
        from src.config import RerankerConfig

        with pytest.raises(ValidationError):
            RerankerConfig(rerank_selection="rank_fusion")  # type: ignore[call-arg]


class TestLegWeights:
    """Stage-1 fusion leg weights are operator-tunable (4e65a89 lineage):
    defaults 0.7/0.3, sum-to-1 validated (±1e-3), extreme ratios warn."""

    def test_leg_weight_defaults(self) -> None:
        """Stage-1 fusion leg weights default to dense 0.7 / BM25 0.3."""
        config = RetrievalConfig()
        assert config.dense_weight == 0.7
        assert config.bm25_weight == 0.3

    def test_leg_weight_custom_balanced_pair(self) -> None:
        """Any positive pair summing to 1.0 (±1e-3) is accepted."""
        config = RetrievalConfig(dense_weight=0.4, bm25_weight=0.6)
        assert config.dense_weight == 0.4
        assert config.bm25_weight == 0.6

    def test_leg_weight_rejects_zero(self) -> None:
        """Zero disables a leg entirely; gt=0 rejects it."""
        with pytest.raises(ValidationError):
            RetrievalConfig(dense_weight=0.0, bm25_weight=1.0)
        with pytest.raises(ValidationError):
            RetrievalConfig(dense_weight=1.0, bm25_weight=0.0)

    def test_leg_weight_rejects_sum_not_one(self) -> None:
        """Pairs not summing to 1.0 (±1e-3) fail the model validator."""
        with pytest.raises(ValidationError, match="dense_weight \\+ bm25_weight"):
            RetrievalConfig(dense_weight=0.5, bm25_weight=0.4)

    def test_leg_weight_rejects_above_one(self) -> None:
        """Individual weights are capped at le=1.0."""
        with pytest.raises(ValidationError):
            RetrievalConfig(dense_weight=1.5, bm25_weight=-0.5)

    def test_extreme_leg_weights_warn(self, caplog: pytest.LogCaptureFixture) -> None:
        """A5: extreme ratios (either weight < 0.05) are accepted but log a
        startup WARNING so operators catch effective single-leg configs."""
        import logging

        with caplog.at_level(logging.WARNING, logger="src.config"):
            config = RetrievalConfig(dense_weight=0.97, bm25_weight=0.03)
        assert config.dense_weight == 0.97
        assert any(
            "effectively disabled" in record.message for record in caplog.records
        )

    def test_normal_leg_weights_do_not_warn(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Default weights must not trigger the extreme-ratio warning."""
        import logging

        with caplog.at_level(logging.WARNING, logger="src.config"):
            RetrievalConfig()
        assert not any(
            "effectively disabled" in record.message for record in caplog.records
        )
