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

"""Tests for pyproject.toml structure and metadata."""

import tomllib
from pathlib import Path


PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


def _load_pyproject():
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)


def test_project_name():
    data = _load_pyproject()
    assert data["project"]["name"] == "agent-pattern-mcp"


def test_project_version():
    data = _load_pyproject()
    assert "version" in data["project"]
    assert data["project"]["version"]


def test_python_version():
    data = _load_pyproject()
    assert data["project"]["requires-python"] == ">=3.12"


def test_entry_point():
    data = _load_pyproject()
    scripts = data["project"].get("scripts", {})
    assert "agent-pattern-mcp" in scripts
    assert scripts["agent-pattern-mcp"] == "src.main:cli"


def test_key_dependencies():
    data = _load_pyproject()
    deps = data["project"]["dependencies"]
    dep_names = [d.split(">=")[0].split("<")[0].strip() for d in deps]
    assert "fastmcp" in dep_names
    assert "pydantic" in dep_names
    assert "llama-index-core" in dep_names
    assert "llama-index-postprocessor-tei-rerank" in dep_names


def test_no_sentence_transformers():
    data = _load_pyproject()
    deps = data["project"]["dependencies"]
    dep_names = [d.split(">=")[0].split("<")[0].strip() for d in deps]
    assert "sentence-transformers" not in dep_names


def test_dev_dependencies():
    data = _load_pyproject()
    dev_deps = data.get("dependency-groups", {}).get("dev", [])
    dev_names = [d.split(">=")[0].strip() for d in dev_deps]
    assert "pytest" in dev_names
    assert "ruff" in dev_names
    assert "pyright" in dev_names
    assert "mypy" in dev_names
