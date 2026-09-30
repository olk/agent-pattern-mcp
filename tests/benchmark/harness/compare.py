# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT

"""A/B comparison of two benchmark runs (S8).

Paired by ``<scenario_id>#<repeat>``; refuses mismatched corpus sha256 or
mode, runs carrying an ``aborted.json`` marker, and completed arms that
contain failed scenario runs (unless ``allow_mismatch``). The
pre-registered verdict (holdout-only): the candidate wins iff holdout p95
is at least 15% better than the baseline's AND the holdout hit rate is at
least the baseline **holdout** hit rate's Wilson lower bound. Fewer than
4 holdout pairs, an undefined p95, or a zero baseline p95 → inconclusive:
an unmeasured speed leg is never scored as a candidate loss.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tests.benchmark.harness.probes import STAGE_E2E_HTTP
from tests.benchmark.harness.scoring import (
    binomial_two_sided_p,
    newcombe_paired_diff_ci,
    sign_test_paired,
    wilson_interval,
)

EXIT_COMPARE_LOSS = 1
EXIT_COMPARE_REFUSAL = 2

#: Minimum paired holdout samples per arm for a p95 to be defined.
MIN_P95_SAMPLES = 4

#: Pre-registered holdout p95 improvement threshold.
P95_IMPROVEMENT_THRESHOLD = 0.15


class CompareRefusal(ValueError):
    """The comparison cannot be made on these inputs (exit code 2)."""

_VERDICT_WIN = "candidate_wins"
_VERDICT_LOSS = "candidate_loses"
_VERDICT_INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class ScenarioPair:
    """One paired observation across baseline and candidate runs."""

    scenario_id: str
    repeat: int
    category: str
    split: str
    baseline_hit: bool
    candidate_hit: bool
    baseline_ms: float | None
    candidate_ms: float | None


@dataclass(frozen=True)
class CompareResult:
    """Verdict + statistics for one A/B comparison."""

    verdict: str
    baseline_run_id: str
    candidate_run_id: str
    pairs: int
    holdout_pairs: int
    baseline_hit_rate: float
    candidate_hit_rate: float
    baseline_wilson: tuple[float, float]
    candidate_wilson: tuple[float, float]
    holdout_baseline_hit_rate: float
    holdout_candidate_hit_rate: float
    baseline_p95_ms: float | None
    candidate_p95_ms: float | None
    holdout_baseline_p95_ms: float | None
    holdout_candidate_p95_ms: float | None
    p95_improvement: float | None
    sign_test_p: float | None
    newcombe_ci: tuple[float, float] | None
    details: dict[str, Any] = field(default_factory=dict)


def load_run(run_dir: Path) -> dict[str, Any]:
    """Load manifest + scenario artifacts for one run directory.

    Raises ValueError when the run is missing artifacts or was aborted.
    """
    manifest_path = run_dir / "manifest.json"
    if (run_dir / "aborted.json").exists():
        raise CompareRefusal(f"run {run_dir.name} was aborted (aborted.json present)")
    if not manifest_path.exists():
        raise CompareRefusal(f"run {run_dir.name} has no manifest.json")
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    scenarios: dict[str, dict[str, Any]] = {}
    scenarios_dir = run_dir / "scenarios"
    if scenarios_dir.is_dir():
        for path in sorted(scenarios_dir.glob("*.json")):
            key = path.stem
            scenarios[key] = json.loads(path.read_text(encoding="utf-8"))
    return {"manifest": manifest, "scenarios": scenarios, "dir": run_dir}


def pair_runs(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[ScenarioPair]:
    """Pair scenario artifacts by ``<scenario_id>#<repeat>`` key."""
    pairs: list[ScenarioPair] = []
    for key in sorted(set(baseline["scenarios"]) & set(candidate["scenarios"])):
        base = baseline["scenarios"][key]
        cand = candidate["scenarios"][key]
        scenario_id, _, repeat_str = key.rpartition("#")
        base_ms = _scenario_e2e_ms(base)
        cand_ms = _scenario_e2e_ms(cand)
        pairs.append(
            ScenarioPair(
                scenario_id=scenario_id,
                repeat=int(repeat_str) if repeat_str else 1,
                category=str(base.get("category", "")),
                split=str(base.get("split", "train")),
                baseline_hit=bool(base.get("hit_at_1", False)),
                candidate_hit=bool(cand.get("hit_at_1", False)),
                baseline_ms=base_ms,
                candidate_ms=cand_ms,
            )
        )
    return pairs


def _scenario_e2e_ms(artifact: dict[str, Any]) -> float | None:
    """Per-scenario wall clock measured at the run boundary.

    ``e2e_ms`` is the harness's own measurement (the value ``residual_ms`` is
    computed against). The ``e2e.http`` record is the fallback for artifacts
    written before that field existed; a run with neither has no measured
    speed, which the verdict reports as inconclusive rather than a loss.
    """
    measured = artifact.get("e2e_ms")
    if measured is not None:
        return float(measured)
    records: list[Any] = artifact.get("stage_records") or []
    values = [
        float(r["duration_ms"])
        for r in records
        if r.get("stage") == STAGE_E2E_HTTP and r.get("ok")
    ]
    return sum(values) / len(values) if values else None


def compare_runs(  # noqa: PLR0912 — the verdict block states every pre-registered condition explicitly
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    allow_mismatch: bool = False,
) -> CompareResult:
    """Pre-registered A/B verdict over paired scenario artifacts."""
    base_manifest = baseline["manifest"]
    cand_manifest = candidate["manifest"]
    mismatches: list[str] = []
    if base_manifest.get("corpus_sha256") != cand_manifest.get("corpus_sha256"):
        mismatches.append("corpus_sha256 mismatch")
    if base_manifest.get("mode") != cand_manifest.get("mode"):
        mismatches.append(f"mode mismatch: {base_manifest.get('mode')} vs {cand_manifest.get('mode')}")
    if mismatches and not allow_mismatch:
        raise CompareRefusal("; ".join(mismatches))

    pairs = pair_runs(baseline, candidate)
    if not pairs:
        raise CompareRefusal("no overlapping scenario keys between runs")

    # A completed arm that recorded failed scenario runs is not a usable
    # A/B input: the failure already counts as a miss, so comparing it would
    # compare arms of different composition. --allow-mismatch opts in.
    failed = sorted(
        key
        for arm in (baseline, candidate)
        for key, artifact in arm["scenarios"].items()
        if (artifact.get("provenance") or {}).get("error")
    )
    if failed and not allow_mismatch:
        raise CompareRefusal(
            f"{len(failed)} scenario run(s) failed inside the compared arms "
            f"({', '.join(failed[:5])}{', …' if len(failed) > 5 else ''}); "
            "re-run or pass --allow-mismatch"
        )
    holdout = [p for p in pairs if p.split == "holdout"]

    base_p95 = _percentile_ms([p.baseline_ms for p in pairs if p.baseline_ms is not None], 0.95)
    cand_p95 = _percentile_ms([p.candidate_ms for p in pairs if p.candidate_ms is not None], 0.95)
    h_base_p95 = _percentile_ms(
        [p.baseline_ms for p in holdout if p.baseline_ms is not None], 0.95
    )
    h_cand_p95 = _percentile_ms(
        [p.candidate_ms for p in holdout if p.candidate_ms is not None], 0.95
    )

    base_hits = sum(1 for p in pairs if p.baseline_hit)
    cand_hits = sum(1 for p in pairs if p.candidate_hit)
    n = len(pairs)
    base_rate = base_hits / n
    cand_rate = cand_hits / n
    h_base_rate = (
        sum(1 for p in holdout if p.baseline_hit) / len(holdout) if holdout else 0.0
    )
    h_cand_rate = (
        sum(1 for p in holdout if p.candidate_hit) / len(holdout) if holdout else 0.0
    )

    improvements = [
        (b - c) / b
        for b, c in ((p.baseline_ms, p.candidate_ms) for p in holdout)
        if b is not None and c is not None and b > 0
    ]
    p95_improvement: float | None = None
    if h_base_p95 is not None and h_cand_p95 is not None and h_base_p95 > 0:
        p95_improvement = (h_base_p95 - h_cand_p95) / h_base_p95

    sign_deltas = [
        1
        if (p.baseline_ms is not None and p.candidate_ms is not None and p.candidate_ms < p.baseline_ms)
        else (-1 if (p.baseline_ms is not None and p.candidate_ms is not None and p.candidate_ms > p.baseline_ms) else 0)
        for p in pairs
    ]
    nonzero = [d for d in sign_deltas if d != 0]
    sign_p = sign_test_paired(nonzero) if nonzero else None
    wins = sum(1 for d in sign_deltas if d == 1)
    both = sum(1 for p in pairs if p.baseline_hit and p.candidate_hit)
    first_only = sum(1 for p in pairs if p.baseline_hit and not p.candidate_hit)
    second_only = sum(1 for p in pairs if p.candidate_hit and not p.baseline_hit)
    ci = newcombe_paired_diff_ci(n, both, first_only, second_only)

    base_wilson = wilson_interval(base_hits, n)
    cand_wilson = wilson_interval(cand_hits, n)

    h_base_hits = sum(1 for p in holdout if p.baseline_hit)
    h_cand_hits = sum(1 for p in holdout if p.candidate_hit)
    h_base_wilson = wilson_interval(h_base_hits, len(holdout))
    h_cand_wilson = wilson_interval(h_cand_hits, len(holdout))

    # Pre-registered rule, holdout-scoped on BOTH legs: the floor is the
    # baseline holdout hit rate's Wilson lower bound (scoping it to all
    # pairs mixes two sample sets and lowers the bar), and an undefined
    # speed leg is inconclusive, never a loss.
    verdict_reasons: list[str] = []
    if len(holdout) < MIN_P95_SAMPLES:
        verdict_reasons.append(
            f"fewer than {MIN_P95_SAMPLES} paired holdout scenarios "
            f"({len(holdout)}): the rule is undefined"
        )
    elif p95_improvement is None:
        verdict_reasons.append(
            "holdout p95 undefined (no e2e.http timings on one or both arms, "
            "or a zero baseline p95): speed was not measured"
        )
    elif p95_improvement < P95_IMPROVEMENT_THRESHOLD:
        verdict_reasons.append(
            f"holdout p95 improved {100.0 * p95_improvement:.1f}% "
            f"(< {100.0 * P95_IMPROVEMENT_THRESHOLD:.0f}%)"
        )
    if h_cand_rate < h_base_wilson[0]:
        verdict_reasons.append(
            f"candidate holdout hit rate {h_cand_rate:.3f} is below the "
            f"baseline holdout Wilson lower bound {h_base_wilson[0]:.3f}"
        )
    speed_measured = len(holdout) >= MIN_P95_SAMPLES and p95_improvement is not None
    speed_ok = p95_improvement is not None and p95_improvement >= P95_IMPROVEMENT_THRESHOLD
    hit_ok = h_cand_rate >= h_base_wilson[0]
    if not speed_measured:
        verdict = _VERDICT_INCONCLUSIVE
    elif speed_ok and hit_ok:
        verdict = _VERDICT_WIN
    else:
        verdict = _VERDICT_LOSS

    return CompareResult(
        verdict=verdict,
        baseline_run_id=base_manifest.get("run_id", ""),
        candidate_run_id=cand_manifest.get("run_id", ""),
        pairs=n,
        holdout_pairs=len(holdout),
        baseline_hit_rate=base_rate,
        candidate_hit_rate=cand_rate,
        baseline_wilson=base_wilson,
        candidate_wilson=cand_wilson,
        holdout_baseline_hit_rate=h_base_rate,
        holdout_candidate_hit_rate=h_cand_rate,
        baseline_p95_ms=base_p95,
        candidate_p95_ms=cand_p95,
        holdout_baseline_p95_ms=h_base_p95,
        holdout_candidate_p95_ms=h_cand_p95,
        p95_improvement=p95_improvement,
        sign_test_p=sign_p,
        newcombe_ci=ci,
        details={
            "mismatches": mismatches,
            "allow_mismatch": allow_mismatch,
            "paired_p95_improvements_holdout": improvements,
            "sign_test_nonzero_pairs": len(nonzero),
            "binomial_sign_p": binomial_two_sided_p(wins, len(nonzero)) if nonzero else None,
            "holdout_baseline_wilson": list(h_base_wilson),
            "holdout_candidate_wilson": list(h_cand_wilson),
            "holdout_baseline_hits": h_base_hits,
            "holdout_candidate_hits": h_cand_hits,
            "p95_improvement_threshold": P95_IMPROVEMENT_THRESHOLD,
            "min_p95_samples": MIN_P95_SAMPLES,
            "verdict_reasons": verdict_reasons,
        },
    )


def _percentile_ms(values: list[float], q: float) -> float | None:
    """Percentile of wall-time samples (None when empty)."""
    from tests.benchmark.harness.scoring import percentiles

    if not values:
        return None
    if q == 0.5:
        p50, _, _ = percentiles(values)
        return p50
    _, p95, _ = percentiles(values)
    return p95


def verdict_exit_code(result: CompareResult) -> int:
    """0 win/inconclusive (reported), 1 candidate loss."""
    return EXIT_COMPARE_LOSS if result.verdict == _VERDICT_LOSS else 0
