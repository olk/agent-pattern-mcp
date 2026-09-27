# Why the Analyze Phase Submits Each Thought to Both MCP Reasoning Tools

When reading `make docker-logs` for an analyze-phase run, the same `thought`
string appears twice per step — once sent to `code-reasoning`, once to
`shannonthinking` (see calls 1–4 in any captured log). This is by design,
not a duplication bug.

## Where the Integration Is Wired

Both servers are children of *this* server (it is an MCP client of
them), not tools it exposes to its own callers: the trace only feeds
the phase prompts, and no tool response carries it. (`overview.reasoning`
in a design answer is the LLM's authored rationale — unrelated to the
reasoning MCPs.)

| Concern | Location |
|---|---|
| Build + startup health check | `src/server.py:379-382` — `_build_reasoning_client` (`:468`), `_check_reasoning_health` (`:485`); `fail_fast` raises at `:509-515` |
| Injected into the pipeline | `src/server.py:404-410` (`reasoning_client=...`); closed at `:533` |
| Phase hooks | `src/pipeline.py:583` (`_reasoning_block`), called at `:739` analyze, `:897` generate, `:999` evaluate, `:1967` refine |
| stdio spawn per call | `src/reasoning/client.py:237` (`StdioTransport(..., keep_alive=False)`) |
| Command resolution | `src/reasoning/client.py:198-231`: explicit override → Docker-embedded path → pinned `npx` |
| Package bake / env knobs | `Dockerfile:60-63`; `config/config.json:60-67` (`REASONING_*`; empty cmd string → embedded default via `src/reasoning/config.py:268-280`) |

## The Tools Are Scratchpads, Not Reasoners

`shannonthinking` and `code-reasoning` are *structured thinking
scratchpads*: they validate, number, and record thoughts a caller
authors. Neither tool authors its own content. The ThoughtGenerator
loop (`src/reasoning/client.py:_generate_trace`) authors each thought
**with the generator's own LLM** (one `generate_structured` call per
step), then submits it to every tool listed in the phase strategy:

```python
# src/reasoning/client.py:_generate_trace (~line 340)
for tool_kind in strategy.tools:                              # every configured tool
    payload = draft_to_params(tool_kind, draft, step_number, total)
    await self._call_tool(tool_kind, payload)                # same thought, different casing
```

## Per-Phase Tool Selection

The `tools` list is per-phase in `ReasoningConfig.per_phase.<phase>.tools`
(`src/reasoning/config.py`, defaults in `_default_per_phase()`):

| Phase   | `tools`              | Calls per step | Submissions per phase run |
|---------|----------------------|----------------|----------------------------|
| analyze | `["code", "shannon"]`| 2              | 2 × `pre_llm_thoughts`     |
| generate| `["code"]`           | 1              | 1 × `pre_llm_thoughts`     |
| evaluate| `["shannon"]`        | 1              | 1 × `pre_llm_thoughts`     |
| refine  | `["code", "shannon"]`| 2              | 2 × `pre_llm_thoughts`     |

The analyze phase uses both tools per step by deliberate design (Plan v5
§8.2): `shannonthinking` provides Shannon-style validation state
(uncertainty, recheckStep, experimentalValidation); `code-reasoning`
provides branch-aware state. Running them in parallel is a
cross-validation pattern — both must accept the same authored thought
for it to be considered validated.

## Which Tool Guards Which Pipeline Output

The per-phase `tools` list is not arbitrary: each phase is guarded by
the tool whose state model matches what that phase emits.

| Phase | Emits | `tools` | Max calls/run |
|---|---|---|---|
| analyze | requirement weights, pattern ranking | `["code", "shannon"]` | 4 × 2 = 8 |
| generate | **design components** (agents, relationships, contracts) | `["code"]` | 3 × 1 = 3 |
| evaluate | metrics, findings, recommendations | `["shannon"]` | 3 × 1 = 3 |
| refine | corrected design | `["code", "shannon"]` | 2 × 2 = 4 |

Upper bounds: `pre_llm_thoughts` (default 4/3/3/2) times the number of
configured tools, further capped by `max_total_steps`. A draft with
`next_needed=false` ends the loop early, so real runs are often lower.

**Component *generation* is `code-reasoning`-only.** `generate`
(`src/pipeline.py :: generate`) is the phase that builds the answer's
components, and its strategy carries `tools=["code"]`
(`src/reasoning/config.py :: _default_per_phase`) — so every reasoning
step feeding the design runs through `code-reasoning` and
`shannonthinking` is never called for that phase. The call chain is

```text
generate
  → _reasoning_block("generate", {"requirements": ...})     # src/pipeline.py
  → ReasoningClient.run_pre_llm("generate", ...)            # src/reasoning/client.py
  → _generate_trace: for tool_kind in strategy.tools: ...   # ["code"] only
  → render_reasoning_context(phase, trace)                  # <reasoning_context>
  → _build_generate_user_prompt(..., reasoning_context=...)  # injected in the prompt
  → generate_structured(AgentSystemDesignResponse)          # the components
```

## Pattern `component_types` Are Extracted Deterministically

The patterns' own components never pass through either reasoning tool.
`component_types` (`"Name: description"` entries in the pattern JSON,
typed at `src/schemas/patterns.py:120`) are read and rendered by plain
Python *before* the phase LLM call:

| Step | Location | Reasoning MCP calls |
|---|---|---|
| `Component Types:` section of the generate prompt | `src/pipeline.py :: _build_pattern_context` (`:1398-1466`, section at `:1454`), consumed by `generate` at `:900-905` | 0 |
| Expected-component list of the evaluate prompt | `src/pipeline.py :: _build_evaluate_user_prompt` (`:1909-1911`) | 0 — evaluate's strategy is shannon-only |
| `component://{type}` blueprint registry, built at startup | `src/resources/components.py :: build_component_blueprints` (`:77`), called once in the server lifespan (`src/server.py:606`, into `lifespan_context["component_blueprints"]` at `:617`) | 0 |

So `code-reasoning` guards component *generation*, not component
*extraction*: it is called for the phase that emits the design's
components (`agents`), while the pattern-side component types are only
read, deduplicated across patterns (no per-pattern slice in
`_build_pattern_context`; the `pattern_context_limits["component_types"]`
cut of 5 applies in the evaluate prompt, `src/config.py:150`), and
formatted into the prompt. Seeing no `code-reasoning` line while
`component_types` flow through a run is expected; seeing none while
`generate` emits `agents` is not.

Corollary: the per-phase tool split does not track *prompt content* —
the evaluate prompt also lists expected component types, yet evaluate
runs `["shannon"]`. The split tracks what the phase *emits*.

`config/config.json` exposes only env knobs (`REASONING_*`) and sets
**no** `per_phase` override, so the code defaults in
`_default_per_phase()` are what actually run in Docker and locally.

Three ways the generate phase emits components *without* a
`code-reasoning` call — check these before concluding the tool is
broken:

1. `generate(override_user_prompt=...)` takes the branch at
   `src/pipeline.py:893-896` that skips `_reasoning_block` entirely — no
   tool call, and no degraded scaffold either. The only in-tree caller
   passing an override is the design-loop retry (`src/pipeline.py:1104`).
2. `REASONING_ENABLED=false`, a tool failure, or an empty trace makes
   `_reasoning_block` fall back to `render_degraded_context(phase)`:
   in-prompt guidance, zero MCP calls.
3. `generate` is a cacheable phase; a cache hit replays the
   `tool_call_counts` of the original run with `cached=True` in the
   `"Reasoning trace ready"` record.

## Proving the Per-Phase Tool Split Without Docker

The strategies are readable, but the wiring is worth executing. This
throwaway script stubs the LLM (the loop only needs it to author
`ThoughtDraft`s) and runs the real servers over stdio:

```python
import asyncio
from src.reasoning.client import ReasoningClient
from src.reasoning.config import ReasoningConfig


class StubAgent:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(self, **kwargs):
        self.calls += 1
        return {
            "thought": f"Component plan step {self.calls}",
            "phase_tag": "implementation",
            "branch_id": None,
            "is_revision": False,
            "assumptions": [],
            "dependencies": [],
            "uncertainty": 0.1,
            "next_needed": self.calls < 3,
        }


async def main() -> None:
    cfg = ReasoningConfig()
    for phase in ("analyze", "generate", "evaluate", "refine"):
        print(phase, cfg.get_strategy(phase).tools)
    client = ReasoningClient(cfg, StubAgent())
    trace = await client.run_pre_llm("generate", {"requirements": "..."})
    print(trace.tool_call_counts, [(s.tool, s.step_number) for s in trace.steps])


asyncio.run(main())
```

Observed output (2026-09-27, local run, `npx` fallback for both
packages — the `/usr/local/lib/node_modules` embedded path only exists
in the image):

```text
analyze  ['code', 'shannon']
generate ['code']
evaluate ['shannon']
refine   ['code', 'shannon']
{'code-reasoning': 3} [('code', 1), ('code', 2), ('code', 3)]
```

with `steps[0].tool_response` carrying the real server ack:

```json
{"status": "processed", "thought_number": 1, "total_thoughts": 3,
 "next_thought_needed": true, "branches": [], "thought_history_length": 1}
```

`shannonthinking` appears nowhere in the generate run — as the table
above predicts. Running the same script against `evaluate` yields
`{'shannonthinking': 3}` and a camelCase ack instead. Outside Docker
both tools log `Reasoning MCP '<kind>' embedded binary not found;
falling back to npx` at INFO on first use; that is the
`npx` fallback in `ReasoningClient._resolve_cmd`, not a failure.

The same probe over all four phases (stub LLM that never sets
`next_needed=false`, so every strategy runs to its full
`pre_llm_thoughts`) yields the routing matrix:

| Phase | Observed `tool_call_counts` |
|---|---|
| analyze | `{'code-reasoning': 4, 'shannonthinking': 4}` |
| generate | `{'code-reasoning': 3}` |
| evaluate | `{'shannonthinking': 3}` |
| refine | `{'code-reasoning': 2, 'shannonthinking': 2}` |

The generate phase's payload keeps the code tool's snake_case contract:
`{'thought': ..., 'thought_number': 1, 'total_thoughts': 3,
'next_thought_needed': True}`.

In Docker the same counts are visible in the `"Reasoning trace ready"`
INFO record — see [Verifying in `docker logs`](#verifying-in-docker-logs).

## Wire Shape Differs, Content Does Not

The two adapters in `src/reasoning/tools.py` only change field casing —
they never mutate the `thought` body:

| Tool             | Wire fields                                                                                              | Bytes |
|------------------|----------------------------------------------------------------------------------------------------------|-------|
| `code-reasoning` | `thought`, `thought_number`, `total_thoughts`, `next_thought_needed` (4 fields, snake_case)              | 153–154 |
| `shannonthinking`| `thought`, `thoughtType`, `thoughtNumber`, `totalThoughts`, `nextThoughtNeeded`, `uncertainty`, `assumptions`, `dependencies` (8 fields, camelCase) | 217–232 |

The `thought` field is byte-identical in both wire payloads. The
differences in **response** structure reflect each tool's bookkeeping:

```json
// code-reasoning — minimal ack + branch state
{"status":"processed","thought_number":2,"total_thoughts":4,
 "next_thought_needed":false,"branches":[],"thought_history_length":1}

// shannonthinking — Shannon-style validation state
{"thoughtNumber":2,"totalThoughts":4,"nextThoughtNeeded":false,
 "thoughtType":"problem_definition","uncertainty":0.05,
 "dependencies":[],"assumptions":[]}
```

## Why Responses Never Contain a Thought

Neither response carries an authored `thought` text — only metadata
(numbering, continuation flag, validation state, branch/experiment
flags). This is **by design**: both tools are *scratchpads that record
thoughts the caller authors*, not generators. The ThoughtGenerator
loop is the only thing that authors content; the tools validate,
number, and decide whether to continue.

The naming ("shannon-**thinking**", "code-**reasoning**") reads like a
generator but the contracts confirm scratchpad-only behavior:

```python
# src/reasoning/tools.py:106-129
SHANNON_TOOL = ToolContract(
    kind="shannon", name="shannonthinking",
    probe_payload={"thought": "startup probe",
                   "thoughtType": "problem_definition",
                   "thoughtNumber": 1, "totalThoughts": 1,
                   "nextThoughtNeeded": False, ...},
)
CODE_TOOL = ToolContract(
    kind="code", name="code-reasoning",
    probe_payload={"thought": "startup probe",
                   "thought_number": 1, "total_thoughts": 1,
                   "next_thought_needed": False},
)
```

Inputs: just `thought` (body) + numbering/control fields. **Nothing
else flows in; nothing thought-shaped flows back.** The tools have
no LLM inside — they're pure validators/recorders, and their npm
packages (`@mettamatt/code-reasoning`, `olaservo/shannon-thinking`)
are pure-JS state machines.

The module docstring makes this explicit
(`src/reasoning/config.py:34-37`):

> Both tools are scratchpads, not reasoning engines: a caller must
> AUTHOR each thought. The ReasoningClient's ThoughtGenerator loop
> does that with this server's own LLM, then submits the thought to
> the tool for structuring.

And the client (`src/reasoning/client.py:23-31`):

> The two reasoning MCP servers are structured SCRATCHPADS: they
> validate, number, branch, and record thoughts that a CALLER
> authors.

If the tools echoed thoughts back, the wire would carry every
thought twice (once in the request, once in the response), doubling
log volume and risking accidental re-disclosure. The lean
request-only content / response-only metadata split is deliberate.

## Dual Submission as a Runtime Integrity Check

Because the same thought body goes to both tools, the two DEBUG log lines
per step carrying **byte-identical `thought` values** is a runtime
sanity check that the wire adapters don't mutate the body — only re-case
field names. An adapter regression that accidentally truncated, rewrote,
or rewrote fields would show up as a divergence between the two log
lines at the same `(phase, step)` and be visible immediately.

This is also why the pre-call DEBUG line logs `payload_keys` (the
shape) but only later versions log the full `thought` (the body) —
the keys list is the shape contract, the thought is the content.

## How to Change It

To restrict analyze (or any phase) to a single tool, edit
`src/reasoning/config.py:_default_per_phase()["analyze"].tools` to
`["shannon"]` (or `["code"]`). This loses the dual-tool
cross-validation pattern — keep the trade-off in mind.

## Verifying in `docker logs`

A clean analyze run produces `tools_called={"code-reasoning": N,
"shannonthinking": N}` in the `"Reasoning trace ready"` INFO record
(`src/pipeline.py :: _reasoning_block`). For the captured run: N=2 for
analyze (4 total calls = 2 steps × 2 tools), N=3 for evaluate (3 ×
shannon), N=3 for generate (3 × code). The counts match the strategy's
`tools` lists above, multiplied by the number of thoughts in the
phase. If `tools_called` ever shows a tool that isn't in the
strategy's `tools` list (or omits one that is), the configuration is
out of sync.