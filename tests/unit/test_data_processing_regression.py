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

"""Regression test: self-rag enters selection for rag-applications.

Before this change, self-rag (canonical fit for 'rag-applications',
listed first in suitable_domains) was dropped from selection because
stage-2 ranked purely on requirements-weighted quality_attributes.
After: blended scoring (0.7/0.3) + weight smoothing (alpha=0.7)
lifts it into the top-5 selected_patterns.

Port note (arch → agent adaptation):
- ArchitecturePipeline → AgentPatternPipeline; vector_index=/bm25_index=
  mocks replaced by the single injected `embedder=` dependency (retrieval
  legs are built internally at warmup).
- 6 arch QA keys → agent 7-key quality model; arch attribute weights
  (scalability/reliability/performance) mapped to
  (output_quality/reliability/latency).
- arch pattern names (pipe-and-filter, kappa-architecture, ...) mapped to
  agent catalog names (self-rag, chain-of-thought, ...) — loader is mocked,
  so names are illustrative only.
"""

from unittest.mock import MagicMock

from src.config import RetrievalConfig
from src.pipeline import AgentPatternPipeline, RequirementWeights
from src.schemas.analysis import QUALITY_ATTRIBUTE_KEYS

_QA_KEYS = QUALITY_ATTRIBUTE_KEYS


def _make_pipeline():
    # AgentPatternPipeline ctor: (agent, pattern_loader, embedder, ...)
    agent = MagicMock()
    loader = MagicMock()
    loader._loaded = True
    return AgentPatternPipeline(
        agent=agent,
        pattern_loader=loader,
        embedder=MagicMock(),
        retrieval_config=RetrievalConfig(
            analysis_blend_weight=0.7,
            fusion_blend_weight=0.3,
            weight_smoothing_alpha=0.7,
        ),
    )


class TestSelfRagRegression:
    """The canonical-fit rag-applications pattern must enter top-5."""

    def test_self_rag_enters_top_5_for_rag_applications(self):
        """self-rag (top recall match) enters selection with default blend.

        Before: excluded at rank 6+ despite having the highest fusion_score.
        After: blended scoring (0.7/0.3) + smoothing (0.7) gives blended score ~82,
        ranking it at position 4.
        """
        pipeline = _make_pipeline()
        # Realistic quality_attributes from the catalogue JSON files.
        # fusion_scores from the original recall log (RRF, k=60).
        patterns = [
            {
                "name": "self-rag",
                "quality_attributes": {
                    "reliability": 7,
                    "cost_efficiency": 6,
                    "latency": 7,
                    "output_quality": 8,
                    "observability": 6,
                    "safety": 6,
                    "simplicity": 8,
                },
                "fusion_score": 0.0333,  # highest — rank 1 in both retrievers
            },
            {
                "name": "chain-of-thought",
                "quality_attributes": {
                    "reliability": 8,
                    "cost_efficiency": 7,
                    "latency": 9,
                    "output_quality": 9,
                    "observability": 5,
                    "safety": 5,
                    "simplicity": 7,
                },
                "fusion_score": 0.0328,
            },
            {
                "name": "reflexion",
                "quality_attributes": {
                    "reliability": 9,
                    "cost_efficiency": 6,
                    "latency": 8,
                    "output_quality": 9,
                    "observability": 7,
                    "safety": 7,
                    "simplicity": 4,
                },
                "fusion_score": 0.0276,
            },
            {
                "name": "react",
                "quality_attributes": {
                    "reliability": 8,
                    "cost_efficiency": 5,
                    "latency": 9,
                    "output_quality": 9,
                    "observability": 5,
                    "safety": 5,
                    "simplicity": 3,
                },
                "fusion_score": 0.0131,  # lowest
            },
            {
                "name": "supervisor-worker",
                "quality_attributes": {
                    "reliability": 8,
                    "cost_efficiency": 6,
                    "latency": 8,
                    "output_quality": 9,
                    "observability": 6,
                    "safety": 6,
                    "simplicity": 3,
                },
                "fusion_score": 0.0296,
            },
            {
                "name": "agent-as-a-judge",
                "quality_attributes": {
                    "reliability": 9,
                    "cost_efficiency": 6,
                    "latency": 7,
                    "output_quality": 9,
                    "observability": 6,
                    "safety": 6,
                    "simplicity": 3,
                },
                "fusion_score": 0.0272,
            },
        ]
        # RequirementWeights from the original bug-report log
        # (arch scalability/reliability/performance → agent
        #  output_quality/reliability/latency).
        weights = RequirementWeights(
            output_quality=1.0,
            reliability=0.9,
            latency=0.5,
        )

        scored = pipeline._score_patterns(patterns, weights)
        top5 = {s["name"] for s in scored[:5]}

        assert "self-rag" in top5, (
            f"self-rag (top recall match) must enter top-5. "
            f"Got top-5: {top5}"
        )
