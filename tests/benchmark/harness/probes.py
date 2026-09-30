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

"""Observability probes for benchmark runs (S3).

Wraps the pipeline's side-effecting collaborators (LLM agent, embedder,
reasoning client, retriever, reranker) so each call is timed and recorded as
a :class:`StageRecord` without changing pipeline semantics. Also provides
:class:`ScriptedAgent` and :class:`StubSlugRetriever` — the deterministic
offline stand-ins used by ``offline.py``.
"""

from __future__ import annotations

import asyncio
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel

from src.schemas.agent_system import AgentSystemDesignResponse, AgentSystemDesignResponseWire
from src.schemas.analysis import RequirementWeights
from src.schemas.evaluation import AgentSystemEvaluation

if TYPE_CHECKING:
    from collections.abc import Iterator


# ---------------------------------------------------------------------------
# Stage records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageRecord:
    """One timed seam call.

    Attributes:
        stage: Latency bucket the report groups by — e.g. ``llm.weights``,
            ``reasoning.analyze``, ``retrieval.fused``, ``reranking``,
            ``e2e.http``, ``build.embed``.
        op: The seam method that produced it, e.g.
            ``AgentSystemArchitect.generate_structured``,
            ``HybridPatternRetriever.retrieve``.
        started_ns: Monotonic clock at operation start.
        duration_ms: Wall duration in milliseconds.
        ok: Whether the operation completed without raising.
        meta: Small structured payload (bucket names, scenario ids, counts).
    """

    stage: str
    op: str
    started_ns: int
    duration_ms: float
    ok: bool
    meta: dict[str, Any] = field(default_factory=dict)

# ---------------------------------------------------------------------------
# Nested attribution
# ---------------------------------------------------------------------------

#: Per-thread stack of nested-time budgets, one frame per enclosing seam.
#: Two seams nest inside another seam's wall time:
#: ``SafeTEIReranker.postprocess_nodes`` runs inside
#: ``HybridPatternRetriever.retrieve`` (src/patterns/retriever.py), and the
#: ThoughtGenerator's ``generate_structured`` calls run inside
#: ``ReasoningClient.run_pre_llm``. Without this accounting the enclosing
#: record double-counts the nested one, so a stage table that sums its rows
#: exceeds the measured total (observed live: a 1.12 s rerank inside a
#: 1.32 s retrieve row). Enclosing records therefore report *exclusive*
#: ``duration_ms``, keeping raw wall time in ``meta["inclusive_ms"]`` and the
#: nested share in ``meta["nested_ms"]``. A nested call is charged only while
#: a frame is open, so a top-level ``llm.*`` call keeps its own duration.
_NESTED_FRAMES = threading.local()


# ---------------------------------------------------------------------------
# Stage taxonomy
# ---------------------------------------------------------------------------

#: ``stage`` is the bucket (what the report groups by), ``op`` is the seam
#: method that produced the record — the same split the sibling harness uses.
#: ``STAGE_BUILD_EMBED`` is recorded once per run (index build) and is
#: excluded from every per-scenario latency total.

STAGE_BUILD_EMBED = "build.embed"
STAGE_RETRIEVAL_FUSED = "retrieval.fused"
STAGE_RERANKING = "reranking"
STAGE_LLM_WEIGHTS = "llm.weights"
STAGE_LLM_GENERATE = "llm.generate"
STAGE_LLM_EVALUATE = "llm.evaluate"
STAGE_LLM_DRAFT = "llm.draft"
STAGE_E2E_HTTP = "e2e.http"

#: Build stages: recorded, never part of a per-scenario total.
BUILD_STAGES: tuple[str, ...] = (STAGE_BUILD_EMBED,)


def reasoning_stage(phase: str) -> str:
    """Stage bucket for one reasoning phase."""
    return f"reasoning.{phase}"


#: Seam method recorded as each stage's ``op``.
OP_RETRIEVE = "HybridPatternRetriever.retrieve"
OP_RERANK = "SafeTEIReranker.postprocess_nodes"
OP_GENERATE_STRUCTURED = "AgentSystemArchitect.generate_structured"
OP_RUN_PRE_LLM = "ReasoningClient.run_pre_llm"
OP_WARMUP_INDEXES = "AgentPatternPipeline.warmup_indexes"
OP_HTTP = "fastmcp_client.call"

def push_nested_frame() -> None:
    """Open a nested-time budget for an enclosing seam (this thread)."""
    frames = getattr(_NESTED_FRAMES, "value", None)
    if frames is None:
        frames = []
        _NESTED_FRAMES.value = frames
    frames.append(0)


def pop_nested_frame_ns() -> int:
    """Close the innermost frame; return the nanoseconds it collected."""
    frames = getattr(_NESTED_FRAMES, "value", None)
    if not frames:
        return 0
    return frames.pop()


def add_nested_time(elapsed_ns: int) -> None:
    """Charge ``elapsed_ns`` to the innermost open frame, if any."""
    frames = getattr(_NESTED_FRAMES, "value", None)
    if frames:
        frames[-1] += elapsed_ns


def exclusive_record(
    stage: str,
    op: str,
    started_ns: int,
    *,
    ok: bool,
    meta: dict[str, Any] | None = None,
) -> StageRecord:
    """Build a record whose ``duration_ms`` excludes the nested time charged
    to the frame the caller opened."""
    elapsed = time.monotonic_ns() - started_ns
    nested = pop_nested_frame_ns()
    payload: dict[str, Any] = dict(meta or {})
    payload["inclusive_ms"] = round(elapsed / 1e6, 3)
    if nested:
        payload["nested_ms"] = round(nested / 1e6, 3)
    return StageRecord(
        stage=stage,
        op=op,
        started_ns=started_ns,
        duration_ms=max(0.0, (elapsed - nested) / 1e6),
        ok=ok,
        meta=payload,
    )




class StageRecorder:
    """Accumulates :class:`StageRecord` entries for one run."""

    def __init__(self) -> None:
        self._records: list[StageRecord] = []

    def add(self, record: StageRecord) -> None:
        """Append one observation."""
        self._records.append(record)

    @property
    def records(self) -> list[StageRecord]:
        """Observed records in insertion order."""
        return list(self._records)

    def counts(self) -> dict[str, int]:
        """Record count per operation bucket."""
        tally: dict[str, int] = {}
        for record in self._records:
            tally[record.op] = tally.get(record.op, 0) + 1
        return tally


# ---------------------------------------------------------------------------
# LLM proxy + protocol
# ---------------------------------------------------------------------------


class SupportsGenerateStructured(Protocol):
    """Anything exposing the pipeline's agent surface."""

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
    ) -> BaseModel: ...


def percentile_fields(values: list[float]) -> dict[str, Any]:
    """p50/p95 of ``values`` via the stdlib inclusive quantiles, or ``None`` when sparse.

    ``statistics.quantiles(n=20, method="inclusive")`` yields 19 cut points at
    ``i/20``; p50 is index 9 and p95 index 18. Fewer than four samples report
    ``None`` plus a note — never NaN.
    """
    from tests.benchmark.harness.scoring import percentiles

    p50, p95, note = percentiles(list(values))
    return {
        "samples": len(values),
        "p50_ms": p50,
        "p95_ms": p95,
        "note": note or None,
    }


def stage_table(records: list[StageRecord]) -> dict[str, dict[str, Any]]:
    """Group ``records`` by stage bucket: count, failures, total ms, p50/p95, ops."""
    table: dict[str, dict[str, Any]] = {}
    for record in records:
        entry = table.setdefault(
            record.stage,
            {"count": 0, "failures": 0, "total_ms": 0.0, "ops": {}, "durations": []},
        )
        entry["count"] += 1
        if not record.ok:
            entry["failures"] += 1
        entry["total_ms"] = round(entry["total_ms"] + record.duration_ms, 3)
        entry["ops"][record.op] = entry["ops"].get(record.op, 0) + 1
        entry["durations"].append(record.duration_ms)
    for entry in table.values():
        entry.update(percentile_fields(entry.pop("durations")))
    return table


def request_stage_total_ms(table: dict[str, dict[str, Any]]) -> float:
    """Σ ``total_ms`` over every non-build stage (index build excluded)."""
    return round(
        sum(float(entry["total_ms"]) for stage, entry in table.items() if stage not in BUILD_STAGES),
        3,
    )


def residual_ms(e2e_ms: float, table: dict[str, dict[str, Any]]) -> float:
    """``e2e − Σ(request stages)``: wall time outside the observed seams.

    A negative value means the seams overlapped beyond what the nested-frame
    accounting covers (concurrency inside one stage), not missing time.
    """
    return round(e2e_ms - request_stage_total_ms(table), 3)


def residual_note(residual: float) -> str | None:
    """Human note for a negative residual, else ``None``."""
    if residual >= 0:
        return None
    return (
        "stage sums exceed the measured wall clock (seam overlap); "
        "a negative residual means overlap, not missing time"
    )


_LLM_BUCKETS: tuple[tuple[str, str], ...] = (
    ("RequirementWeights", STAGE_LLM_WEIGHTS),
    ("AgentSystemDesignResponse", STAGE_LLM_GENERATE),
    ("AgentSystemDesignResponseWire", STAGE_LLM_GENERATE),
    ("AgentSystemEvaluation", STAGE_LLM_EVALUATE),
    ("ThoughtDraft", STAGE_LLM_DRAFT),
)


def _llm_bucket(response_schema: type[BaseModel]) -> str:
    """Map a response schema to its latency bucket."""
    name = response_schema.__name__
    for schema_name, bucket in _LLM_BUCKETS:
        if name == schema_name:
            return bucket
    return "llm.other"


class LLMProxy:
    """Times and records every ``generate_structured`` call of a real agent."""

    def __init__(
        self,
        real_agent: SupportsGenerateStructured,
        recorder: StageRecorder,
        stage: str = "run",
    ) -> None:
        self._real_agent = real_agent
        self._recorder = recorder
        self._stage = stage

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        """Delegate to the wrapped agent, recording the observed call."""
        started = time.monotonic_ns()
        ok = True
        try:
            return await self._real_agent.generate_structured(
                system_prompt, user_prompt, response_schema
            )
        except Exception:
            ok = False
            raise
        finally:
            add_nested_time(time.monotonic_ns() - started)
            self._recorder.add(
                exclusive_record(
                    _llm_bucket(response_schema),
                    OP_GENERATE_STRUCTURED,
                    started,
                    ok=ok,
                    meta={"schema": response_schema.__name__},
                )
            )


class EmbedderProbe:
    """Counts embedding calls while delegating to the real embedder.

    Only the methods the pipeline actually exercises are explicit; everything
    else resolves through ``__getattr__`` so the probe is a drop-in wrapper.
    """

    def __init__(self, real_embedder: Any, recorder: StageRecorder) -> None:
        self._real_embedder = real_embedder
        self._recorder = recorder

    def _record(self, op: str, started_ns: int, ok: bool) -> None:
        self._recorder.add(
            StageRecord(
                stage=op,
                op="BaseEmbedding.embed",
                started_ns=started_ns,
                duration_ms=(time.monotonic_ns() - started_ns) / 1e6,
                ok=ok,
                meta={},
            )
        )

    def get_query_embedding(self, query: str) -> list[float]:
        """Delegate and record an ``embedder.query`` call."""
        started = time.monotonic_ns()
        try:
            result: list[float] = self._real_embedder.get_query_embedding(query)
        except Exception:
            self._record("embedder.query", started, False)
            raise
        self._record("embedder.query", started, True)
        return result

    def get_text_embedding(self, text: str) -> list[float]:
        """Delegate and record an ``embedder.text`` call."""
        started = time.monotonic_ns()
        try:
            result: list[float] = self._real_embedder.get_text_embedding(text)
        except Exception:
            self._record("embedder.text", started, False)
            raise
        self._record("embedder.text", started, True)
        return result

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Delegate and record an ``embedder.texts`` call."""
        started = time.monotonic_ns()
        try:
            result: list[list[float]] = self._real_embedder._get_text_embeddings(texts)
        except Exception:
            self._record("embedder.texts", started, False)
            raise
        self._record("embedder.texts", started, True)
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real_embedder, name)


class ReasoningProbe:
    """Times reasoning-client pre-LLM calls per phase."""

    def __init__(self, real_client: Any, recorder: StageRecorder) -> None:
        self._real_client = real_client
        self._recorder = recorder

    @property
    def enabled(self) -> bool:
        """Whether the wrapped reasoning client is enabled."""
        return bool(self._real_client.enabled)

    async def run_pre_llm(self, phase: str, task_inputs: dict[str, str]) -> Any:
        """Delegate to the wrapped client, recording ``reasoning.<phase>``."""
        started = time.monotonic_ns()
        ok = True
        push_nested_frame()
        try:
            return await self._real_client.run_pre_llm(phase, task_inputs)
        except Exception:
            ok = False
            raise
        finally:
            self._recorder.add(
                exclusive_record(
                    reasoning_stage(phase), OP_RUN_PRE_LLM, started, ok=ok,
                    meta={"phase": phase},
                )
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real_client, name)


# ---------------------------------------------------------------------------
# Live-probe patching (monkeypatches; restored on context exit)
# ---------------------------------------------------------------------------


@contextmanager
def apply_live_probes(recorder: StageRecorder) -> Iterator[None]:
    """Patch retriever/reranker call sites to observe real invocations.

    Patches ``HybridPatternRetriever.retrieve`` (sync; the pipeline drives it
    through ``asyncio.to_thread``) and ``SafeTEIReranker.postprocess_nodes``
    (observe-only wrapper). Restores both on exit.
    """
    from src.patterns.retriever import HybridPatternRetriever
    from src.patterns.safe_tei_rerank import SafeTEIReranker

    original_retrieve = HybridPatternRetriever.retrieve
    original_postprocess = SafeTEIReranker.postprocess_nodes

    def probed_retrieve(
        self: HybridPatternRetriever, user_domain: str, normalized_domain: str
    ) -> Any:
        started = time.monotonic_ns()
        ok = True
        push_nested_frame()
        try:
            return original_retrieve(self, user_domain, normalized_domain)
        except Exception:
            ok = False
            raise
        finally:
            recorder.add(
                exclusive_record(
                    STAGE_RETRIEVAL_FUSED,
                    OP_RETRIEVE,
                    started,
                    ok=ok,
                    meta={"user_domain": user_domain},
                )
            )

    def probed_postprocess(
        self: SafeTEIReranker, nodes: Any, query_bundle: Any = None
    ) -> Any:
        started = time.monotonic_ns()
        result = original_postprocess(self, nodes, query_bundle=query_bundle)
        add_nested_time(time.monotonic_ns() - started)
        recorder.add(
            StageRecord(
                stage=STAGE_RERANKING,
                op=OP_RERANK,
                started_ns=started,
                duration_ms=(time.monotonic_ns() - started) / 1e6,
                ok=True,
                meta={"nodes": len(nodes)},
            )
        )
        return result

    HybridPatternRetriever.retrieve = probed_retrieve  # type: ignore[method-assign]
    SafeTEIReranker.postprocess_nodes = probed_postprocess  # type: ignore[method-assign,assignment]
    try:
        yield
    finally:
        HybridPatternRetriever.retrieve = original_retrieve  # type: ignore[method-assign]
        SafeTEIReranker.postprocess_nodes = original_postprocess  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Offline stand-ins
# ---------------------------------------------------------------------------


#: Schema name → latency bucket (same taxonomy as the live LLM proxy).
_LLM_OP_BY_SCHEMA: dict[str, str] = {
    "RequirementWeights": STAGE_LLM_WEIGHTS,
    "AgentSystemDesignResponse": STAGE_LLM_GENERATE,
    "AgentSystemDesignResponseWire": STAGE_LLM_GENERATE,
    "AgentSystemEvaluation": STAGE_LLM_EVALUATE,
}


class ScriptedAgent:
    """Deterministic agent replaying scenario-scripted pipeline responses.

    Dispatches on ``response_schema`` exactly like the mock in
    ``tests/unit/test_pipeline.py``:

    - ``RequirementWeights`` → the scenario's scripted weights.
    - design schemas → a minimal valid design whose ``overview.topology``
      equals the winner's catalog topology (drives ``final_pattern_name``).
    - ``AgentSystemEvaluation`` → an evaluation whose ``overall_quality``
      metric sits in [55, 75) — above the floor that would look broken, below
      the 100.0 early-stop threshold pinned in ``offline_retrieval_config``.
    """

    def __init__(
        self, scenario_id: str, scripted_weights: dict[str, float], topology: str, category: str,
        recorder: StageRecorder | None = None,
    ) -> None:
        self._scenario_id = scenario_id
        self._scripted_weights = scripted_weights
        self._topology = topology
        self._category = category
        self._recorder = recorder

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        """Return the scripted response for the requested schema."""
        del system_prompt, user_prompt
        name = response_schema.__name__
        started = time.monotonic_ns()
        result = self._dispatch(name, response_schema)
        if self._recorder is not None:
            self._recorder.add(
                StageRecord(
                    stage=_LLM_OP_BY_SCHEMA.get(name, "llm.other"),
                    op="ScriptedAgent.generate_structured",
                    started_ns=started,
                    duration_ms=(time.monotonic_ns() - started) / 1e6,
                    ok=True,
                    meta={"schema": name},
                )
            )
        return result

    def _dispatch(self, name: str, response_schema: type[BaseModel]) -> BaseModel:
        """Return the scripted payload for one schema name."""
        if name == "RequirementWeights":
            return _scripted_weights(self._scripted_weights)
        if name in {"AgentSystemDesignResponse", "AgentSystemDesignResponseWire"}:
            return _scripted_design(response_schema, self._scenario_id, self._topology, self._category)
        if name == "AgentSystemEvaluation":
            return _scripted_evaluation(self._scenario_id)
        msg = f"ScriptedAgent: no scripted response for schema {name}"
        raise ValueError(msg)


def _scripted_weights(scripted: dict[str, float]) -> RequirementWeights:
    """Build RequirementWeights from the scenario's scripted map."""
    kwargs: dict[str, float] = {key: float(scripted.get(key, 0.0)) for key in
                                ("reliability", "cost_efficiency", "latency",
                                 "output_quality", "observability", "safety", "simplicity")}
    return RequirementWeights(**kwargs)


def _scripted_design(
    response_schema: type[BaseModel], scenario_id: str, topology: str, category: str
) -> BaseModel:
    """Build a minimal valid design response with the winner's topology."""
    from src.schemas.components import Agent

    agent = Agent(
        id="bench-agent",
        name="Benchmark Agent",
        role="worker",
        description="Scripted benchmark agent.",
        responsibilities=["Execute the scripted benchmark step."],
    )
    payload: dict[str, Any] = {
        "overview": {
            "topology": topology,
            "category": category,
            "principles": ["Deterministic scripted design for benchmark replay."],
            "reasoning": f"Scripted design for scenario {scenario_id}.",
        },
        "agents": [agent.model_dump()],
        "relationships": [],
        "quality_attributes": {"reliability": 8.0},
        "tool_contracts": [],
        "shared_state_models": [],
        "message_contracts": [],
    }
    model = response_schema.model_validate(payload)
    return model


def _scripted_evaluation(scenario_id: str) -> AgentSystemEvaluation:
    """Deterministic evaluation scoring 55-74 (never triggers early stop)."""
    import random

    rng = random.Random(f"overall_quality:{scenario_id}")
    score = 55.0 + rng.random() * 20.0
    return AgentSystemEvaluation.model_validate(
        {
            "summary": {
                "reasoning": f"Scripted evaluation for scenario {scenario_id}.",
                "overall_score": score,
            },
            "metrics": [
                {
                    "name": "overall_quality",
                    "score": score,
                    "description": "Scripted overall quality metric.",
                    "findings": ["Scripted finding."],
                    "recommendations": ["Scripted recommendation."],
                }
            ],
            "risks": [],
            "compliance": [],
            "recommendations": {"immediate": [], "long_term": []},
        }
    )


class StubSlugRetriever:
    """Single-slug retriever standing in for both hybrid legs offline.

    Returns one node per requested slug with a constant score. Because both
    legs return the identical node set, ``QueryFusionRetriever`` dedupes to a
    single fused node and the reranker is skipped — zero network in offline
    runs (the ``offline-invalid`` reranker URL acts as a tripwire).
    """

    def __init__(self, slugs: list[str], score: float = 0.9) -> None:
        self._slugs = list(slugs)
        self._score = score
        self.calls: list[str] = []

    def retrieve(self, query: str | Any) -> list[Any]:
        """Return one NodeWithScore per configured slug (llama-index leg API)."""
        del query
        from llama_index.core.schema import NodeWithScore, TextNode

        self.calls.append(str(len(self._slugs)))
        return [
            NodeWithScore(
                node=TextNode(text=slug, id_=f"slug::{slug}", metadata={"slug": slug}),
                score=self._score,
            )
            for slug in self._slugs
        ]

    async def aretrieve(self, query: str | Any) -> list[Any]:
        """Async variant delegating to the sync path."""
        return self.retrieve(query)


def run_stub_retriever_probe(slugs: list[str]) -> int:
    """Sync smoke helper: drive the stub once, return the node count."""
    stub = StubSlugRetriever(slugs)
    nodes = stub.retrieve("ignored")
    return len(nodes)


def async_wait_for(coro: Any, timeout: float) -> Any:
    """Thin asyncio.wait_for wrapper kept for parity with the reference harness."""
    return asyncio.wait_for(coro, timeout=timeout)
