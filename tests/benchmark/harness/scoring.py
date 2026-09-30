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

"""Selection-quality scoring and statistics for benchmark runs (S4).

Per-scenario metrics (hit@1, recall@K, MRR, topology hit, confidence) and
arm-level statistics (Wilson intervals, exact paired sign test, Newcombe
paired-difference CI, Brier score, ECE, reliability curve, risk-coverage
elbow, robust percentiles). All numerics use the Python standard library.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import quantiles
from typing import NamedTuple

#: Default two-sided confidence level z-value (95%).
Z95: float = 1.959963984540054

#: Quality-attribute keys in canonical order (mirrors the seed schema).
_WEIGHT_KEYS: tuple[str, ...] = (
    "reliability",
    "cost_efficiency",
    "latency",
    "output_quality",
    "observability",
    "safety",
    "simplicity",
)


# ---------------------------------------------------------------------------
# Per-scenario metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioScore:
    """Selection-quality metrics for one scenario in one arm.

    Attributes:
        scenario_id: Scenario identifier.
        hit_at_1: ``final_pattern_name`` is an acceptable primary and the run
            was not a fallback.
        recall: recall@K over analyze-phase selected pattern names for
            K = 1..5 (fraction of acceptable primaries present).
        mrr: reciprocal rank of the first acceptable primary in
            ``selected_patterns`` (0.0 when none appear).
        topology_hit: final topology equals the winner's catalog topology.
        confidence: Top-1 blended analysis score in [0, 1] (calibration
            input for Brier/ECE; 0.5 when unavailable).
        is_fallback: The pipeline reported fallback (no real domain match).
        final_pattern_name: Pattern the pipeline finally selected ("" when
            unresolved).
        acceptable_primary_f1: Hit ⇒ P=1, R=1/|A| (F1 of that pair); a miss
            scores 0/0. |A| is the scenario's acceptable-primary count.
        error: Set when the scenario run failed; the score is a zeroed miss
            and the run counts in every rate (see :func:`score_failure`).
    """

    scenario_id: str
    hit_at_1: bool
    recall: dict[int, float]
    mrr: float
    topology_hit: bool
    confidence: float
    is_fallback: bool
    final_pattern_name: str
    acceptable_primary_f1: float = 0.0
    error: str | None = None


def score_failure(scenario_id: str, error: str) -> ScenarioScore:
    """Zeroed miss for a scenario whose run raised.

    A failed run stays in the arm: it counts as a miss in every rate, carries
    no confidence credit, and its ``error`` surfaces in ``summary.failures``
    and the report's failure table. Swallowing it here is what lets a live
    arm survive one stochastic provider fault instead of aborting.
    """
    return ScenarioScore(
        scenario_id=scenario_id,
        hit_at_1=False,
        recall=dict.fromkeys(range(1, 6), 0.0),
        mrr=0.0,
        topology_hit=False,
        confidence=0.0,
        is_fallback=False,
        final_pattern_name="",
        acceptable_primary_f1=0.0,
        error=error,
    )


def recall_at_k(selected_names: list[str], primaries: list[str], k: int) -> float:
    """Fraction of acceptable primaries within the top-K selected names."""
    if not primaries:
        return 0.0
    top = set(selected_names[:k])
    return sum(1 for name in primaries if name in top) / len(primaries)


def reciprocal_rank(selected_names: list[str], primaries: list[str]) -> float:
    """1-based reciprocal rank of the first acceptable primary; 0.0 if absent."""
    primary_set = set(primaries)
    for index, name in enumerate(selected_names, start=1):
        if name in primary_set:
            return 1.0 / index
    return 0.0


def score_scenario(
    scenario_id: str,
    primaries: list[str],
    winner_topology: str,
    selected_names: list[str],
    top_blended_score: float | None,
    final_pattern_name: str,
    final_topology: str,
    is_fallback: bool,
) -> ScenarioScore:
    """Compute per-scenario metrics from pipeline outputs.

    Args:
        scenario_id: Scenario identifier.
        primaries: Acceptable primary pattern names (winner first).
        winner_topology: Catalog topology of the winner pattern.
        selected_names: Analyze-phase selected pattern names, scored order.
        top_blended_score: Blended score of the top selected pattern
            (``None`` → confidence 0.5).
        final_pattern_name: Pipeline's finally selected pattern name.
        final_topology: Pipeline's final topology.
        is_fallback: Whether the run reported fallback.
    """
    recall = {k: recall_at_k(selected_names, primaries, k) for k in range(1, 6)}
    hit = (not is_fallback) and final_pattern_name in set(primaries)
    confidence = 0.5 if top_blended_score is None else max(0.0, min(1.0, top_blended_score))
    return ScenarioScore(
        scenario_id=scenario_id,
        hit_at_1=hit,
        recall=recall,
        mrr=reciprocal_rank(selected_names, primaries),
        topology_hit=final_topology == winner_topology,
        confidence=confidence,
        is_fallback=is_fallback,
        final_pattern_name=final_pattern_name,
        acceptable_primary_f1=acceptable_primary_f1(hit, len(primaries)),
    )


def acceptable_primary_f1(hit: bool, primaries_count: int) -> float:
    """F1 of the acceptable-primary prediction: hit ⇒ P=1, R=1/|A|; miss ⇒ 0."""
    if not hit or primaries_count <= 0:
        return 0.0
    precision = 1.0
    recall = 1.0 / primaries_count
    return 2.0 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Arm-level summary
# ---------------------------------------------------------------------------


class ReliabilityBin(NamedTuple):
    """One equal-width confidence bin of the reliability curve."""

    lower: float
    upper: float
    samples: int
    mean_confidence: float
    fraction_hit: float


@dataclass
class ArmSummary:
    """Aggregate statistics over one arm's scenario scores."""

    arm: str
    n: int
    hits: int
    hit_rate: float
    wilson_low: float
    wilson_high: float
    mrr_mean: float
    topology_rate: float
    brier: float
    ece: float
    reliability: list[ReliabilityBin] = field(default_factory=list)
    mrr_p50: float | None = None
    mrr_p95: float | None = None
    percentile_note: str = ""
    failures: list[str] = field(default_factory=list)
    acceptable_primary_f1: float = 0.0
    aurc: float | None = None
    risk_at_80: float | None = None
    risk_at_90: float | None = None
    risk_at_100: float | None = None

    def to_dict(self) -> dict[str, object]:
        """JSON-safe dict for manifest/report writing."""
        return {
            "arm": self.arm,
            "n": self.n,
            "hits": self.hits,
            "hit_rate": self.hit_rate,
            "wilson_low": self.wilson_low,
            "wilson_high": self.wilson_high,
            "mrr_mean": self.mrr_mean,
            "topology_rate": self.topology_rate,
            "brier": self.brier,
            "ece": self.ece,
            "reliability": [
                {
                    "lower": b.lower,
                    "upper": b.upper,
                    "samples": b.samples,
                    "mean_confidence": b.mean_confidence,
                    "fraction_hit": b.fraction_hit,
                }
                for b in self.reliability
            ],
            "mrr_p50": self.mrr_p50,
            "mrr_p95": self.mrr_p95,
            "percentile_note": self.percentile_note,
            "acceptable_primary_f1": self.acceptable_primary_f1,
            "aurc": self.aurc,
            "risk_at_80": self.risk_at_80,
            "risk_at_90": self.risk_at_90,
            "risk_at_100": self.risk_at_100,
            "failures": self.failures,
        }


def summarize_arm(arm: str, scores: list[ScenarioScore]) -> ArmSummary:
    """Aggregate one arm's scores into summary statistics."""
    n = len(scores)
    if n == 0:
        return ArmSummary(arm=arm, n=0, hits=0, hit_rate=0.0, wilson_low=0.0,
                          wilson_high=0.0, mrr_mean=0.0, topology_rate=0.0,
                          brier=0.0, ece=0.0)
    hits = sum(1 for s in scores if s.hit_at_1)
    low, high = wilson_interval(hits, n)
    p50, p95, note = percentiles([s.mrr for s in scores])
    confidences = [s.confidence for s in scores]
    correctness = [1.0 if s.hit_at_1 else 0.0 for s in scores]
    return ArmSummary(
        arm=arm,
        n=n,
        hits=hits,
        hit_rate=hits / n,
        wilson_low=low,
        wilson_high=high,
        mrr_mean=sum(s.mrr for s in scores) / n,
        topology_rate=sum(1 for s in scores if s.topology_hit) / n,
        brier=brier_score(confidences, correctness),
        ece=expected_calibration_error(confidences, correctness),
        reliability=reliability_curve(confidences, correctness),
        mrr_p50=p50,
        mrr_p95=p95,
        percentile_note=note,
        failures=[
            f"{s.scenario_id}: {s.error}" for s in scores if s.error is not None
        ],
        acceptable_primary_f1=sum(s.acceptable_primary_f1 for s in scores) / n,
        aurc=area_under_risk_coverage(scores),
        risk_at_80=risk_at_coverage(scores, 0.80),
        risk_at_90=risk_at_coverage(scores, 0.90),
        risk_at_100=risk_at_coverage(scores, 1.00),
    )


# ---------------------------------------------------------------------------
# Statistics primitives
# ---------------------------------------------------------------------------


def wilson_interval(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (two-sided, level z)."""
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    spread = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / denom
    return (max(0.0, center - spread), min(1.0, center + spread))


def binomial_two_sided_p(k: int, n: int) -> float:
    """Exact two-sided binomial test p-value under p=0.5 (sign test)."""
    if n == 0:
        return 1.0
    k_eff = min(k, n - k)

    def tail(count: int) -> float:
        return sum(math.comb(n, i) for i in range(count + 1)) / (2.0**n)

    p = tail(k_eff) * 2.0
    return min(1.0, p)


def sign_test_paired(diffs: list[int]) -> float:
    """Exact two-sided sign test over +1/-1 paired differences.

    Zeros are discarded (ties), per the classic sign test.
    """
    plus = sum(1 for d in diffs if d > 0)
    minus = sum(1 for d in diffs if d < 0)
    return binomial_two_sided_p(plus, plus + minus)


def newcombe_paired_diff_ci(
    n: int, both: int, first_only: int, second_only: int, z: float = Z95
) -> tuple[float, float]:
    """Newcombe (1998) method-10 CI for the paired difference of proportions.

    Args:
        n: Number of paired observations.
        both: Count where BOTH arms succeed (1,1).
        first_only: Count where only the first arm succeeds (1,0).
        second_only: Count where only the second arm succeeds (0,1).
        z: Two-sided normal quantile.

    Returns:
        (low, high) for ``p2 - p1`` where p1 is arm one's success rate.
    """
    if n <= 0:
        return (0.0, 0.0)
    p1 = (both + first_only) / n
    p2 = (both + second_only) / n
    diff = p2 - p1
    l1, u1 = wilson_interval(both + first_only, n, z)
    l2, u2 = wilson_interval(both + second_only, n, z)
    low = diff - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    high = diff + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (max(-1.0, low), min(1.0, high))


def brier_score(confidences: list[float], correctness: list[float]) -> float:
    """Mean squared error of confidence against binary correctness."""
    if not confidences or len(confidences) != len(correctness):
        return 0.0
    return sum((c - y) ** 2 for c, y in zip(confidences, correctness, strict=True)) / len(
        confidences
    )


def reliability_curve(
    confidences: list[float], correctness: list[float], bins: int = 10
) -> list[ReliabilityBin]:
    """Equal-width reliability bins over [0, 1] confidence."""
    if not confidences or len(confidences) != len(correctness):
        return []
    width = 1.0 / bins
    bucket: dict[int, list[tuple[float, float]]] = {}
    for c, y in zip(confidences, correctness, strict=True):
        idx = min(bins - 1, int(c / width))
        bucket.setdefault(idx, []).append((c, y))
    curve: list[ReliabilityBin] = []
    for idx in range(bins):
        members = bucket.get(idx, [])
        if not members:
            continue
        mean_conf = sum(m[0] for m in members) / len(members)
        frac_hit = sum(m[1] for m in members) / len(members)
        curve.append(
            ReliabilityBin(
                lower=idx * width,
                upper=(idx + 1) * width,
                samples=len(members),
                mean_confidence=mean_conf,
                fraction_hit=frac_hit,
            )
        )
    return curve


def expected_calibration_error(
    confidences: list[float], correctness: list[float], bins: int = 10
) -> float:
    """ECE: confidence-weighted absolute gap between accuracy and confidence."""
    curve = reliability_curve(confidences, correctness, bins)
    total = len(confidences)
    if total == 0 or not curve:
        return 0.0
    return sum(b.samples * abs(b.fraction_hit - b.mean_confidence) for b in curve) / total


def percentiles(values: list[float]) -> tuple[float | None, float | None, str]:
    """P50/P95 via inclusive quantiles; (None, None, note) below 4 samples."""
    if len(values) < 4:
        return (None, None, f"percentiles unavailable: {len(values)} samples < 4")
    cuts = quantiles(values, n=20, method="inclusive")
    return (cuts[9], cuts[18], "")


# ---------------------------------------------------------------------------
# Risk-coverage
# ---------------------------------------------------------------------------


class RiskCoveragePoint(NamedTuple):
    """One point on the risk-coverage curve (prefix of confidence-sorted runs)."""

    coverage: float
    risk: float


def risk_coverage_curve(scores: list[ScenarioScore]) -> list[RiskCoveragePoint]:
    """Risk (error rate) as a function of coverage over confidence-sorted prefixes."""
    ordered = sorted(scores, key=lambda s: s.confidence, reverse=True)
    n = len(ordered)
    if n == 0:
        return []
    curve: list[RiskCoveragePoint] = []
    errors = 0
    for k, score in enumerate(ordered, start=1):
        if not score.hit_at_1:
            errors += 1
        curve.append(RiskCoveragePoint(coverage=k / n, risk=errors / k))
    return curve


def risk_coverage_elbow(
    scores: list[ScenarioScore], risk_budget: float = 0.0
) -> RiskCoveragePoint | None:
    """Highest-coverage point whose risk stays within ``risk_budget``.

    Returns ``None`` when even full coverage exceeds the budget.
    """
    curve = risk_coverage_curve(scores)
    within = [pt for pt in curve if pt.risk <= risk_budget]
    return within[-1] if within else None


def area_under_risk_coverage(scores: list[ScenarioScore]) -> float | None:
    """Mean risk over the risk-coverage curve (AURC, lower is better).

    The average of the per-prefix risks, i.e. the discrete integral the
    selective-prediction literature uses; ``None`` for an empty arm so
    "not measured" stays distinguishable from "measured as 0".
    """
    curve = risk_coverage_curve(scores)
    if not curve:
        return None
    return sum(point.risk for point in curve) / len(curve)


def risk_at_coverage(scores: list[ScenarioScore], coverage: float) -> float | None:
    """Risk at the smallest observed coverage reaching ``coverage``."""
    curve = risk_coverage_curve(scores)
    if not curve:
        return None
    for point in curve:
        if point.coverage >= coverage - 1e-9:
            return point.risk
    return curve[-1].risk
