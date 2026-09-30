# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT

"""Harness self-checks (S9).

Exercises every scoring/statistics anchor on known values and validates the
scenario fixture (schema acceptance + tampered-variant rejection). Exit 0
means the harness numbers can be trusted; any anchor failure exits 2.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.benchmark.harness.config import (
    SEED_PATH,
    SCHEMA_PATH,
    load_corpus,
    load_schema,
)
from tests.benchmark.harness.offline import check_integrity, run_corpus
from tests.benchmark.harness.scoring import (
    acceptable_primary_f1,
    area_under_risk_coverage,
    brier_score,
    expected_calibration_error,
    newcombe_paired_diff_ci,
    percentiles,
    recall_at_k,
    reciprocal_rank,
    risk_at_coverage,
    risk_coverage_curve,
    score_failure,
    score_scenario,
    sign_test_paired,
    summarize_arm,
    wilson_interval,
)


def _check(name: str, condition: bool, detail: str = "") -> bool:
    """Report one anchor; returns pass/fail."""
    status = "PASS" if condition else "FAIL"
    suffix = f" ({detail})" if detail else ""
    print(f"  [{status}] {name}{suffix}")
    return condition


def anchor_percentiles() -> bool:
    """Anchors 1-2: percentile cuts and the <4-sample rule."""
    values = [float(i) for i in range(1, 21)]  # 1..20
    p50, p95, _ = percentiles(values)
    ok = _check("percentile cuts p50=10.5 p95=19.05", p50 == 10.5 and p95 == 19.05, f"got {p50}, {p95}")
    small = percentiles([1.0, 2.0, 3.0])
    ok &= _check("percentiles <4 samples -> None + note", small[0] is None and small[2] != "")
    return bool(ok)


def anchor_wilson() -> bool:
    """Anchor 4: Wilson interval against known values."""
    lo, hi = wilson_interval(8, 10)
    ok = _check("Wilson 8/10 in [0.490, 0.943]", abs(lo - 0.490) < 1e-3 and abs(hi - 0.943) < 1e-3, f"got {lo:.4f}, {hi:.4f}")
    return bool(ok)


def anchor_sign_test() -> bool:
    """Anchor 5: sign-test p on symmetric splits."""
    ok = _check("sign test 10/10 wins p=2/1024", abs(sign_test_paired([1] * 10) - 2 / 1024) < 1e-12)
    ok &= _check("sign test all-ties p=1.0", sign_test_paired([0, 0, 0]) == 1.0)
    return bool(ok)


def anchor_newcombe() -> bool:
    """Anchor 6: Newcombe CI sign behaviour."""
    lo, hi = newcombe_paired_diff_ci(10, 10, 0, 0)
    ok = _check("Newcombe no-disagreement CI contains 0", lo <= 0 <= hi, f"[{lo:.3f}, {hi:.3f}]")
    lo2, hi2 = newcombe_paired_diff_ci(10, 0, 0, 10)
    ok &= _check("Newcombe all-disagreement CI excludes 0, clamped", lo2 > 0 and hi2 <= 1.0, f"[{lo2:.3f}, {hi2:.3f}]")
    return bool(ok)


def anchor_recall_mrr() -> bool:
    """Anchors 7-8: recall@K monotonicity and a hand-computed MRR."""
    names = ["x", "primary-a", "y", "primary-b", "z"]
    recalls = [recall_at_k(names, ["primary-a", "primary-b"], k) for k in range(1, 6)]
    monotonic = all(a <= b for a, b in itertools.pairwise(recalls))
    ok = _check("recall@K monotonic non-decreasing", monotonic, str(recalls))
    ok &= _check("MRR hand-computed 0.5", reciprocal_rank(names, ["primary-a"]) == 0.5)
    return bool(ok)


def anchor_fallback_is_miss() -> bool:
    """Anchor 9: fallback poisons hit@1 even with the correct name."""
    score = score_scenario(
        scenario_id="s",
        primaries=["p"],
        winner_topology="single-agent-loop",
        selected_names=["p"],
        top_blended_score=0.9,
        final_pattern_name="p",
        final_topology="single-agent-loop",
        is_fallback=True,
    )
    ok = _check("fallback with correct name = miss", score.hit_at_1 is False)
    return bool(ok)


def anchor_calibration() -> bool:
    """Anchor 10: Brier/ECE extremes on toy vectors."""
    perfect = brier_score([1.0, 0.0], [1.0, 0.0])
    anti = brier_score([0.0, 1.0], [1.0, 0.0])
    ok = _check("Brier perfect=0 anti=1", perfect == 0.0 and anti == 1.0)
    ece_perfect = expected_calibration_error([0.5, 0.5], [1, 0])
    ok &= _check("ECE perfectly calibrated = 0", ece_perfect < 1e-9, f"got {ece_perfect}")
    return bool(ok)


def anchor_risk_coverage() -> bool:
    """Anchor 11: risk non-increasing as coverage grows (sorted by score)."""
    scores = score_scenario("s", ["p"], "t", ["p"], 1.0, "p", "t", False)
    curve = risk_coverage_curve([scores])
    ok = _check("risk-coverage single sample risk<=0.5", all(pt.risk <= 0.5 + 1e-9 for pt in curve), str(curve))
    return bool(ok)


def anchor_schema_validation() -> bool:
    """Anchor 12: seed validates; tampered variants rejected."""
    schema = load_schema()
    raw: dict[str, Any] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    from tests.benchmark.harness.config import draft7_validate

    try:
        errors = draft7_validate(raw, schema)
        ok = _check("schema validator accepts seed.json", not errors, "; ".join(errors[:3]))
    except (TypeError, ValueError) as exc:
        ok = _check("schema validator accepts seed.json", False, str(exc))

    scenarios = raw.get("scenarios", [])
    tampered: list[tuple[str, dict[str, Any]]] = []
    if scenarios:
        base = json.loads(json.dumps(scenarios[0]))
        missing = json.loads(json.dumps(base))
        missing.pop("requirements")
        tampered.append(("missing-required", {"scenarios": [missing]}))
        bad_enum = json.loads(json.dumps(base))
        bad_enum["split"] = "dev"
        tampered.append(("bad-enum", {"scenarios": [bad_enum]}))
        unknown = json.loads(json.dumps(base))
        unknown["extra_key"] = 1
        tampered.append(("unknown-key", {"scenarios": [unknown]}))
        short = json.loads(json.dumps(base))
        short["requirements"] = "too short"
        tampered.append(("short-requirements", {"scenarios": [short]}))
    for name, doc in tampered:
        errors = draft7_validate(doc, schema)
        ok &= _check(f"schema rejects {name}", bool(errors), errors[0] if errors else "accepted")
    return bool(ok)


def anchor_topology_catalog() -> bool:
    """Anchor 13: topology expectation matches the catalog file."""
    corpus = load_corpus()
    catalog: dict[str, dict[str, Any]] = {}
    from tests.benchmark.harness.config import PATTERN_DIR

    for path in sorted(PATTERN_DIR.glob("*-pattern.json")):
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        catalog[data["name"]] = data
    ok = True
    for scenario in corpus.scenarios:
        winner = scenario.acceptable_primary[0]
        entry = catalog.get(winner)
        if entry is None or entry.get("topology") != catalog.get(winner, {}).get("topology"):
            ok = False
    ok &= _check(
        f"primary topology readable from catalog for all {len(corpus.scenarios)} scenarios", ok
    )
    return bool(ok)


def anchor_offline_fixture() -> bool:
    """Offline fixture integrity over the WHOLE corpus (both arms).

    Full corpus, not a subset: a scenario whose domain slug and scripted
    weights cannot steer the scripted arm to its labelled primary only shows
    up when that scenario is actually run, and it then breaks every offline
    arm (``make benchmark-offline`` exiting 2). The 20-scenario run is
    deterministic and costs a few seconds.
    """
    corpus = load_corpus()
    results = asyncio.run(run_corpus(corpus, ["normal", "flipped"]))
    violations = check_integrity(
        [(item.run.arm, item.run.scenario, item.run.score) for item in results]
    )
    ok = _check(
        f"offline fixture over all {len(corpus.scenarios)} scenarios: "
        "normal hits / flipped misses",
        not violations,
        "; ".join(violations[:3]),
    )
    return bool(ok)


def anchor_failure_policy() -> bool:
    """A failed scenario run is a recorded miss, not a swallowed or aborted arm."""
    good = score_scenario("ok", ["p"], "t", ["p"], 0.8, "p", "t", False)
    bad = score_failure("boom", "LLMError: no tool call")
    summary = summarize_arm("live", [good, bad])
    ok = _check(
        "failed run scores as a miss (hit_rate 1/2)",
        summary.hits == 1 and abs(summary.hit_rate - 0.5) < 1e-9,
        f"hits={summary.hits}",
    )
    ok &= _check(
        "failed run carries its error into summary.failures",
        summary.failures == ["boom: LLMError: no tool call"],
        str(summary.failures),
    )
    ok &= _check(
        "failed run carries zero confidence and drags Brier up",
        bad.confidence == 0.0 and summary.brier > 0.0,
        f"confidence={bad.confidence} brier={summary.brier:.4f}",
    )
    ok &= _check(
        "failed run in the normal arm is an integrity violation",
        check_integrity([("normal", _scenario("boom"), bad)]) != [],
    )
    ok &= _check(
        "failed run in the flipped arm is not a violation",
        check_integrity([("flipped", _scenario("boom"), bad)]) == [],
    )
    return bool(ok)


def anchor_provider_death() -> bool:
    """Permanent provider faults abort; stochastic faults stay tolerated."""
    from tests.benchmark.harness.live import is_permanent_provider_death

    dead = [
        (
            'LLMError: LLM provider deepseek error: ERR_009 - litellm.BadRequestError: DeepseekException - '
            '{"error":{"message":"Insufficient Balance (request_id: b5b0466d-1ced-4e03-960e-bec2955f2ccd)",'
            '"type":"unknown_error","param":null,"code":"invalid_request_error"}}'
        ),
        "litellm.RateLimitError: OpenAIException - You have no credits remaining.",
        "litellm.AuthenticationError: invalid_api_key",
        (
            "litellm.APIConnectionError: MinimaxException - "
            '{"type":"error","error":{"type":"authorized_error","message":"login fail: Please carry '
            'the API secret key in the \'Authorization\' field of the request header (1004)",'
            '"http_code":"401"},"request_id":"070c5d498c49c2f41ef47782c804279e"}.'
        ),
    ]
    alive = [
        (
            "LLMError: ERR_009 - Structured output extraction failed: the LLM's tool call "
            "could not be parsed into AgentSystemDesignResponse. overview Field required "
            "[type=missing, input_value={}, input_type=dict]"
        ),
        "asyncio.TimeoutError",
        "litellm.RateLimitError: 429 rate limit exceeded, retry after 30s",
    ]
    ok = _check(
        "provider-death signatures match balance/credits/auth faults",
        all(is_permanent_provider_death(s) for s in dead),
        str([s[:50] for s in dead if not is_permanent_provider_death(s)]),
    )
    ok &= _check(
        "parse faults, timeouts and 429s stay tolerated",
        not any(is_permanent_provider_death(s) for s in alive),
        str([s[:50] for s in alive if is_permanent_provider_death(s)]),
    )
    return bool(ok)


def anchor_tolerant_runner() -> bool:
    """The tolerant runner completes the arm; fail_fast re-raises."""
    from tests.benchmark.harness import offline

    corpus = load_corpus()
    original = offline._run_single

    async def _boom(scenario: Any, arm: str, recorder: Any) -> Any:
        raise RuntimeError("provider exploded")

    offline._run_single = _boom  # type: ignore[assignment]
    try:
        outcomes = asyncio.run(
            offline.run_corpus_tolerant(corpus.scenarios[:2], ["normal"])
        )
    finally:
        offline._run_single = original  # type: ignore[assignment]
    ok = _check(
        "tolerant runner completes every scenario after a failure",
        len(outcomes) == 2 and all(o.error for o in outcomes),
        str([o.error for o in outcomes]),
    )
    offline._run_single = _boom  # type: ignore[assignment]
    try:
        asyncio.run(
            offline.run_corpus_tolerant(corpus.scenarios[:1], ["normal"], fail_fast=True)
        )
    except RuntimeError:
        raised = True
    else:
        raised = False
    finally:
        offline._run_single = original  # type: ignore[assignment]
    ok &= _check("fail_fast re-raises the first failure", raised)
    return bool(ok)


def anchor_compare_verdicts() -> bool:
    """Pre-registered rule: holdout-scoped floor, unmeasured speed = inconclusive."""
    from tests.benchmark.harness.compare import CompareRefusal, compare_runs

    def _run(
        sid: str, split: str, hit: bool, ms: float | None, *, error: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "scenario_id": sid,
            "category": "c",
            "split": split,
            "hit_at_1": hit,
            "e2e_ms": ms,
            "stage_records": (
                [{"stage": "e2e.http", "op": "fastmcp_client.call", "duration_ms": ms, "ok": True}]
                if ms is not None
                else []
            ),
        }
        if error:
            payload["provenance"] = {"error": error}
        return payload

    def _arms(
        *, cand_ms: float | None, cand_hit: bool, error: str | None = None, split: str = "holdout"
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        base = {
            "manifest": {"run_id": "base", "mode": "e2e", "corpus_sha256": "x"},
            "scenarios": {f"h{i}#1": _run(f"h{i}", split, True, 1000.0) for i in range(4)},
        }
        cand = {
            "manifest": {"run_id": "cand", "mode": "e2e", "corpus_sha256": "x"},
            "scenarios": {
                f"h{i}#1": _run(f"h{i}", split, cand_hit, cand_ms, error=error)
                for i in range(4)
            },
        }
        return base, cand

    base, cand = _arms(cand_ms=500.0, cand_hit=True)
    win = compare_runs(base, cand)
    ok = _check("win: 50% holdout p95 gain + matching hit rate",
                win.verdict == "candidate_wins", win.verdict)

    base, cand = _arms(cand_ms=950.0, cand_hit=True)
    loss = compare_runs(base, cand)
    ok &= _check("loss: a 5% gain is below the 15% threshold",
                 loss.verdict == "candidate_loses", loss.verdict)

    base, cand = _arms(cand_ms=None, cand_hit=True)
    unmeasured = compare_runs(base, cand)
    ok &= _check("inconclusive (never a loss) when p95 was not measured",
                  unmeasured.verdict == "inconclusive", unmeasured.verdict)

    base, cand = _arms(cand_ms=500.0, cand_hit=False)
    below = compare_runs(base, cand)
    ok &= _check("loss when the holdout hit rate falls below the baseline floor",
                 below.verdict == "candidate_loses", below.verdict)

    base, cand = _arms(cand_ms=500.0, cand_hit=True, error="LLMError: boom")
    try:
        compare_runs(base, cand)
    except CompareRefusal:
        refused = True
    else:
        refused = False
    ok &= _check("refusal when an arm recorded failed runs", refused)
    allowed = compare_runs(base, cand, allow_mismatch=True)
    ok &= _check("--allow-mismatch overrides the failed-run refusal",
                 allowed.verdict != "")

    train_only, cand_train = _arms(cand_ms=500.0, cand_hit=True, split="train")
    no_holdout = compare_runs(train_only, cand_train)
    ok &= _check("inconclusive when the holdout split has no pairs",
                 no_holdout.verdict == "inconclusive", no_holdout.verdict)
    return bool(ok)


def anchor_nested_attribution() -> bool:
    """A nested seam is not counted twice in the stage table."""
    from tests.benchmark.harness.probes import (
        STAGE_RETRIEVAL_FUSED,
        STAGE_RERANKING,
        StageRecord,
        add_nested_time,
        exclusive_record,
        pop_nested_frame_ns,
        push_nested_frame,
        residual_ms,
        stage_table,
    )

    push_nested_frame()
    started = time.monotonic_ns()
    time.sleep(0.02)
    add_nested_time(12_000_000)  # 12 ms of nested (separately attributed) work
    record = exclusive_record(
        STAGE_RETRIEVAL_FUSED, "HybridPatternRetriever.retrieve", started,
        ok=True, meta={"user_domain": "d"},
    )
    nested = StageRecord(
        STAGE_RERANKING, "SafeTEIReranker.postprocess_nodes", started, 12.0, True, {}
    )
    ok = _check(
        "enclosing record subtracts nested time",
        record.meta.get("nested_ms") == 12.0 and abs(record.duration_ms - 8.0) < 5.0,
        f"exclusive={record.duration_ms:.1f}ms nested={record.meta.get('nested_ms')}",
    )
    ok &= _check(
        "inclusive wall time is preserved in meta",
        record.meta["inclusive_ms"] >= record.duration_ms,
    )
    residual = residual_ms(100.0, stage_table([record, nested]))
    ok &= _check(
        "residual = total - exclusive stage sum",
        abs(residual - 80.0) < 5.0,
        f"residual={residual:.1f}",
    )
    ok &= _check(
        "a top-level call keeps its own duration (no open frame, no charge)",
        pop_nested_frame_ns() == 0
        and add_nested_time(5_000_000) is None
        and pop_nested_frame_ns() == 0,
    )
    return bool(ok)


def anchor_live_dispatch() -> bool:
    """The live driver honours ``--split`` and ``--out`` (a flag that is
    accepted but never forwarded is indistinguishable from a broken filter)."""
    import tempfile

    from tests.benchmark.harness import live as live_module
    from tests.benchmark.harness.main import _run_live

    corpus = load_corpus()
    seen: list[list[str]] = []
    original = live_module.run_live_corpus

    def _stub_config() -> SimpleNamespace:
        """The fields ``_run_live`` echoes into the manifest's effective config."""
        return SimpleNamespace(
            generator=SimpleNamespace(provider="deepseek", config=SimpleNamespace(model="m")),
            embedder=SimpleNamespace(provider="tei", config=SimpleNamespace(base_url="u")),
            reranker=SimpleNamespace(config=SimpleNamespace(base_url="r")),
            reasoning=SimpleNamespace(enabled=False, fail_fast=False),
        )

    async def _capture(scenarios, recorder, **kwargs):  # noqa: ANN001, ANN003
        seen.append([s.scenario_id for s in scenarios])
        return (
            [],
            SimpleNamespace(reasoning_health={}, config=_stub_config()),
            {"enabled": False},
        )

    live_module.run_live_corpus = _capture  # type: ignore[assignment]
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _run_live(
                corpus=corpus,
                limit=3,
                repeat=1,
                output_root=Path(tmp),
                out=Path(tmp) / "explicit",
                warmup=False,
                split="holdout",
            )
    finally:
        live_module.run_live_corpus = original  # type: ignore[assignment]

    ok = _check(
        "live driver runs only the selected split",
        bool(seen) and seen[0] == [s.scenario_id for s in corpus.scenarios if s.split == "holdout"][:3],
        str(seen[:1]),
    )
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "explicit"
        live_module.run_live_corpus = _capture  # type: ignore[assignment]
        try:
            _run_live(corpus=corpus, limit=1, repeat=1, output_root=Path(tmp),
                      out=out_dir, warmup=False, split="holdout")
        finally:
            live_module.run_live_corpus = original  # type: ignore[assignment]
        ok &= _check(
            "--out writes the run into exactly that directory",
            (out_dir / "manifest.json").exists()
            and (out_dir / "scenarios").is_dir()
            and not list(Path(tmp).glob("bench-live-*")),
            str(sorted(p.name for p in out_dir.iterdir())) if out_dir.is_dir() else "missing",
        )
        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
        ok &= _check(
            "manifest records the split that was requested",
            manifest.get("split") == "holdout" and manifest.get("mode") == "live",
            str(manifest.get("split")),
        )
    return bool(ok)


def anchor_f1_and_aurc() -> bool:
    """Hand-computed acceptable-primary F1, AURC and risk@coverage."""
    ok = _check("F1 |A|=1 hit = 1.0", acceptable_primary_f1(True, 1) == 1.0)
    ok &= _check("F1 |A|=2 hit = 2/3", abs(acceptable_primary_f1(True, 2) - 2 / 3) < 1e-12)
    ok &= _check("F1 miss = 0.0", acceptable_primary_f1(False, 2) == 0.0)
    scores = [
        score_scenario("a", ["p"], "t", ["p"], 0.9, "p", "t", False),
        score_scenario("b", ["p"], "t", ["x"], 0.1, "x", "t", False),
    ]
    ok &= _check(
        "AURC = mean per-prefix risk = 0.25",
        abs(area_under_risk_coverage(scores) - 0.25) < 1e-9,
        f"aurc={area_under_risk_coverage(scores)}",
    )
    ok &= _check("risk@100 = full-coverage miss rate",
                 abs(risk_at_coverage(scores, 1.0) - 0.5) < 1e-9)
    ok &= _check("AURC of an empty arm is None (not 0.0)", area_under_risk_coverage([]) is None)
    return bool(ok)


def _scenario(scenario_id: str) -> Any:
    """A minimal scenario stub for the integrity anchors."""
    from tests.benchmark.harness.config import BenchmarkScenario

    return BenchmarkScenario(
        scenario_id=scenario_id,
        category="reasoning",
        split="train",
        requirements="x" * 60,
        domain="complex-reasoning",
        acceptable_primary=["chain-of-thought"],
        decoy_domains=["e-commerce"],
        scripted_weights=dict.fromkeys(
            (
                "reliability", "cost_efficiency", "latency", "output_quality",
                "observability", "safety", "simplicity",
            ),
            1 / 7,
        ),
    )


def anchor_stage_residual() -> bool:
    """Anchor 3: stage table groups by bucket, residual = e2e − Σ stages."""
    from tests.benchmark.harness.probes import (
        STAGE_BUILD_EMBED,
        StageRecord,
        StageRecorder,
        request_stage_total_ms,
        residual_ms,
        residual_note,
        stage_table,
    )

    recorder = StageRecorder()
    samples = [("llm.weights", 10.0), ("llm.generate", 5.0), ("llm.weights", 20.0),
               ("llm.weights", 30.0), ("llm.weights", 40.0), (STAGE_BUILD_EMBED, 900.0)]
    for index, (stage, ms) in enumerate(samples):
        recorder.add(
            StageRecord(
                stage=stage, op=f"{stage}.seam", started_ns=index,
                duration_ms=ms, ok=True, meta={},
            )
        )
    table = stage_table(recorder.records)
    total = request_stage_total_ms(table)
    ok = _check(
        "build stage is excluded from the per-scenario stage total",
        abs(total - 105.0) < 1e-6 and STAGE_BUILD_EMBED in table,
        f"total={total}",
    )
    ok &= _check(
        "residual = e2e - stage total (negative only on overlap)",
        abs(residual_ms(205.0, table) - 100.0) < 1e-6
        and abs(residual_ms(50.0, table) + 55.0) < 1e-6,
    )
    ok &= _check(
        "negative residual carries an overlap note",
        residual_note(-55.0) is not None and residual_note(100.0) is None,
    )
    # 'llm.weights' has 4 samples [10, 20, 30, 40]: inclusive p50=25, p95=38.5.
    row = table["llm.weights"]
    ok &= _check(
        "stage table groups by bucket with p50/p95 and op counts",
        row["count"] == 4
        and row["p50_ms"] == 25.0
        and abs(row["p95_ms"] - 38.5) < 1e-9
        and row["ops"] == {"llm.weights.seam": 4},
        f"row={row}",
    )
    return bool(ok)


def run_selfchecks() -> bool:
    """Run every anchor; returns overall pass/fail."""
    print("benchmark selfcheck:")
    ok = anchor_percentiles()
    ok &= anchor_stage_residual()
    ok &= anchor_wilson()
    ok &= anchor_sign_test()
    ok &= anchor_newcombe()
    ok &= anchor_recall_mrr()
    ok &= anchor_fallback_is_miss()
    ok &= anchor_calibration()
    ok &= anchor_risk_coverage()
    ok &= anchor_schema_validation()
    ok &= anchor_topology_catalog()
    ok &= anchor_offline_fixture()
    ok &= anchor_f1_and_aurc()
    ok &= anchor_failure_policy()
    ok &= anchor_provider_death()
    ok &= anchor_tolerant_runner()
    ok &= anchor_compare_verdicts()
    ok &= anchor_nested_attribution()
    ok &= anchor_live_dispatch()
    return bool(ok)


def main() -> int:
    """Entry point for ``make benchmark-selfcheck``."""
    if not run_selfchecks():
        print("selfcheck FAILED", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
