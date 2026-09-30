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

"""Benchmark configuration, scenario model, corpus loading, and validation.

S2 of the stage-0 selection benchmark harness (plan: local://apm-stage0-benchmark-plan.md).

Hand-rolled Draft-07-subset schema validation (the repo has no ``jsonschema``
dependency): supports ``type``, ``required``, ``enum``, ``minLength``,
``minItems``, ``properties``, ``items``, ``additionalProperties`` and the
``$defs``/``$ref`` indirection used by ``scenarios/scenario.schema.json``.
Cross-checks beyond the schema verify that every referenced pattern exists in
the catalog, that domain/decoy slugs are consistent, and that splits are
disjoint per category family.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.config import RerankerConfig, RerankerInnerConfig, RetrievalConfig

_HARNESS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _HARNESS_DIR.parents[2]
PATTERN_DIR = _REPO_ROOT / "pattern"
SCENARIO_DIR = _HARNESS_DIR / "scenarios"
SEED_PATH = SCENARIO_DIR / "seed.json"
SCHEMA_PATH = SCENARIO_DIR / "scenario.schema.json"
RUNS_ROOT = _REPO_ROOT / "data" / "benchmark-runs"

#: The 10 pattern categories (``PatternCategory`` values). Every category
#: family carries exactly 2 scenarios, and each category lives on exactly one
#: split: the pre-existing holdout tertile (observability, safety_control,
#: tool_use) stays holdout, the research_synthesis family is seeded into
#: holdout, and every other family is train — 8 holdout / 12 train scenarios.
CATEGORIES: tuple[str, ...] = (
    "reflection",
    "observability",
    "retrieval",
    "multi_agent",
    "reasoning",
    "tool_use",
    "memory",
    "safety_control",
    "planning",
    "research_synthesis",
)


# ---------------------------------------------------------------------------
# Hand-rolled Draft-07-subset validator
# ---------------------------------------------------------------------------

_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "null": (type(None),),
}


def _type_ok(value: Any, expected: str | list[str]) -> bool:
    """Return True when ``value`` matches the JSON-schema ``type`` keyword."""
    names = expected if isinstance(expected, list) else [expected]
    for name in names:
        types = _TYPES.get(name)
        if types is None:
            continue
        # bool is a subclass of int in Python — exclude it from number/integer.
        if isinstance(value, bool) and name in {"number", "integer"}:
            continue
        if isinstance(value, types):
            return True
    return False


def _resolve_ref(schema: dict[str, Any], ref: str) -> dict[str, Any]:
    """Resolve a local ``#/$defs/Name`` pointer against the schema root."""
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        msg = f"unsupported $ref (only local #/$defs/ supported): {ref}"
        raise ValueError(msg)
    name = ref[len(prefix) :]
    target = schema["$defs"].get(name)
    if not isinstance(target, dict):
        raise TypeError(f"$ref target is not an object: {ref}")
    return target


def _validate_leaf(
    instance: Any, schema: dict[str, Any], path: str
) -> list[str] | None:
    """Validate scalar keywords (``type``/``enum``/``minLength``/``minItems``).

    Returns the error list when a ``type`` mismatch short-circuits the walk,
    else ``None`` (with scalar errors accumulated into ``leaf_errors``).
    """
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type is not None:
        if not isinstance(expected_type, (str, list)):
            msg = f"schema 'type' keyword must be str or list: {expected_type!r}"
            raise TypeError(msg)
        if not _type_ok(instance, expected_type):
            rendered = expected_type if isinstance(expected_type, str) else "/".join(expected_type)
            return [
                f"{path or '<root>'}: expected type {rendered}, got {type(instance).__name__}"
            ]

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path or '<root>'}: {instance!r} not in enum {schema['enum']!r}")

    min_length = schema.get("minLength")
    if isinstance(instance, str) and isinstance(min_length, int) and len(instance) < min_length:
        errors.append(f"{path or '<root>'}: shorter than minLength={min_length}")

    min_items = schema.get("minItems")
    if isinstance(instance, list) and isinstance(min_items, int) and len(instance) < min_items:
        errors.append(f"{path or '<root>'}: fewer than minItems={min_items} items")
    return errors or None


def draft7_validate(
    instance: Any,
    schema: dict[str, Any],
    root: dict[str, Any] | None = None,
    path: str = "",
) -> list[str]:
    """Validate ``instance`` against a Draft-07-subset schema.

    Returns a list of human-readable error strings carrying JSON-pointer-ish
    paths (``scenarios[3].domain`` style). Supports the keywords the harness
    schema actually uses: ``type``, ``required``, ``enum``, ``minLength``,
    ``minItems``, ``properties``, ``items``, ``additionalProperties``,
    ``propertyNames``, ``$defs``/``$ref``.
    """
    root = schema if root is None else root
    if "$ref" in schema:
        target = _resolve_ref(root, str(schema["$ref"]))
        return draft7_validate(instance, target, root, path)

    leaf_errors = _validate_leaf(instance, schema, path)
    if leaf_errors is not None:
        return leaf_errors
    errors = list(leaf_errors or [])

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path or '<root>'}: missing required property {key!r}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        prop_names = schema.get("propertyNames")
        for key, value in instance.items():
            child = f"{path}.{key}" if path else key
            if prop_names is not None:
                errors.extend(draft7_validate(key, prop_names, root, child))
            if key in properties:
                errors.extend(draft7_validate(value, properties[key], root, child))
            elif additional is False:
                errors.append(f"{child}: property not allowed (additionalProperties=false)")
            elif isinstance(additional, dict):
                errors.extend(draft7_validate(value, additional, root, child))

    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            child = f"{path}[{index}]"
            errors.extend(draft7_validate(item, schema["items"], root, child))

    return errors


def load_schema() -> dict[str, Any]:
    """Load and return the bundled scenario schema."""
    loaded: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return loaded


# ---------------------------------------------------------------------------
# Scenario model + corpus loading
# ---------------------------------------------------------------------------


class BenchmarkScenario(BaseModel):
    """One benchmark scenario as emitted in ``scenarios/seed.json``."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    category: str
    split: str
    requirements: str
    domain: str
    acceptable_primary: list[str] = Field(min_length=1)
    decoy_domains: list[str]
    scripted_weights: dict[str, float]


class CorpusStats(BaseModel):
    """Fingerprint of the pattern catalog a run was measured against."""

    pattern_files: int
    corpus_sha256: str


class Corpus:
    """Loaded benchmark corpus: scenarios + catalog fingerprint."""

    def __init__(self, scenarios: list[BenchmarkScenario], stats: CorpusStats) -> None:
        self.scenarios = scenarios
        self.stats = stats

    def scenario_set_sha256(self) -> str:
        """Stable hash over the canonical JSON of the scenario list."""
        payload = json.dumps(
            [s.model_dump() for s in self.scenarios], sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def corpus_sha256(pattern_dir: Path = PATTERN_DIR) -> str:
    """Hash the sorted bytes of every ``*-pattern.json`` in the catalog."""
    digest = hashlib.sha256()
    for path in sorted(pattern_dir.glob("*-pattern.json")):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_corpus(
    seed_path: Path = SEED_PATH,
    schema_path: Path = SCHEMA_PATH,
    pattern_dir: Path = PATTERN_DIR,
) -> Corpus:
    """Load, schema-validate, and cross-check the scenario seed.

    Raises ``ValueError`` with all accumulated problems on any validation or
    cross-check failure.
    """
    raw: dict[str, Any] = json.loads(seed_path.read_text(encoding="utf-8"))
    schema: dict[str, Any] = json.loads(schema_path.read_text(encoding="utf-8"))

    errors = draft7_validate(raw, schema)
    if errors:
        raise ValueError("scenario seed failed schema validation:\n" + "\n".join(errors))

    scenarios = [BenchmarkScenario.model_validate(row) for row in raw["scenarios"]]

    problems = _cross_check(scenarios, pattern_dir)
    if problems:
        raise ValueError("scenario seed failed cross-checks:\n" + "\n".join(problems))

    stats = CorpusStats(
        pattern_files=len(sorted(pattern_dir.glob("*-pattern.json"))),
        corpus_sha256=corpus_sha256(pattern_dir),
    )
    return Corpus(scenarios, stats)


def _load_catalog(pattern_dir: Path) -> dict[str, dict[str, Any]]:
    """Load the pattern catalog keyed by pattern name."""
    catalog: dict[str, dict[str, Any]] = {}
    for path in sorted(pattern_dir.glob("*-pattern.json")):
        pattern = json.loads(path.read_text(encoding="utf-8"))
        catalog[str(pattern.get("name", ""))] = pattern
    return catalog


def _slug_categories(pattern_dir: Path) -> dict[str, set[str]]:
    """Map every suitable_domains slug to the set of categories on it."""
    slug_cats: dict[str, set[str]] = {}
    for pattern in _load_catalog(pattern_dir).values():
        category = str(pattern.get("category", ""))
        for slug in pattern.get("suitable_domains", []):
            slug_cats.setdefault(str(slug), set()).add(category)
    return slug_cats


def _cross_check(
    scenarios: list[BenchmarkScenario], pattern_dir: Path
) -> list[str]:
    """Semantic checks the JSON schema cannot express."""
    problems: list[str] = []
    catalog = _load_catalog(pattern_dir)
    slug_cats = _slug_categories(pattern_dir)

    seen_ids: set[str] = set()
    for scenario in scenarios:
        sid = scenario.scenario_id
        if sid in seen_ids:
            problems.append(f"{sid}: duplicate scenario_id")
        seen_ids.add(sid)

        primaries = set(scenario.acceptable_primary)
        for name in primaries:
            if name not in catalog:
                problems.append(f"{sid}: acceptable_primary {name!r} not in catalog")
                continue
            # Only the winner (primary[0]) must carry the scenario category:
            # listed alternates exist as supporting candidates and may come
            # from other categories.
            if name == scenario.acceptable_primary[0] and catalog[name].get(
                "category"
            ) != scenario.category:
                problems.append(
                    f"{sid}: primary {name!r} category {catalog[name].get('category')!r}"
                    f" != scenario category {scenario.category!r}"
                )

        if scenario.domain not in catalog.get(primaries_next(scenario), {}).get(
            "suitable_domains", []
        ):
            problems.append(
                f"{sid}: domain {scenario.domain!r} not in suitable_domains of"
                f" primary {primaries_next(scenario)!r}"
            )

        # A decoy must not carry ANY pattern whose category is one of the
        # categories of this scenario's acceptable_primary patterns: the
        # labelled primary's own category must not be reachable via a decoy.
        primary_categories = {
            str(catalog[name].get("category", ""))
            for name in primaries
            if name in catalog
        }
        for slug in scenario.decoy_domains:
            leak = slug_cats.get(slug, set()) & primary_categories
            if leak:
                problems.append(
                    f"{sid}: decoy slug {slug!r} carries primary categories"
                    f" {sorted(leak)} (primary {primaries_next(scenario)!r})"
                )

    # Family split disjointness: each category lives on exactly one split.
    by_category: dict[str, set[str]] = {}
    for scenario in scenarios:
        by_category.setdefault(scenario.category, set()).add(scenario.split)
    for category, splits in sorted(by_category.items()):
        if len(splits) > 1:
            problems.append(f"category {category}: scenarios span splits {sorted(splits)}")

    return problems


def primaries_next(scenario: BenchmarkScenario) -> str:
    """The primary whose catalog entry anchors the scenario (the winner)."""
    return scenario.acceptable_primary[0]


# ---------------------------------------------------------------------------
# Offline pins + run identity
# ---------------------------------------------------------------------------


def offline_retrieval_config() -> RetrievalConfig:
    """RetrievalConfig with the deterministic offline pins.

    - ``weight_smoothing_alpha=1.0`` disables convex smoothing so scripted
      weights reach ``_score_patterns`` verbatim.
    - ``min_quality_score=100.0`` disables the design-loop early stop so
      every scenario runs the same number of generate/evaluate rounds.
    - ``use_lean_wire_schema=False`` keeps the full generate schema so the
      LLMProxy bucket names stay stable.
    """
    return RetrievalConfig(
        min_fusion_score=0.0,
        weight_smoothing_alpha=1.0,
        min_quality_score=100.0,
        use_lean_wire_schema=False,
    )


def offline_reranker_config() -> RerankerConfig:
    """RerankerConfig pointing at a never-contacted offline URL.

    The single-node fused recall set skips the reranker entirely; the URL is
    a tripwire — a regression that re-enables reranking fails loudly instead
    of silently changing selection semantics.
    """
    return RerankerConfig(config=RerankerInnerConfig(base_url="http://offline-invalid:8080"))


def new_run_id(mode: str) -> str:
    """Fresh run id: ``bench-<mode>-<utcstamp>-<shortrand>``."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"bench-{mode}-{stamp}-{secrets.token_hex(3)}"


def run_dir(output_root: Path, run_id: str) -> Path:
    """Directory for one run's artifacts."""
    return output_root / run_id
