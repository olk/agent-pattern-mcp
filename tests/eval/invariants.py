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
L9 structural invariants over LLM output (testing-strategies.md §3.9a).

The mechanizable T1.5 slice between "machinery fails on no input" (T1) and
"the design is good" (T2, unmechanizable): a generated agent system design
either is well-formed and internally consistent or it is not — no semantic
judgment required. These invariants are REGRESSION oracles for the product:
a prompt edit, model swap, or pipeline change that silently drops section
completeness or breaks reference closure fails the corpus.

The boundary sentence (part of the layer's claim template): this layer
certifies WELL-FORMEDNESS and INTERNAL CONSISTENCY — never whether the
design is good. It is the cheap mechanical precursor to human review, not
a substitute for T2 rubrics.
"""

import json
from pathlib import Path
from typing import Any

from src.schemas.enums import AgentTopology

REPO_ROOT = Path(__file__).resolve().parents[2]
PATTERN_DIR = REPO_ROOT / "pattern"

# Score ranges as declared by the schemas (src/schemas/design.py,
# src/schemas/agent_system.py). Keep in sync with the Field constraints.
SCORE_RANGE = (0.0, 100.0)

_VALID_TOPOLOGIES = frozenset(t.value for t in AgentTopology)


def catalogue_pattern_names() -> set[str]:
    """Pattern names the design may cite (from the pattern directory)."""
    names: set[str] = set()
    for path in PATTERN_DIR.glob("*-pattern.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "name" in data:
            names.add(str(data["name"]))
    return names


def check_invariants(design: dict[str, Any], pattern_names: set[str] | None = None) -> list[str]:
    """Run every structural invariant; returns the list of violations.

    A non-empty list means the LLM output drifted: the triggering change
    (prompt/model/pipeline) blocks until triaged (prompt bug vs corpus
    staleness). An empty list on a KNOWN-BAD design would mean the invariants
    are vacuous — the offline vacuity test guards that.
    """
    violations: list[str] = []

    overview: dict[str, Any] = design.get("overview") or {}
    agents: list[dict[str, Any]] = list(design.get("agents") or [])
    relationships: list[dict[str, Any]] = list(design.get("relationships") or [])
    tool_contracts: list[dict[str, Any]] = list(design.get("tool_contracts") or [])
    messages: list[dict[str, Any]] = list(design.get("message_contracts") or [])
    quality: dict[str, Any] = design.get("quality_attributes") or {}

    agent_ids = [str(a.get("id")) for a in agents]

    # INV-1: section completeness — required sections present and non-empty.
    if not overview:
        violations.append("INV-1: overview section missing/empty")
    if not agents:
        violations.append("INV-1: agents section missing/empty")
    if not quality:
        violations.append("INV-1: quality_attributes section missing/empty")

    # INV-2: agent ids unique and well-formed (dangling references would
    # otherwise be ambiguous).
    if len(agent_ids) != len(set(agent_ids)):
        violations.append("INV-2: duplicate agent ids")

    # INV-3: every relationship endpoint resolves to a declared agent.
    id_set = set(agent_ids)
    for rel in relationships:
        for endpoint in ("source", "target"):
            node = str(rel.get(endpoint))
            if node not in id_set:
                violations.append(f"INV-3: relationship {endpoint}={node!r} unresolved")

    # INV-4: every message contract names a producer AND at least one consumer,
    # both declared agents.
    for message in messages:
        producer = str(message.get("published_by"))
        if producer not in id_set:
            violations.append(
                f"INV-4: message {message.get('message_name')!r} producer unresolved"
            )
        consumers: list[Any] = list(message.get("consumed_by") or [])
        if not consumers:
            violations.append(
                f"INV-4: message {message.get('message_name')!r} has no consumer"
            )
        for consumer in consumers:
            if str(consumer) not in id_set:
                violations.append(
                    f"INV-4: message {message.get('message_name')!r} consumer unresolved"
                )

    # INV-5: tool-contract agent references resolve.
    for contract in tool_contracts:
        owner = str(contract.get("agent_id"))
        if owner not in id_set:
            violations.append(
                f"INV-5: tool_contract {contract.get('tool_name')!r} for unresolved "
                f"agent {owner!r}"
            )

    # INV-6: the cited topology is canonical (no hallucinated topologies —
    # the in-repo cousin of package slopsquatting).
    cited = overview.get("topology")
    if cited is not None and str(cited) not in _VALID_TOPOLOGIES and str(cited) != "":
        violations.append(f"INV-6: cited topology {str(cited)!r} not canonical")

    # INV-7: score fields fall within their declared ranges.
    for label, score in (
        ("overview.score", overview.get("score")),
        ("final_quality_score", design.get("final_quality_score")),
    ):
        if score is not None and not (SCORE_RANGE[0] <= float(score) <= SCORE_RANGE[1]):
            violations.append(f"INV-7: {label}={score!r} outside {SCORE_RANGE}")

    return violations
