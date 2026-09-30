# Copyright (c) 2026 Oliver Kowalke
# SPDX-License-Identifier: MIT

"""Run-artifact writing and report rendering for benchmark runs (S6)."""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tests.benchmark.harness.config import new_run_id, run_dir
from tests.benchmark.harness.probes import StageRecorder
from tests.benchmark.harness.scoring import ArmSummary, summarize_arm

SECRETS_FLAGS: tuple[str, ...] = (
    "DEEPSEEK_API_KEY",
    "MINIMAXAI_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)

_ENV_KEYS: tuple[str, ...] = (
    "GENERATOR_PROVIDER",
    "GENERATOR_MODEL",
    "GENERATOR_TOP_K",
    "EMBEDDER_BASE_URL",
    "RERANKER_BASE_URL",
    "REASONING_ENABLED",
    "REASONING_FAIL_FAST",
)

_MODE_NOTES: dict[str, str] = (
    {
        "offline": (
            "Offline arm: retrieval legs are single-slug stubs and the agent is"
            " scripted; timings measure harness overhead only — do not read them"
            " as pipeline performance."
        ),
        "live": (
            "Live arm: real LLM + embedder + sidecars in-process; stage table"
            " attributes wall time to analyze/generate/evaluate/reasoning."
        ),
        "e2e": (
            "E2E arm: MCP wire calls to a deployed server; per-call HTTP wall"
            " time includes the full server pipeline."
        ),
    }
)


class RunHandle:
    """Owns one run directory and its aggregate artifacts."""

    def __init__(
        self, output_root: Path, mode: str, *, out_dir: Path | None = None, force: bool = False
    ) -> None:
        self.mode = mode
        self.run_id = new_run_id(mode)
        if out_dir is None:
            self.dir = run_dir(output_root, self.run_id)
            self.scenarios_dir = self.dir / "scenarios"
            self.dir.mkdir(parents=True, exist_ok=True)
            self.scenarios_dir.mkdir(exist_ok=True)
            self.explicit_out = False
        else:
            # --out names the run directory itself (sibling parity): the run's
            # artifacts land directly in it, not in a generated child. Writing
            # into a non-empty directory is refused unless --force, so a base
            # run is never silently mixed with the previous one.
            self.dir = out_dir
            self.scenarios_dir = self.dir / "scenarios"
            self.explicit_out = True
            existing = sorted(p.name for p in self.dir.iterdir()) if self.dir.is_dir() else []
            if existing and not force:
                raise FileExistsError(
                    f"--out {self.dir} is not empty ({', '.join(existing[:5])}"
                    f"{', …' if len(existing) > 5 else ''}); pass --force to overwrite"
                )
            self.dir.mkdir(parents=True, exist_ok=True)
            self.scenarios_dir.mkdir(exist_ok=True)
        self.recorder = StageRecorder()
        self.started_monotonic = time.monotonic()
        self.aborted = False
        self._extra_manifest: dict[str, Any] = {}

    def note(self, key: str, value: Any) -> None:
        """Attach an extra top-level manifest entry."""
        self._extra_manifest[key] = value

    def write_scenario(
        self,
        scenario_id: str,
        repeat: int,
        payload: dict[str, Any],
    ) -> Path:
        """Write one scenario artifact."""
        path = self.scenarios_dir / f"{scenario_id}#{repeat}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def mark_aborted(self, reason: str) -> Path:
        """Drop the abort marker; compare refuses such runs."""
        self.aborted = True
        path = self.dir / "aborted.json"
        path.write_text(
            json.dumps({"reason": reason, "at": datetime.now(UTC).isoformat()}, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    # -- aggregation -------------------------------------------------------

    def env_snapshot(self) -> dict[str, Any]:
        """Unprefixed env names + secret presence flags (never values)."""
        snapshot: dict[str, Any] = {
            key: os.environ.get(key) for key in _ENV_KEYS if os.environ.get(key) is not None
        }
        snapshot["secret_presence"] = {name: name in os.environ for name in SECRETS_FLAGS}
        return snapshot

    def python_snapshot(self) -> dict[str, Any]:
        """Interpreter/platform fingerprint."""
        return {
            "python": sys.version.split(" ", 1)[0],
            "platform": platform.platform(),
            "implementation": platform.python_implementation(),
        }

    def write_manifest(
        self,
        corpus_sha: str,
        scenario_set_sha: str,
        effective_config: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> Path:
        """Write manifest.json."""
        manifest: dict[str, Any] = {
            "run_id": self.run_id,
            "mode": self.mode,
            "created_utc": datetime.now(UTC).isoformat(),
            "corpus_sha256": corpus_sha,
            "scenario_set_sha256": scenario_set_sha,
            "effective_config": effective_config,
            "env": self.env_snapshot(),
            "python": self.python_snapshot(),
            "aborted": self.aborted,
            "wall_seconds": time.monotonic() - self.started_monotonic,
        }
        manifest.update(self._extra_manifest)
        if extra:
            manifest.update(extra)
        path = self.dir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def write_summary(self, summary: dict[str, Any]) -> Path:
        """Write summary.json (arm summaries keyed by arm name)."""
        path = self.dir / "summary.json"
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def write_warmup(self, warmup: dict[str, Any]) -> Path:
        """Write warmup.json (the untimed warmup scenario's provenance)."""
        path = self.dir / "warmup.json"
        path.write_text(json.dumps(warmup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def write_report(
        self,
        arm_summaries: dict[str, ArmSummary],
        stage_rows: dict[str, dict[str, Any]],
        integrity: list[str],
    ) -> Path:
        """Render report.md: stage table, metrics, calibration, notes."""
        lines: list[str] = []
        lines.append(f"# Benchmark run {self.run_id}")
        lines.append("")
        lines.append(f"Mode: `{self.mode}` — {_MODE_NOTES.get(self.mode, '')}")
        lines.append("")
        lines.append("## Stage attribution")
        lines.append("")
        lines.append(
            "`stage` is the latency bucket, `op` the seam method that produced it."
        )
        lines.append("")
        lines.append("| stage | n | failures | total ms | p50 ms | p95 ms | ops |")
        lines.append("|---|---|---|---|---|---|---|")
        for name in sorted(stage_rows):
            row = stage_rows[name]
            ops = ", ".join(f"{op} x{count}" for op, count in sorted(row["ops"].items()))
            lines.append(
                f"| `{name}` | {row['count']} | {row['failures']} | {row['total_ms']} |"
                f" {row['p50_ms']} | {row['p95_ms']} | {ops} |"
            )
        for arm, summary in sorted(arm_summaries.items()):
            lines.append("")
            lines.append(f"## Arm: {arm}")
            lines.append("")
            lines.append(
                f"- n={summary.n}, hits={summary.hits}, hit_rate="
                f"{summary.hit_rate:.3f} (Wilson {summary.wilson_low:.3f} - {summary.wilson_high:.3f})"
            )
            lines.append(f"- MRR mean={summary.mrr_mean:.3f}")
            lines.append(f"- topology_hit rate={summary.topology_rate:.3f}")
            lines.append(
                f"- Brier={summary.brier:.4f}, ECE={summary.ece:.4f}"
                + (f" ({summary.percentile_note})" if summary.percentile_note else "")
            )
            lines.append(
                "- acceptable-primary F1="
                f"{summary.acceptable_primary_f1:.3f}, AURC="
                + ("n/a" if summary.aurc is None else f"{summary.aurc:.4f}")
                + (
                    ", risk@100="
                    + ("n/a" if summary.risk_at_100 is None else f"{summary.risk_at_100:.3f}")
                )
            )
            if summary.failures:
                lines.append("")
                lines.append("### Failed scenario runs")
                lines.append("")
                for failure in summary.failures:
                    lines.append(f"- {failure}")
        if integrity:
            lines.append("")
            lines.append("## Fixture integrity")
            lines.append("")
            for violation in integrity:
                lines.append(f"- VIOLATION: {violation}")
        else:
            lines.append("")
            lines.append("## Fixture integrity")
            lines.append("")
            lines.append("- OK (no violations)")
        lines.append("")
        path = self.dir / "report.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
