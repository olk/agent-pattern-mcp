# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT

"""Benchmark CLI entry point (S6).

Runs a benchmark corpus in one of three modes (offline / live / e2e),
writes the run directory (manifest, per-scenario artifacts, summary,
report), and enforces fixture integrity for the offline mode.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import click

from tests.benchmark.harness.config import load_corpus
from tests.benchmark.harness.offline import EXIT_INTEGRITY_FAILURE
from tests.benchmark.harness.probes import (
    StageRecord,
    StageRecorder,
    percentile_fields,
    request_stage_total_ms,
    residual_ms,
    residual_note,
    stage_table as build_stage_table,
)
from tests.benchmark.harness.runner import RunHandle
from tests.benchmark.harness.scoring import summarize_arm


#: Exit code for a refused run (same convention as `compare`).
EXIT_REFUSAL = 2

#: Exit code for a live arm aborted because the generator provider is
#: permanently dead (balance/credits/quota/auth).
EXIT_PROVIDER_DEAD = 3


def _corpus_fingerprint(corpus: Any) -> tuple[str, str]:
    """Corpus sha256 + scenario-set sha256 (seed bytes)."""
    scenario_set_sha = corpus.scenario_set_sha256
    return corpus.corpus_sha256, scenario_set_sha


@click.group()
def main() -> None:
    """Stage-0 selection benchmark harness."""


@click.command(name="run")
@click.option(
    "--mode",
    type=click.Choice(["offline", "live", "e2e"]),
    default="offline",
    show_default=True,
    help="Benchmark mode.",
)
@click.option("--limit", type=int, default=None, help="Cap scenarios (smoke runs).")
@click.option("--flip", is_flag=True, default=False, help="Offline: feed decoy slug instead of domain.")
@click.option("--repeat", type=int, default=1, show_default=True, help="Repetitions per scenario.")
@click.option(
    "--split",
    type=click.Choice(["all", "train", "holdout"]),
    default="all",
    show_default=True,
    help="Restrict the corpus to one split.",
)
@click.option(
    "--fail-fast",
    is_flag=True,
    default=False,
    help="Abort on the first scenario failure (default: record it and continue).",
)
@click.option(
    "--no-warmup",
    is_flag=True,
    default=False,
    help="Skip the untimed warmup scenario (live mode).",
)
@click.option(
    "--log-level",
    default="warning",
    show_default=True,
    help="Root log level for the harness process (also applied to bm25s).",
)
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the run into exactly this directory (refuses a non-empty one without --force).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Allow writing into a non-empty --out directory.",
)
@click.option(
    "--output-root",
    type=click.Path(path_type=Path),
    default=Path("data/benchmark-runs"),
    show_default=True,
    help="Run directory parent.",
)
@click.option("--call-timeout", type=int, default=None, help="E2E per-call timeout (s).")
@click.option("--dry-run", is_flag=True, default=False, help="Draft mode (not yet implemented).")
@click.option("--mcp-url", type=str, default=None, help="E2E MCP endpoint.")
def run(
    mode: str,
    limit: int | None,
    flip: bool,
    repeat: int,
    split: str,
    fail_fast: bool,
    no_warmup: bool,
    log_level: str,
    out: Path | None,
    force: bool,
    output_root: Path,
    call_timeout: int | None,
    dry_run: bool,
    mcp_url: str | None,
) -> None:
    """Run the Stage-0 selection benchmark and write a run directory."""
    _configure_logging(log_level)
    if out is not None and out.is_dir() and any(out.iterdir()) and not force:
        click.echo(
            f"refusal: --out {out} is not empty; pass FORCE=1 to overwrite it in place"
        )
        raise SystemExit(EXIT_REFUSAL)
    corpus = load_corpus()
    if dry_run:
        click.echo("dry-run: corpus loads and validates; no pipeline run performed")
        return
    if mode == "e2e":
        _run_e2e(
            corpus=corpus,
            limit=limit,
            repeat=repeat,
            output_root=output_root,
            out=out,
            force=force,
            call_timeout=1500.0 if call_timeout is None else float(call_timeout),
            mcp_url=mcp_url,
            split=split,
            fail_fast=fail_fast,
        )
        return
    if mode == "live":
        _run_live(
            corpus=corpus,
            limit=limit,
            repeat=repeat,
            output_root=output_root,
            out=out,
            force=force,
            warmup=not no_warmup,
            fail_fast=fail_fast,
            split=split,
        )
        return
    _run_offline(
        corpus=corpus,
        limit=limit,
        flip=flip,
        repeat=repeat,
        output_root=output_root,
        out=out,
        force=force,
        split=split,
        fail_fast=fail_fast,
    )


def _configure_logging(level: str) -> None:
    """Set the root logger, its handlers, and bm25s (which re-pins at import)."""
    import logging

    resolved = getattr(logging, level.upper(), logging.WARNING)
    root = logging.getLogger()
    root.setLevel(resolved)
    for handler in root.handlers:
        handler.setLevel(resolved)
    logging.getLogger("bm25s").setLevel(resolved)


def _run_offline(
    corpus: Any,
    limit: int | None,
    flip: bool,
    repeat: int,
    output_root: Path,
    out: Path | None = None,
    force: bool = False,
    split: str = "all",
    fail_fast: bool = False,
) -> None:
    """Offline mode: scripted arms, integrity-checked."""
    from tests.benchmark.harness.offline import run_corpus_tolerant

    mode = "offline"
    arms = ["flipped"] if flip else ["normal"]
    handle = RunHandle(output_root, mode, out_dir=out, force=force)
    handle.note("flip", flip)
    handle.note("arms", arms)
    handle.note("repeat", repeat)
    handle.note("split", split)
    handle.note("fail_fast", fail_fast)
    scenarios = _select(corpus, limit, split)
    outcomes: list[Any] = []
    latency_rows: list[dict[str, Any]] = []
    integrity: list[str] = []
    try:
        for repeat_index in range(1, repeat + 1):
            repeat_outcomes = asyncio.run(
                run_corpus_tolerant(scenarios, arms, fail_fast=fail_fast)
            )
            outcomes.extend(repeat_outcomes)
            for item in repeat_outcomes:
                handle.write_scenario(
                    item.scenario.scenario_id,
                    repeat_index,
                    _offline_payload(item),
                )
                latency_rows.append(_latency_row(item, repeat_index))
        arm_summaries = {
            arm: summarize_arm(arm, [o.score for o in outcomes if o.arm == arm])
            for arm in arms
        }
        integrity = _offline_integrity(outcomes, arms)
        handle.write_summary(
            {
                **{arm: summary.to_dict() for arm, summary in arm_summaries.items()},
                "latency": _latency_summary(latency_rows),
            }
        )
        all_records = [r for item in outcomes for r in item.recorder.records]
        handle.write_manifest(
            corpus_sha=corpus.stats.corpus_sha256,
            scenario_set_sha=corpus.scenario_set_sha256(),
            effective_config={
                "retrieval": _offline_retrieval_config_dump(),
                "reranker": _offline_reranker_config_dump(),
                "limit": limit,
                "repeat": repeat,
                "split": split,
            },
            extra={"failures": {a: s.failures for a, s in arm_summaries.items()}},
        )
        handle.write_report(arm_summaries, build_stage_table(all_records), integrity)
    except Exception as exc:
        handle.mark_aborted(f"{type(exc).__name__}: {exc}")
        raise
    if integrity:
        click.echo("fixture integrity FAILED:")
        for violation in integrity:
            click.echo(f"  - {violation}")
        raise SystemExit(EXIT_INTEGRITY_FAILURE)
    for arm, summary in arm_summaries.items():
        _echo_arm_summary(summary, label=arm)
    click.echo(f"run dir: {handle.dir}")


def _offline_integrity(outcomes: list[Any], arms: list[str]) -> list[str]:
    """Scripted-fixture integrity over the tolerant outcomes.

    The normal arm must hit and the flipped arm must miss; a failed run
    counts as a miss in both directions, so a broken fixture cannot hide.
    """
    from tests.benchmark.harness.offline import check_integrity

    return check_integrity([(o.arm, o.scenario, o.score) for o in outcomes])


def _offline_payload(outcome: Any) -> dict[str, Any]:
    """Per-scenario offline artifact (flat fields, like the live artifact)."""
    scenario = outcome.scenario
    score = outcome.score
    payload: dict[str, Any] = {
        "scenario_id": scenario.scenario_id,
        "arm": outcome.arm,
        "category": scenario.category,
        "split": scenario.split,
        "final_pattern_name": score.final_pattern_name,
        "is_fallback": score.is_fallback,
        "hit_at_1": score.hit_at_1,
        "recall": {str(k): v for k, v in score.recall.items()},
        "mrr": score.mrr,
        "topology_hit": score.topology_hit,
        "confidence": score.confidence,
        "provenance": {"error": outcome.error},
        "stage_records": [_record_dict(r) for r in outcome.recorder.records],
    }
    payload.update(_latency_block(outcome.recorder.records, outcome.e2e_ms))
    if outcome.result is not None:
        result = outcome.result.result
        payload["final_quality_score"] = getattr(result, "final_quality_score", None)
        payload["attempts"] = getattr(result, "attempts", None)
        payload["matched_domains"] = [
            dict(m) if not isinstance(m, dict) else m
            for m in (getattr(result, "matched_domains", None) or [])
        ]
    return payload


def _offline_retrieval_config_dump() -> dict[str, Any]:
    """Effective offline retrieval config as JSON-safe dict."""
    from tests.benchmark.harness.config import offline_retrieval_config

    return offline_retrieval_config().model_dump()


def _run_live(
    corpus: Any,
    limit: int | None,
    repeat: int,
    output_root: Path,
    out: Path | None = None,
    force: bool = False,
    warmup: bool = True,
    fail_fast: bool = False,
    split: str = "all",
) -> None:
    """Live mode: real pipeline, real catalog, probes attached."""
    from tests.benchmark.harness.live import ProviderDeathError, run_live_corpus

    mode = "live"
    handle = RunHandle(output_root, mode, out_dir=out, force=force)
    handle.note("repeat", repeat)
    handle.note("warmup", warmup)
    handle.note("fail_fast", fail_fast)
    handle.note("split", split)
    scores: list[Any] = []
    all_records: list[StageRecord] = []
    reasoning_health: dict[str, str] = {}
    effective_config: dict[str, Any] = {}
    warmup_record: dict[str, Any] = {"enabled": False}
    latency_rows: list[dict[str, Any]] = []
    try:
        for repeat_index in range(1, repeat + 1):
            outcomes, components, warmup_record = asyncio.run(
                run_live_corpus(
                    _select(corpus, limit, split),
                    handle.recorder,
                    warmup=warmup,
                    fail_fast=fail_fast,
                )
            )
            reasoning_health = components.reasoning_health
            effective_config = {
                "generator_provider": components.config.generator.provider,
                "generator_model": components.config.generator.config.model,
                "embedder_provider": components.config.embedder.provider,
                "embedder_base_url": components.config.embedder.config.base_url,
                "reranker_base_url": components.config.reranker.config.base_url,
                "reasoning_enabled": components.config.reasoning.enabled,
                "reasoning_fail_fast": components.config.reasoning.fail_fast,
                "limit": limit,
                "repeat": repeat,
            }
            for outcome in outcomes:
                scores.append(outcome.score)
                all_records.extend(outcome.records)
                handle.write_scenario(
                    outcome.scenario.scenario_id,
                    repeat_index,
                    _live_payload(outcome),
                )
                latency_rows.append(_latency_row(outcome, repeat_index))
        arm_summary = summarize_arm("live", scores)
        handle.write_summary(
            {"live": arm_summary.to_dict(), "latency": _latency_summary(latency_rows)}
        )
        handle.write_warmup(warmup_record)
        handle.write_manifest(
            corpus_sha=corpus.stats.corpus_sha256,
            scenario_set_sha=corpus.scenario_set_sha256(),
            effective_config=effective_config,
            extra={
                "reasoning_health": reasoning_health,
                "warmup": warmup_record,
                "failures": arm_summary.failures,
            },
        )
        handle.write_report({"live": arm_summary}, build_stage_table(all_records), [])
    except ProviderDeathError as exc:
        handle.mark_aborted(f"ProviderDeathError: {exc}")
        click.echo(f"ABORTED — generator provider permanently failed: {exc}")
        click.echo(
            "Fix: top up the provider account or switch GENERATOR_* env "
            "(see tests/benchmark/README.md)."
        )
        raise SystemExit(EXIT_PROVIDER_DEAD) from exc
    except Exception as exc:
        handle.mark_aborted(f"{type(exc).__name__}: {exc}")
        raise
    _echo_arm_summary(arm_summary)
    click.echo(f"reasoning_health: {reasoning_health or 'disabled'}")
    click.echo(f"run dir: {handle.dir}")


def _live_payload(outcome: Any) -> dict[str, Any]:
    """Per-scenario live artifact: this scenario's own records only."""
    scenario = outcome.scenario
    payload: dict[str, Any] = {
        "scenario_id": scenario.scenario_id,
        "arm": "live",
        "category": scenario.category,
        "split": scenario.split,
        "score": dict(outcome.score.__dict__),
        "provenance": {"error": outcome.error},
        "stage_records": [_record_dict(record) for record in outcome.records],
    }
    payload.update(_latency_block(outcome.records, outcome.e2e_ms))
    if outcome.run is not None:
        result = outcome.run.result
        payload.update(
            {
                "final_pattern_name": outcome.score.final_pattern_name,
                "is_fallback": outcome.score.is_fallback,
                "hit_at_1": outcome.score.hit_at_1,
                "recall": {str(k): v for k, v in outcome.score.recall.items()},
                "mrr": outcome.score.mrr,
                "topology_hit": outcome.score.topology_hit,
                "confidence": outcome.score.confidence,
                "final_quality_score": getattr(result, "final_quality_score", None),
                "attempts": getattr(result, "attempts", None),
                "matched_domains": [
                    dict(m) if not isinstance(m, dict) else m
                    for m in (getattr(result, "matched_domains", None) or [])
                ],
            }
        )
    return payload


def _run_e2e(
    corpus: Any,
    limit: int | None,
    repeat: int,
    output_root: Path,
    call_timeout: float,
    mcp_url: str | None,
    out: Path | None = None,
    force: bool = False,
    split: str = "all",
    fail_fast: bool = False,
) -> None:
    """E2E mode: wire calls to the deployed MCP server."""
    from tests.benchmark.harness.e2e import resolve_mcp_url, run_e2e_corpus_tolerant

    mode = "e2e"
    url = resolve_mcp_url(mcp_url)
    scenarios = _select(corpus, limit, split)
    handle = RunHandle(output_root, mode, out_dir=out, force=force)
    handle.note("mcp_url", url)
    handle.note("call_timeout_s", call_timeout)
    handle.note("repeat", repeat)
    handle.note("split", split)
    handle.note("fail_fast", fail_fast)
    outcomes: list[Any] = []
    latency_rows: list[dict[str, Any]] = []
    try:
        for repeat_index in range(1, repeat + 1):
            e2e_outcomes = asyncio.run(
                run_e2e_corpus_tolerant(
                    scenarios, url, call_timeout, fail_fast=fail_fast
                )
            )
            outcomes.extend(e2e_outcomes)
            for item in e2e_outcomes:
                handle.write_scenario(
                    item.scenario.scenario_id,
                    repeat_index,
                    _e2e_payload(item),
                )
                latency_rows.append(_latency_row(item, repeat_index))
        arm_summary = summarize_arm("e2e", [o.score for o in outcomes])
        handle.write_summary(
            {"e2e": arm_summary.to_dict(), "latency": _latency_summary(latency_rows)}
        )
        all_records = [r for item in outcomes for r in item.recorder.records]
        handle.write_manifest(
            corpus_sha=corpus.stats.corpus_sha256,
            scenario_set_sha=corpus.scenario_set_sha256(),
            effective_config={
                "limit": limit,
                "repeat": repeat,
                "call_timeout_s": call_timeout,
                "split": split,
                "mcp_url": url,
            },
            extra={"failures": arm_summary.failures},
        )
        handle.write_report({"e2e": arm_summary}, build_stage_table(all_records), [])
    except Exception as exc:
        handle.mark_aborted(f"{type(exc).__name__}: {exc}")
        raise
    _echo_arm_summary(arm_summary)
    click.echo(f"run dir: {handle.dir}")


def _e2e_payload(outcome: Any) -> dict[str, Any]:
    """Per-scenario e2e artifact."""
    records = outcome.recorder.records
    payload: dict[str, Any] = {
        "scenario_id": outcome.scenario.scenario_id,
        "arm": "e2e",
        "category": outcome.scenario.category,
        "split": outcome.scenario.split,
        "output": outcome.output,
        "score": dict(outcome.score.__dict__),
        "provenance": {"error": outcome.error},
        "stage_records": [_record_dict(r) for r in records],
    }
    payload.update(_latency_block(records, outcome.e2e_ms))
    return payload


def _latency_block(records: list[StageRecord], e2e_ms: float | None) -> dict[str, Any]:
    """Per-scenario latency: aggregated stage table, totals and residual.

    The scenario wall clock (``e2e_ms``) is measured at the run boundary, not
    recorded as a stage — otherwise the stage sum would include the total it is
    subtracted from. ``residual_ms`` is what the observed seams do not explain.
    """
    table = build_stage_table(records)
    if e2e_ms is None:
        return {
            "e2e_ms": None,
            "stages": table,
            "stage_total_ms": request_stage_total_ms(table),
            "residual_ms": None,
            "residual_note": "scenario failed before completion; no timing is attributable",
        }
    residual = residual_ms(e2e_ms, table)
    return {
        "e2e_ms": e2e_ms,
        "stages": table,
        "stage_total_ms": request_stage_total_ms(table),
        "residual_ms": residual,
        "residual_note": residual_note(residual),
    }


def _latency_row(outcome: Any, repeat: int) -> dict[str, Any]:
    """One scenario's latency row for the run-level summary."""
    records = (
        outcome.records if hasattr(outcome, "records") else outcome.recorder.records
    )
    table = build_stage_table(records)
    e2e = getattr(outcome, "e2e_ms", None)
    return {
        "scenario_id": outcome.scenario.scenario_id,
        "repeat": repeat,
        "e2e_ms": e2e,
        "stage_total_ms": request_stage_total_ms(table),
        "residual_ms": None if e2e is None else residual_ms(e2e, table),
    }


def _latency_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Run-level latency block: e2e/residual distributions, stage table, overlap note."""
    from tests.benchmark.harness.probes import stage_table as aggregate_stage_table

    e2e_values = [float(r["e2e_ms"]) for r in rows if r.get("e2e_ms") is not None]
    residuals = [float(r["residual_ms"]) for r in rows if r.get("residual_ms") is not None]
    negative = [r for r in residuals if r < 0.0]
    return {
        "e2e_ms": percentile_fields(e2e_values),
        "residual_ms": percentile_fields(residuals),
        "negative_residual_scenarios": len(negative),
        "residual_note": residual_note(negative[0]) if negative else None,
        "per_scenario": rows,
    }


def _record_dict(record: StageRecord) -> dict[str, Any]:
    """JSON-safe stage record for a scenario artifact."""
    return {
        "stage": record.stage,
        "op": record.op,
        "duration_ms": round(record.duration_ms, 3),
        "ok": record.ok,
        "meta": record.meta,
    }


def _select(corpus: Any, limit: int | None, split: str) -> list[Any]:
    """Corpus scenarios filtered by split, then capped by ``limit``."""
    scenarios = (
        list(corpus.scenarios)
        if split == "all"
        else [s for s in corpus.scenarios if s.split == split]
    )
    return scenarios if limit is None else scenarios[:limit]


def _echo_arm_summary(summary: Any, label: str | None = None) -> None:
    """Print one arm's headline metrics, including recorded failures."""
    name = label or summary.arm
    click.echo(
        f"{name}: n={summary.n} hits={summary.hits} hit_rate={summary.hit_rate:.3f}"
        f" mrr={summary.mrr_mean:.3f} topology={summary.topology_rate:.3f}"
        f" f1={summary.acceptable_primary_f1:.3f}"
    )
    if summary.failures:
        click.echo(f"  failed scenario runs: {len(summary.failures)}")
        for failure in summary.failures:
            click.echo(f"    - {failure}")


def _offline_reranker_config_dump() -> dict[str, Any]:
    """Effective offline reranker config as JSON-safe dict."""
    from tests.benchmark.harness.config import offline_reranker_config

    return offline_reranker_config().model_dump()


@click.command(name="compare")
@click.argument("baseline_dir", type=click.Path(exists=True, path_type=Path))
@click.argument("candidate_dir", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--allow-mismatch",
    is_flag=True,
    default=False,
    help="Permit corpus/mode mismatch (recorded in output).",
)
def compare(baseline_dir: Path, candidate_dir: Path, allow_mismatch: bool) -> None:
    """A/B compare a BASELINE run dir against a CANDIDATE run dir."""
    from tests.benchmark.harness.compare import (
        EXIT_COMPARE_REFUSAL,
        CompareRefusal,
        compare_runs,
        load_run,
        verdict_exit_code,
    )

    try:
        baseline = load_run(baseline_dir)
        candidate = load_run(candidate_dir)
        result = compare_runs(baseline, candidate, allow_mismatch=allow_mismatch)
    except CompareRefusal as exc:
        click.echo(f"refusal: {exc}")
        raise SystemExit(EXIT_COMPARE_REFUSAL) from exc
    click.echo(f"verdict: {result.verdict}")
    click.echo(
        f"pairs={result.pairs} holdout={result.holdout_pairs} "
        f"hit base={result.baseline_hit_rate:.3f} cand={result.candidate_hit_rate:.3f}"
    )
    click.echo(
        f"p95 base={result.baseline_p95_ms} cand={result.candidate_p95_ms} "
        f"holdout improvement="
        f"{None if result.p95_improvement is None else round(result.p95_improvement, 4)}"
    )
    click.echo(f"sign-test p={result.sign_test_p} newcombe CI={result.newcombe_ci}")
    for reason in result.details.get("verdict_reasons", []):
        click.echo(f"reason: {reason}")
    click.echo(json.dumps(result.details, indent=2, sort_keys=True))
    raise SystemExit(verdict_exit_code(result))


main.add_command(run)
main.add_command(compare)
from tests.benchmark.harness.draft import draft as _draft_command  # noqa: E402

main.add_command(_draft_command)


if __name__ == "__main__":
    main()
