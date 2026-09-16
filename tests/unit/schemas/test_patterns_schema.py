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
In-gate unit tests for src/schemas/patterns.py (Pattern / PatternQualityAttributes / ScoredPattern).

The property-based constraint suite lives in tests/schemas/ (outside the unit gate);
this module pins the same semantics with example-based tests inside the gate:

- PatternQualityAttributes: 1-10 bounds, mean() over the 7 dimensions
- Pattern: name regex, min-length constraints, suitable/unsuitable domain disjointness
- quality_score: 0-100 scale derived from the attribute mean
- ScoredPattern: optional analyze/fusion score fields with their bounds
"""

from typing import Any

import pytest
from pydantic import ValidationError

from src.schemas.enums import AgentDomain, AgentTopology, PatternCategory
from src.schemas.patterns import Pattern, PatternQualityAttributes, ScoredPattern

_QA: dict[str, float] = {
    "reliability": 8,
    "cost_efficiency": 6,
    "latency": 7,
    "output_quality": 9,
    "observability": 6,
    "safety": 7,
    "simplicity": 8,
}


def _make_pattern(**overrides: Any) -> dict[str, Any]:
    """A minimal valid Pattern payload; per-test overrides layered on top."""
    data: dict[str, Any] = {
        "topology": AgentTopology.HIERARCHICAL,
        "category": PatternCategory.PLANNING,
        "name": "test-pattern",
        "context": "When a test pattern is needed.",
        "benefits": ["Simplicity"],
        "tradeoffs": ["Coupling"],
        "quality_attributes": dict(_QA),
        "suitable_domains": [AgentDomain.AUTONOMOUS_TASK_EXECUTION],
        "unsuitable_domains": [AgentDomain.CYBERSECURITY],
    }
    data.update(overrides)
    return data


class TestPatternQualityAttributes:
    def test_mean_is_average_of_seven_dimensions(self) -> None:
        """mean() averages exactly the seven quality dimensions."""
        qa = PatternQualityAttributes(**_QA)
        assert qa.mean() == pytest.approx(sum(_QA.values()) / 7)

    @pytest.mark.parametrize("field", list(_QA))
    def test_dimension_below_one_is_rejected(self, field: str) -> None:
        """Each dimension rejects scores below 1."""
        payload = {**_QA, field: 0.5}
        with pytest.raises(ValidationError):
            PatternQualityAttributes(**payload)

    @pytest.mark.parametrize("field", list(_QA))
    def test_dimension_above_ten_is_rejected(self, field: str) -> None:
        """Each dimension rejects scores above 10."""
        payload = {**_QA, field: 10.1}
        with pytest.raises(ValidationError):
            PatternQualityAttributes(**payload)


class TestPattern:
    def test_valid_minimal_pattern_constructs(self) -> None:
        """A minimal valid payload constructs with optional lists defaulting to empty."""
        pattern = Pattern(**_make_pattern())
        assert pattern.name == "test-pattern"
        assert pattern.use_cases == []
        assert pattern.best_practices == []
        assert pattern.references == []

    @pytest.mark.parametrize("bad_name", ["React", "1abc", "has_underscore"])
    def test_name_regex_is_enforced(self, bad_name: str) -> None:
        """Names must match ^[a-z][a-z0-9-]*$ (lowercase start, no underscores)."""
        with pytest.raises(ValidationError):
            Pattern(**_make_pattern(name=bad_name))

    def test_empty_context_is_rejected(self) -> None:
        """context has min_length=1."""
        with pytest.raises(ValidationError):
            Pattern(**_make_pattern(context=""))

    def test_empty_benefits_are_rejected(self) -> None:
        """benefits has min_length=1."""
        with pytest.raises(ValidationError):
            Pattern(**_make_pattern(benefits=[]))

    def test_empty_tradeoffs_are_rejected(self) -> None:
        """tradeoffs has min_length=1."""
        with pytest.raises(ValidationError):
            Pattern(**_make_pattern(tradeoffs=[]))

    def test_suitable_and_unsuitable_domains_must_be_disjoint(self) -> None:
        """Overlapping suitable/unsuitable domains raise a named validator error."""
        payload = _make_pattern(
            unsuitable_domains=[AgentDomain.AUTONOMOUS_TASK_EXECUTION],
        )
        with pytest.raises(ValidationError, match="must be disjoint"):
            Pattern(**payload)

    def test_quality_score_is_mean_times_ten(self) -> None:
        """quality_score maps the 1-10 attribute mean onto the 0-100 scale."""
        pattern = Pattern(**_make_pattern())
        assert pattern.quality_score == pytest.approx(round(sum(_QA.values()) / 7 * 10, 1))


class TestScoredPattern:
    def test_score_fields_default_to_none(self) -> None:
        """All analyze/fusion scores are optional and default to None."""
        scored = ScoredPattern(**_make_pattern())
        assert scored.analysis_score is None
        assert scored.fusion_score is None
        assert scored.fusion_score_normalized is None
        assert scored.blended_score is None

    def test_score_fields_accept_valid_values(self) -> None:
        """A fully scored two-stage analyze payload round-trips."""
        scored = ScoredPattern(
            **_make_pattern(
                analysis_score=87.5,
                fusion_score=0.42,
                fusion_score_normalized=66.0,
                blended_score=79.4,
            )
        )
        assert scored.analysis_score == 87.5
        assert scored.blended_score == 79.4

    def test_analysis_score_above_100_is_rejected(self) -> None:
        """analysis_score is bounded to 0-100."""
        with pytest.raises(ValidationError):
            ScoredPattern(**_make_pattern(analysis_score=100.5))

    def test_fusion_score_must_be_non_negative(self) -> None:
        """fusion_score allows unbounded-above but rejects negatives."""
        with pytest.raises(ValidationError):
            ScoredPattern(**_make_pattern(fusion_score=-0.1))
