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
Unit tests for PatternLoader class.
"""

import json
import tempfile
from pathlib import Path

from src.patterns.loader import (
    QUALITY_ATTRIBUTES,
    PatternLoader,
)


def _make_pattern(name, category, suitable_domains, quality_attrs):
    return {
        "name": name,
        "topology": "hierarchical",
        "category": category,
        "context": "Test context",
        "benefits": ["Benefit 1"],
        "tradeoffs": ["Tradeoff 1"],
        "quality_attributes": quality_attrs,
        "suitable_domains": suitable_domains,
        "unsuitable_domains": [],
    }


class TestPatternLoaderInit:
    """Verify PatternLoader class exists and accepts optional patterns_dir parameter"""

    def test_pattern_loader_class_exists(self):
        """PatternLoader class can be instantiated"""
        loader = PatternLoader()
        assert loader is not None
        assert isinstance(loader, PatternLoader)

    def test_pattern_loader_accepts_custom_patterns_dir(self):
        """PatternLoader accepts optional patterns_dir parameter"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = PatternLoader(patterns_dir=tmpdir)
            assert loader._patterns_dir == Path(tmpdir)

    def test_pattern_loader_default_patterns_dir(self):
        """PatternLoader uses default path when no patterns_dir provided"""
        loader = PatternLoader()
        expected = Path(__file__).parent.parent.parent / "pattern"
        assert loader._patterns_dir == expected


class TestLoadAll:
    """Verify load_all method loads all pattern JSON files"""

    def test_load_all_returns_list(self):
        """load_all returns a list of patterns"""
        loader = PatternLoader()
        patterns = loader.load_all()
        assert isinstance(patterns, list)

    def test_load_all_loads_pattern_json_files(self):
        """PatternLoader loads all *-pattern.json files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_pattern = _make_pattern(
                "test-pattern",
                "reasoning",
                ["test-domain"],
                {"reliability": 8.0, "cost_efficiency": 7.0, "latency": 7.0, "output_quality": 8.0, "observability": 7.0, "safety": 8.0, "simplicity": 6.0},
            )

            pattern_file = Path(tmpdir) / "test-pattern.json"
            with open(pattern_file, 'w') as f:
                json.dump(test_pattern, f)

            loader = PatternLoader(patterns_dir=tmpdir)
            patterns = loader.load_all()

            assert len(patterns) == 1
            assert patterns[0]["name"] == "test-pattern"

    def test_load_all_lazy_loading(self):
        """Verify lazy loading - patterns loaded only on first call"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = PatternLoader(patterns_dir=tmpdir)

            assert loader._loaded is False
            assert loader._patterns_cache == []

            test_pattern = _make_pattern(
                "test-pattern",
                "reasoning",
                ["test-domain"],
                {"reliability": 8.0, "cost_efficiency": 7.0, "latency": 7.0, "output_quality": 8.0, "observability": 7.0, "safety": 8.0, "simplicity": 6.0},
            )
            pattern_file = Path(tmpdir) / "test-pattern.json"
            with open(pattern_file, 'w') as f:
                json.dump(test_pattern, f)

            patterns = loader.load_all()

            assert loader._loaded is True
            assert len(loader._patterns_cache) == 1

            patterns2 = loader.load_all()
            assert patterns2 == patterns

    def test_load_all_empty_directory(self):
        """load_all handles empty directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = PatternLoader(patterns_dir=tmpdir)
            patterns = loader.load_all()
            assert patterns == []

    def test_load_all_nonexistent_directory(self):
        """load_all handles nonexistent directory gracefully"""
        loader = PatternLoader(patterns_dir="/nonexistent/path")
        patterns = loader.load_all()
        assert patterns == []


class TestFilterByDomain:
    """Verify filter_by_domain method accepts domain string, returns filtered list"""

    def test_filter_by_domain_returns_list(self):
        """filter_by_domain returns a list"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = PatternLoader(patterns_dir=tmpdir)
            result = loader.filter_by_domain("test-domain")
            assert isinstance(result, list)

    def test_filter_by_domain_normalizes_domain(self):
        """filter_by_domain normalizes domain (lowercase + hyphens)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_pattern = _make_pattern(
                "test-pattern",
                "reasoning",
                ["cloud-native", "multi-agent-systems"],
                {"reliability": 8.0, "cost_efficiency": 7.0, "latency": 7.0, "output_quality": 8.0, "observability": 7.0, "safety": 8.0, "simplicity": 6.0},
            )

            pattern_file = Path(tmpdir) / "test-pattern.json"
            with open(pattern_file, 'w') as f:
                json.dump(test_pattern, f)

            loader = PatternLoader(patterns_dir=tmpdir)

            result = loader.filter_by_domain("Cloud Native")

            assert len(result) == 1
            assert result[0]["name"] == "test-pattern"

    def test_filter_by_domain_lowercase_conversion(self):
        """Domain normalization converts to lowercase"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_pattern = _make_pattern(
                "test-pattern",
                "reasoning",
                ["rag-applications"],
                {"reliability": 8.0, "cost_efficiency": 7.0, "latency": 7.0, "output_quality": 8.0, "observability": 7.0, "safety": 8.0, "simplicity": 6.0},
            )

            pattern_file = Path(tmpdir) / "test-pattern.json"
            with open(pattern_file, 'w') as f:
                json.dump(test_pattern, f)

            loader = PatternLoader(patterns_dir=tmpdir)

            result = loader.filter_by_domain("RAG APPLICATIONS")

            assert len(result) == 1

    def test_filter_by_domain_spaces_to_hyphens(self):
        """Domain normalization replaces spaces with hyphens"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_pattern = _make_pattern(
                "test-pattern",
                "reasoning",
                ["multi-agent-systems"],
                {"reliability": 8.0, "cost_efficiency": 7.0, "latency": 7.0, "output_quality": 8.0, "observability": 7.0, "safety": 8.0, "simplicity": 6.0},
            )

            pattern_file = Path(tmpdir) / "test-pattern.json"
            with open(pattern_file, 'w') as f:
                json.dump(test_pattern, f)

            loader = PatternLoader(patterns_dir=tmpdir)

            result = loader.filter_by_domain("multi agent systems")

            assert len(result) == 1

    def test_filter_by_domain_no_match(self):
        """filter_by_domain returns empty list when no patterns match"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_pattern = _make_pattern(
                "test-pattern",
                "reasoning",
                ["cloud-native"],
                {"reliability": 8.0, "cost_efficiency": 7.0, "latency": 7.0, "output_quality": 8.0, "observability": 7.0, "safety": 8.0, "simplicity": 6.0},
            )

            pattern_file = Path(tmpdir) / "test-pattern.json"
            with open(pattern_file, 'w') as f:
                json.dump(test_pattern, f)

            loader = PatternLoader(patterns_dir=tmpdir)

            result = loader.filter_by_domain("unknown-domain")

            assert len(result) == 0

    def test_filter_by_domain_excludes_unsuitable(self):
        """filter_by_domain excludes patterns whose unsuitable_domains contains the normalized domain"""
        with tempfile.TemporaryDirectory() as tmpdir:
            suitable_pattern = _make_pattern(
                "suitable-pattern",
                "reasoning",
                ["e-commerce"],
                {"reliability": 8.0, "cost_efficiency": 7.0, "latency": 7.0, "output_quality": 8.0, "observability": 7.0, "safety": 8.0, "simplicity": 6.0},
            )
            suitable_pattern["unsuitable_domains"] = ["simple-crud"]

            unsuitable_pattern = _make_pattern(
                "unsuitable-pattern",
                "reasoning",
                ["healthcare"],
                {"reliability": 8.0, "cost_efficiency": 7.0, "latency": 7.0, "output_quality": 8.0, "observability": 7.0, "safety": 8.0, "simplicity": 6.0},
            )
            unsuitable_pattern["unsuitable_domains"] = ["e-commerce", "simple-crud"]

            for p in [suitable_pattern, unsuitable_pattern]:
                pf = Path(tmpdir) / f"{p['name']}-pattern.json"
                with open(pf, 'w') as f:
                    json.dump(p, f)

            loader = PatternLoader(patterns_dir=tmpdir)

            result = loader.filter_by_domain("e-commerce")
            names = [p["name"] for p in result]

            assert "suitable-pattern" in names
            assert "unsuitable-pattern" not in names

    def test_filter_by_domain_unsuitable_normalized(self):
        """Verify unsuitable_domains is normalized like suitable_domains"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pattern = _make_pattern(
                "test-pattern",
                "reasoning",
                ["cloud-native"],
                {"reliability": 8.0, "cost_efficiency": 7.0, "latency": 7.0, "output_quality": 8.0, "observability": 7.0, "safety": 8.0, "simplicity": 6.0},
            )
            pattern["unsuitable_domains"] = ["Simple CRUD Applications"]

            pattern_file = Path(tmpdir) / "test-pattern.json"
            with open(pattern_file, 'w') as f:
                json.dump(pattern, f)

            loader = PatternLoader(patterns_dir=tmpdir)

            result = loader.filter_by_domain("cloud-native")
            assert len(result) == 1
            assert result[0]["name"] == "test-pattern"

            result2 = loader.filter_by_domain("simple crud applications")
            assert len(result2) == 0


class TestIntegration:
    """Integration tests for full PatternLoader workflow"""

    def test_full_workflow_load_filter(self):
        """Test complete workflow: load -> filter"""
        with tempfile.TemporaryDirectory() as tmpdir:
            patterns = [
                _make_pattern(
                    "pattern-a",
                    "reasoning",
                    ["multi-agent-systems", "rag-applications"],
                    {"reliability": 8.0, "cost_efficiency": 7.0, "latency": 7.0, "output_quality": 8.0, "observability": 7.0, "safety": 8.0, "simplicity": 6.0},
                ),
                _make_pattern(
                    "pattern-b",
                    "planning",
                    ["multi-agent-systems"],
                    {"reliability": 7.0, "cost_efficiency": 8.0, "latency": 7.0, "output_quality": 7.0, "observability": 8.0, "safety": 7.0, "simplicity": 7.0},
                ),
                _make_pattern(
                    "pattern-c",
                    "memory",
                    ["simple-domain"],
                    {"reliability": 6.0, "cost_efficiency": 6.0, "latency": 6.0, "output_quality": 6.0, "observability": 6.0, "safety": 6.0, "simplicity": 9.0},
                ),
            ]

            for i, pattern in enumerate(patterns):
                pattern_file = Path(tmpdir) / f"pattern{i}-pattern.json"
                with open(pattern_file, 'w') as f:
                    json.dump(pattern, f)

            loader = PatternLoader(patterns_dir=tmpdir)

            all_patterns = loader.load_all()
            assert len(all_patterns) == 3

            filtered = loader.filter_by_domain("multi agent systems")
            assert len(filtered) == 2

    def test_domain_normalization_integration(self):
        """Test domain normalization works in full workflow"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pattern = _make_pattern(
                "test-pattern",
                "reasoning",
                ["multi-agent-systems"],
                {"reliability": 8.0, "cost_efficiency": 7.0, "latency": 7.0, "output_quality": 8.0, "observability": 7.0, "safety": 8.0, "simplicity": 6.0},
            )

            pattern_file = Path(tmpdir) / "test-pattern.json"
            with open(pattern_file, 'w') as f:
                json.dump(pattern, f)

            loader = PatternLoader(patterns_dir=tmpdir)

            result1 = loader.filter_by_domain("multi agent systems")
            result2 = loader.filter_by_domain("Multi Agent Systems")
            result3 = loader.filter_by_domain("MULTI-AGENT-SYSTEMS")

            assert len(result1) == 1
            assert len(result2) == 1
            assert len(result3) == 1
            assert result1[0]["name"] == result2[0]["name"] == result3[0]["name"]
