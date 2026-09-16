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

# Tests for QualityMetrics schema
# Validates: FR-17, FR-18, IC-10
# Test scenarios: SCEN-3
# Acceptance criteria: AC-18

import pytest
from pydantic import ValidationError

from src.schemas.quality import QualityMetrics


class TestQualityMetrics:
    """Test suite for QualityMetrics Pydantic model.

    Validates requirements:
    - FR-17: AgentPatternPipeline uses QualityMetrics
    - IC-10: 6 required properties with values in range 0-10

    Test scenarios:
    - SCEN-3: QualityMetrics validates 6 required properties
    """

    # SCEN-3: QualityMetrics validates 6 required properties
    def test_quality_metrics_6_required_properties(self):
        """SCEN-3: QualityMetrics validates 6 required properties.

        Verifies IC-10: QualityMetrics has all 6 required properties.
        Creates QualityMetrics with all 6 required properties.
        """
        qm = QualityMetrics(
            cost_efficiency=8.0,
            latency=7.5,
            output_quality=9.0,
            observability=8.5,
            safety=7.0,
            reliability=8.0
        )

        assert qm.cost_efficiency == 8.0
        assert qm.latency == 7.5
        assert qm.output_quality == 9.0
        assert qm.observability == 8.5
        assert qm.safety == 7.0
        assert qm.reliability == 8.0

    def test_quality_metrics_missing_required_property_raises_error(self):
        """SCEN-3: Missing required property should raise ValidationError.

        Verifies IC-10: All 6 required properties are mandatory.
        """
        with pytest.raises(ValidationError) as exc_info:
            QualityMetrics(
                cost_efficiency=8.0,
                # Missing latency, output_quality, observability, safety, reliability
            )

        errors = exc_info.value.errors()
        assert len(errors) == 5  # 5 missing required fields

    # IC-10: Values in range 0-10
    def test_values_at_minimum_boundary(self):
        """IC-10: Values can be 0.0 (minimum boundary).

        Verifies all 6 required properties accept minimum boundary value.
        """
        qm = QualityMetrics(
            cost_efficiency=0.0,
            latency=0.0,
            output_quality=0.0,
            observability=0.0,
            safety=0.0,
            reliability=0.0
        )

        assert qm.cost_efficiency == 0.0
        assert qm.latency == 0.0
        assert qm.output_quality == 0.0
        assert qm.observability == 0.0
        assert qm.safety == 0.0
        assert qm.reliability == 0.0

    def test_values_at_maximum_boundary(self):
        """IC-10: Values can be 10.0 (maximum boundary).

        Verifies all 6 required properties accept maximum boundary value.
        """
        qm = QualityMetrics(
            cost_efficiency=10.0,
            latency=10.0,
            output_quality=10.0,
            observability=10.0,
            safety=10.0,
            reliability=10.0
        )

        assert qm.cost_efficiency == 10.0
        assert qm.latency == 10.0
        assert qm.output_quality == 10.0
        assert qm.observability == 10.0
        assert qm.safety == 10.0
        assert qm.reliability == 10.0

    def test_value_below_range_raises_error(self):
        """IC-10: Values below 0.0 should raise ValidationError.

        Verifies ge=0.0 constraint is enforced.
        """
        with pytest.raises(ValidationError) as exc_info:
            QualityMetrics(
                cost_efficiency=-0.1,
                latency=5.0,
                output_quality=5.0,
                observability=5.0,
                safety=5.0,
                reliability=5.0
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]['loc'] == ('cost_efficiency',)

    def test_value_above_range_raises_error(self):
        """IC-10: Values above 10.0 should raise ValidationError.

        Verifies le=10.0 constraint is enforced.
        """
        with pytest.raises(ValidationError) as exc_info:
            QualityMetrics(
                cost_efficiency=10.1,
                latency=5.0,
                output_quality=5.0,
                observability=5.0,
                safety=5.0,
                reliability=5.0
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]['loc'] == ('cost_efficiency',)

    # IC-10: observability range 0-10
    def test_observability_at_minimum_boundary(self):
        """IC-10: observability can be 0.0 (minimum boundary).

        Verifies observability range includes 0.0.
        """
        qm = QualityMetrics(
            cost_efficiency=5.0,
            latency=5.0,
            output_quality=5.0,
            observability=0.0,
            safety=5.0,
            reliability=5.0
        )

        assert qm.observability == 0.0

    def test_observability_at_maximum_boundary(self):
        """IC-10: observability can be 10.0 (maximum boundary).

        Verifies observability range includes 10.0.
        """
        qm = QualityMetrics(
            cost_efficiency=5.0,
            latency=5.0,
            output_quality=5.0,
            observability=10.0,
            safety=5.0,
            reliability=5.0
        )

        assert qm.observability == 10.0

    def test_observability_within_range(self):
        """IC-10: observability accepts any value in 0-10 range.

        Verifies typical value is valid.
        """
        qm = QualityMetrics(
            cost_efficiency=5.0,
            latency=5.0,
            output_quality=5.0,
            observability=7.0,
            safety=5.0,
            reliability=5.0
        )

        assert 0.0 <= qm.observability <= 10.0
        assert qm.observability == 7.0

    def test_observability_below_range_raises_error(self):
        """IC-10: observability below 0.0 should raise ValidationError.

        Verifies observability ge=0.0 constraint is enforced.
        """
        with pytest.raises(ValidationError) as exc_info:
            QualityMetrics(
                cost_efficiency=5.0,
                latency=5.0,
                output_quality=5.0,
                observability=-0.1,
                safety=5.0,
                reliability=5.0
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]['loc'] == ('observability',)

    def test_observability_above_range_raises_error(self):
        """IC-10: observability above 10.0 should raise ValidationError.

        Verifies observability le=10.0 constraint is enforced.
        """
        with pytest.raises(ValidationError) as exc_info:
            QualityMetrics(
                cost_efficiency=5.0,
                latency=5.0,
                output_quality=5.0,
                observability=10.1,
                safety=5.0,
                reliability=5.0
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]['loc'] == ('observability',)
