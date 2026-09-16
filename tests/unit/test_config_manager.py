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
Unit tests for the real ConfigManager.load_config behaviour (src/config.py).

Every other unit test runs against the autouse-mocked ConfigManager; this module
exercises the actual load/expand/validate/cache logic. The module-level
``mock_config_manager`` fixture below shadows the conftest autouse fixture of the
same name (pytest override-by-redefinition) so the real code path runs here.

Covers:
- Path resolution priority: CONFIG_PATH env var > config_path param > default
- FileNotFoundError (ERR_010) for a missing config file
- ValueError for invalid JSON
- {env:VAR:-default} expansion in nested config values
- Pydantic validation errors (extra=forbid, removed planner/reflector sections)
- Config caching between calls and clear_cache() reset
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.config import ConfigManager


@pytest.fixture(autouse=True)
def mock_config_manager() -> None:
    """Shadow the conftest autouse fixture so the REAL ConfigManager runs in this module."""
    return


@pytest.fixture(autouse=True)
def _reset_config_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate the ConfigManager class-level cache and CONFIG_PATH env var per test."""
    ConfigManager.clear_cache()
    monkeypatch.delenv("CONFIG_PATH", raising=False)
    yield
    ConfigManager.clear_cache()


def _write_config(tmp_path: Path, **overrides: Any) -> str:
    """Write a minimal valid config.json into tmp_path and return its path as str."""
    config: dict[str, Any] = {
        "generator": {
            "provider": "openai",
            "config": {"model": "gpt-4"},
        },
        "embedder": {
            "provider": "tei",
            "config": {"base_url": "http://localhost:8080"},
        },
        "pattern_directory": "/tmp/patterns",
    }
    config.update(overrides)
    path = tmp_path / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config), encoding="utf-8")
    return str(path)


class TestPathResolution:
    def test_config_path_env_var_beats_config_path_parameter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CONFIG_PATH env var has the highest priority (FR-272)."""
        env_config = _write_config(tmp_path / "env", pattern_directory="/tmp/from-env")
        param_config = _write_config(tmp_path / "param", pattern_directory="/tmp/from-param")
        monkeypatch.setenv("CONFIG_PATH", env_config)

        result = ConfigManager.load_config(param_config)

        assert result["pattern_directory"] == "/tmp/from-env"

    def test_config_path_parameter_used_when_env_unset(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without CONFIG_PATH, the explicit config_path parameter is used (FR-14)."""
        param_config = _write_config(tmp_path, pattern_directory="/tmp/from-param")
        monkeypatch.delenv("CONFIG_PATH", raising=False)

        result = ConfigManager.load_config(param_config)

        assert result["pattern_directory"] == "/tmp/from-param"

    def test_default_path_used_when_no_env_and_no_param(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The DEFAULT_CONFIG_PATH class attribute is the final fallback (FR-271)."""
        default_config = _write_config(tmp_path, pattern_directory="/tmp/from-default")
        monkeypatch.delenv("CONFIG_PATH", raising=False)
        monkeypatch.setattr(ConfigManager, "DEFAULT_CONFIG_PATH", default_config)

        result = ConfigManager.load_config()

        assert result["pattern_directory"] == "/tmp/from-default"


class TestErrorPaths:
    def test_missing_config_file_raises_file_not_found(self, tmp_path: Path) -> None:
        """A non-existent config file raises FileNotFoundError with the absolute path (FR-15/IC-9)."""
        missing = tmp_path / "does-not-exist.json"

        with pytest.raises(FileNotFoundError, match="Configuration file not found at path"):
            ConfigManager.load_config(str(missing))

    def test_invalid_json_raises_value_error(self, tmp_path: Path) -> None:
        """Malformed JSON raises ValueError (ERR_010 family: invalid config)."""
        path = tmp_path / "broken.json"
        path.write_text("{not valid json", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid JSON configuration"):
            ConfigManager.load_config(str(path))

    def test_unknown_top_level_key_fails_validation(self, tmp_path: Path) -> None:
        """ServerConfig forbids extra keys; unknown sections raise ValidationError."""
        path = _write_config(tmp_path, unknown_section={"key": "value"})

        with pytest.raises(ValidationError, match="unknown_section"):
            ConfigManager.load_config(path)

    def test_removed_planner_section_is_rejected(self, tmp_path: Path) -> None:
        """Legacy planner/reflector sections are rejected with an actionable error."""
        path = _write_config(tmp_path, planner={"provider": "openai"})

        with pytest.raises(ValidationError, match="removed LLM section"):
            ConfigManager.load_config(path)


class TestEnvExpansion:
    def test_env_default_expansion_when_var_unset(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """{env:VAR:-default} resolves to the default when the variable is unset."""
        monkeypatch.delenv("APM_TEST_MODEL", raising=False)
        generator = {"provider": "openai", "config": {"model": "{env:APM_TEST_MODEL:-fallback-model}"}}
        path = _write_config(tmp_path, generator=generator)

        result = ConfigManager.load_config(path)

        assert result["generator"]["config"]["model"] == "fallback-model"

    def test_env_expansion_uses_var_value_when_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """{env:VAR:-default} resolves to the live variable when it is set."""
        monkeypatch.setenv("APM_TEST_MODEL", "custom-model")
        generator = {"provider": "openai", "config": {"model": "{env:APM_TEST_MODEL:-fallback-model}"}}
        path = _write_config(tmp_path, generator=generator)

        result = ConfigManager.load_config(path)

        assert result["generator"]["config"]["model"] == "custom-model"


class TestCaching:
    def test_second_load_returns_cached_config_without_file_access(self, tmp_path: Path) -> None:
        """After a successful load, the config is cached — deleting the file still loads."""
        path = _write_config(tmp_path, pattern_directory="/tmp/cached")

        first = ConfigManager.load_config(path)
        (tmp_path / "config.json").unlink()
        second = ConfigManager.load_config()

        assert second is first
        assert second["pattern_directory"] == "/tmp/cached"

    def test_clear_cache_forces_reload_from_disk(self, tmp_path: Path) -> None:
        """clear_cache() drops the cache; the next load re-reads (and fails if the file is gone)."""
        path = _write_config(tmp_path)
        ConfigManager.load_config(path)
        ConfigManager.clear_cache()
        (tmp_path / "config.json").unlink()

        with pytest.raises(FileNotFoundError):
            ConfigManager.load_config()
