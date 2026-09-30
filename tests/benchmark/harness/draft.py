# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT

"""Draft-scenario generation (S11): join run artifacts against ``seed.json``.

Reads one or more benchmark run directories, extracts the *observed* evidence
per scenario (selected patterns, final topology, per-family category), joins
it with the authored seed metadata, and emits **draft** scenario entries for
families whose positional position in the category falls in the holdout
tertile (last third). Drafts are placeholders for human review — they are
never written into ``seed.json`` by the harness; the default ``--output`` is a
sibling draft file and the command prints a review checklist.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import click

from tests.benchmark.harness.config import SEED_PATH, load_corpus


def _family_positions(seed_path: Path) -> dict[str, int]:
    """Per-category family size from the seed (1-based counts)."""
    raw: dict[str, Any] = json.loads(seed_path.read_text(encoding="utf-8"))
    counts: dict[str, int] = defaultdict(int)
    for row in raw["scenarios"]:
        counts[row["category"]] += 1
    return dict(counts)


def _observed_from_run(run_dir: Path) -> dict[str, dict[str, Any]]:
    """scenario_id → observed evidence from one run dir's scenario artifacts."""
    scenarios_dir = run_dir / "scenarios"
    observed: dict[str, dict[str, Any]] = {}
    for path in sorted(scenarios_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        observed[payload["scenario_id"]] = payload
    return observed


def _holdout_position(family_size: int) -> int:
    """First 1-based family position that maps to the holdout tertile."""
    return max(1, (2 * family_size) // 3 + 1)


def build_drafts(
    run_dirs: list[Path],
    seed_path: Path = SEED_PATH,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Build draft scenario entries from run evidence + seed metadata.

    Returns ``(drafts, notes)``; notes carry skipped families and review
    reminders. A family contributes a draft only when every member's run
    artifact is present and at least one member was a real hit (evidence the
    family's requirements text generalizes).
    """
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in seed["scenarios"]:
        families[row["category"]].append(row)

    observed: dict[str, dict[str, Any]] = {}
    for run_dir in run_dirs:
        observed.update(_observed_from_run(run_dir))

    family_sizes = _family_positions(seed_path)
    drafts: list[dict[str, Any]] = []
    notes: list[str] = []

    for category in sorted(families):
        members = families[category]
        holdout_from = _holdout_position(len(members))
        missing = [
            m["scenario_id"]
            for m in members
            if m["scenario_id"] not in observed
        ]
        if missing:
            notes.append(
                f"{category}: skipped ({len(missing)} member(s) without run "
                f"artifacts: {', '.join(sorted(missing))})"
            )
            continue
        hits = [
            observed[m["scenario_id"]]
            for m in members
            if observed[m["scenario_id"]]["hit_at_1"]
        ]
        if not hits:
            notes.append(
                f"{category}: skipped (no member achieved hit_at_1 in the "
                "provided runs; requirements text would not generalize)"
            )
            continue
        exemplar = hits[0]
        exemplar_row = next(
            m for m in members if m["scenario_id"] == exemplar["scenario_id"]
        )
        # Positional index of the exemplar within its family determines the
        # draft's split: only families whose *next* position falls in the
        # holdout tertile produce a holdout draft.
        exemplar_index = members.index(exemplar_row)
        draft_split = "holdout" if exemplar_index + 1 >= holdout_from - 1 else "train"
        drafts.append(
            {
                "scenario_id": f"{category}-generalization-draft",
                "category": category,
                "split": draft_split,
                "requirements": _draft_requirements(exemplar, exemplar_row),
                "domain": exemplar_row["domain"],
                "acceptable_primary": _acceptable_from_observed(exemplar),
                "decoy_domains": list(exemplar_row["decoy_domains"]),
                "scripted_weights": dict(exemplar_row["scripted_weights"]),
                "_review": [
                    "rewrite requirements in your own words before committing",
                    "confirm acceptable_primary against pattern/ records",
                    "decoy_domains copied from exemplar — verify 2+ are true decoys",
                ],
            }
        )
    if not drafts:
        notes.append("no families produced drafts (see skips above)")
    return drafts, notes


def _draft_requirements(observed_row: dict[str, Any], seed_row: dict[str, Any]) -> str:
    """Seed requirements annotated with the observed selection outcome."""
    final = observed_row.get("final_pattern_name") or "<none>"
    quality = observed_row.get("final_quality_score")
    return (
        f"[DRAFT — derived from {seed_row['scenario_id']}] "
        f"{seed_row['requirements']} "
        f"(observed: selected '{final}' at quality {quality}; rewrite this "
        "requirements text before committing.)"
    )


def _acceptable_from_observed(observed_row: dict[str, Any]) -> list[str]:
    """Acceptable-primary seeded from the observed selection, deduped."""
    final = observed_row.get("final_pattern_name")
    return [final] if final else ["<set manually>"]


@click.command(name="draft")
@click.option(
    "--run-dir",
    "run_dirs",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    multiple=True,
    required=True,
    help="Benchmark run directory (repeatable).",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Draft output path (default: <repo>/tests/benchmark/harness/scenarios/draft.json).",
)
@click.option(
    "--validate",
    is_flag=True,
    default=False,
    help="Validate the merged seed+draft corpus after writing (dry-run check).",
)
def draft(run_dirs: tuple[Path, ...], output: Path | None, validate: bool) -> None:
    """Draft new scenarios from run evidence joined against the seed."""
    target = output if output is not None else SEED_PATH.parent / "draft.json"
    drafts, notes = build_drafts(list(run_dirs))
    target.write_text(
        json.dumps({"scenarios": drafts}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    click.echo(f"drafts: {len(drafts)} written to {target}")
    for note in notes:
        click.echo(f"  note: {note}")
    for draft_row in drafts:
        click.echo(f"  draft: {draft_row['scenario_id']} ({draft_row['split']})")
        for reminder in draft_row["_review"]:
            click.echo(f"    - {reminder}")
    if validate:
        merged = json.loads(target.read_text(encoding="utf-8"))
        for row in merged["scenarios"]:
            row.pop("_review", None)
        seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        combined = seed["scenarios"] + merged["scenarios"]
        corpus_probe = load_corpus.__wrapped__ if hasattr(load_corpus, "__wrapped__") else None
        del corpus_probe  # load_corpus reads SEED_PATH directly; validate via schema instead
        from tests.benchmark.harness.config import draft7_validate

        schema: dict[str, Any] = json.loads(
            (SEED_PATH.parent / "scenario.schema.json").read_text(encoding="utf-8")
        )
        errors = draft7_validate({"scenarios": combined}, schema)
        if errors:
            for err in errors:
                click.echo(f"  INVALID: {err}")
            raise SystemExit(1)
        click.echo("  merged seed+draft passes schema validation")
