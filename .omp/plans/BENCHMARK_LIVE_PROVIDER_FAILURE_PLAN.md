# Plan: make benchmark-live fail fast on dead LLM providers (benchmark-live-provider-failure)

## Context

`make benchmark-live OUT=benchmarks/base` ran with an unfunded DeepSeek account. Result: ~75 minutes burned, 15/23 scenarios zeroed (14× `Insufficient Balance` → `LLMError ERR_009`, 1× empty-tool-call parse fault), 14× `Thought generation failed; trace ends here` (same generator authors the reasoning `ThoughtDraft`s, so provider death kills both paths), `hits=0`. Root cause is environmental — DeepSeek returns HTTP 402-class `Insufficient Balance` until the account is topped up (verified: DeepSeek error docs define 402 = out of balance, fix = top up at platform.deepseek.com) — but the harness made it silent and expensive: per-scenario tolerance (correct for *stochastic* faults) kept retrying and continuing a permanently dead provider, and llama-index `acompletion_with_retry` adds tenacity 4/8/10 s backoff per dead call (only Timeout/APIError/APIConnectionError/RateLimitError/ServiceUnavailableError retry — BadRequestError is not retried there; the minutes-per-scenario came from the harness self-healing repair loop `VALIDATION_MAX_RETRIES=2` ×3 calls plus retry cascades on the OpenAI no-credits variant which surfaces as RateLimitError).

Goal: a permanently dead generator provider (balance/credits/quota/auth) aborts the live arm loudly within seconds of first detection — before warmup when already dead, after the first failed scenario when it dies mid-run — with `aborted.json` written and a clean non-zero exit. Stochastic faults (parse errors, timeouts, single 429s) keep today's tolerant policy. Zero changes in `src/` (no mypy/oracle churn, no `.fizz` implications: job/pipeline control flow untouched). Also document the provider runbook (top up DeepSeek or switch to MiniMax via env; `make benchmark-live` stays env-overridable).

Evidence anchors (all read this session):
- `tests/benchmark/harness/live.py:207-263` `run_live_corpus`: tolerant loop, `except Exception` at :236 records `error = f"{type(exc).__name__}: {exc}"`, appends zeroed `LiveOutcome`, continues.
- `tests/benchmark/harness/live.py:286-319` `_run_warmup` swallows non-fail_fast errors; warmup would burn minutes before detection.
- `tests/benchmark/harness/live.py:65-130` `build_live_components` constructs `agent = AgentSystemArchitect(config)` at :74 (currently NOT returned in `LiveComponents`), `reasoning_client.health_check()` at :84.
- `tests/benchmark/harness/main.py:313-391` `_run_live`: generic `except Exception` at :386 calls `handle.mark_aborted(...)` and re-raises → traceback exit. `EXIT_REFUSAL = 2` at :36.
- `tests/benchmark/harness/runner.py:107-115` `RunHandle.mark_aborted` writes `aborted.json` (compare already refuses aborted runs).
- `tests/benchmark/harness/selfcheck.py:572-593` `run_selfchecks` registry; anchors are pure functions, no network (pattern to copy at :211-239).
- Failure strings: `benchmarks/base/manifest.json:31-45`; prior funded run `data/benchmark-runs/bench-live-20260928T193307Z-6764c0` had 2 parse faults and 0 balance faults — proves parse ≠ provider death and parse must stay tolerated.
- `src/agent.py:56-77` `LLMError(provider, error, provider_message)` — raw provider text is preserved in `str(exc)`.

## Approach

All edits in `tests/benchmark/harness/` (never pytest-collected; gate is `make benchmark-selfcheck`). No `src/` edits.

### 1. `live.py`: provider-death classifier + `ProviderDeathError`

Add after the imports / near top of module:

```python
class ProviderDeathError(RuntimeError):
    """Generator provider permanently failed (balance/quota/auth) — abort the arm."""


#: Substrings (lowercased) that mark a provider as dead for money/auth reasons.
#: Deliberately phrase-anchored: bare numeric tokens ('401','403') would
#: false-positive on request ids like 'b5b0466d-1ced-...'.
PROVIDER_DEATH_SIGNATURES: tuple[str, ...] = (
    "insufficient balance",
    "no credits remaining",
    "insufficient_quota",
    "invalid_api_key",
    "incorrect api key",
    "api key not valid",
    "authentication_error",
    "permission denied",
    "account is depleted",
)


def is_permanent_provider_death(error_text: str) -> bool:
    """True when an error string names a permanent provider fault.

    Parse faults ('could not be parsed into', 'Field required'), timeouts,
    transient 429s and request-id noise match none of these phrases and stay
    tolerated by the per-scenario failure policy.
    """
    lowered = error_text.lower()
    return any(sig in lowered for sig in PROVIDER_DEATH_SIGNATURES)
```

### 2. `live.py`: carry the agent for a preflight probe

- `LiveComponents` (frozen dataclass, :43-52): add field `agent: Any` after `reasoning_client`.
- `build_live_components` (:125-130): return `agent=agent` in the `LiveComponents(...)` call.
- New module-level probe schema + preflight function:

```python
class _PreflightProbe(BaseModel):
    ok: bool = Field(default=True, description="Acknowledgement that the model is operational.")


async def preflight_generator(agent: Any, timeout_s: float = 120.0) -> None:
    """One cheap structured call before the arm; raise ProviderDeathError on death.

    asyncio.TimeoutError and non-death LLMError pass through silently — the
    preflight must never abort an arm on a transient hiccup; the mid-run
    classifier (step 4) still catches a provider that dies later.
    """
    try:
        await asyncio.wait_for(
            agent.generate_structured(
                system_prompt="Preflight check.",
                user_prompt="Confirm you are operational by calling the PreflightProbe function.",
                response_schema=_PreflightProbe,
            ),
            timeout=timeout_s,
        )
    except ProviderDeathError:
        raise
    except Exception as exc:  # noqa: BLE001 — classified, else conservative pass
        if is_permanent_provider_death(f"{type(exc).__name__}: {exc}"):
            raise ProviderDeathError(
                f"generator provider permanently failed preflight: {type(exc).__name__}: {exc}"
            ) from exc
```

Imports needed in `live.py`: `from pydantic import BaseModel, Field` (verify not already imported; add if missing).

### 3. `live.py`: call preflight in `run_live_corpus` before warmup

In `run_live_corpus` (:222-228), immediately after `components = await build_live_components(recorder)` and inside the existing `try` (so `finally: await shutdown_live_components(components)` still runs):

```python
        await preflight_generator(components.agent)
```

Insert as the first statement of the `try:` block, before the `warmup_record = ...` assignment. Docstring of `run_live_corpus`: append one sentence — "A provider that is permanently dead (balance/quota/auth) raises `ProviderDeathError` before warmup."

### 4. `live.py`: mid-run classifier in the tolerant loop

In the scenario loop's `except Exception` branch (:236-250), after `error = f"{type(exc).__name__}: {exc}"` and before `outcomes.append(...)`:

```python
                if is_permanent_provider_death(error):
                    raise ProviderDeathError(
                        f"generator provider died mid-run: {error}"
                    ) from exc
```

Keep appending the failed outcome is NOT needed — raising here means the arm is aborted; the already-collected `outcomes` are discarded by the abort path exactly like fail-fast does today (consistent with `_run_live`'s `mark_aborted` semantics). The `finally` shutdown still runs.

Update the `run_live_corpus` docstring failure-policy paragraph: tolerant for stochastic faults; `ProviderDeathError` (permanent balance/quota/auth) aborts regardless of `fail_fast`.

### 5. `main.py`: clean exit for `ProviderDeathError`

- Add constant near `EXIT_REFUSAL = 2` (:36): `EXIT_PROVIDER_DEAD = 3`.
- In `_run_live`, add a dedicated handler BEFORE the generic `except Exception as exc:` at :386:

```python
    except ProviderDeathError as exc:
        handle.mark_aborted(f"ProviderDeathError: {exc}")
        click.echo(f"ABORTED — generator provider permanently failed: {exc}")
        click.echo("Fix: top up the provider account or switch GENERATOR_* env (see tests/benchmark/README.md).")
        raise SystemExit(EXIT_PROVIDER_DEAD)
```

Import `ProviderDeathError` from `tests.benchmark.harness.live` alongside the existing lazy `run_live_corpus` import at :325 (module-level import is fine; `live.py` is already imported lazily inside `_run_live` — keep the lazy style: `from tests.benchmark.harness.live import ProviderDeathError, run_live_corpus`).

### 6. `selfcheck.py`: anchors for the classifier

- New anchor (pure, no network), following the `_check` pattern of `anchor_failure_policy` (:211-239):

```python
def anchor_provider_death() -> bool:
    """Permanent provider faults abort; stochastic faults stay tolerated."""
    from tests.benchmark.harness.live import is_permanent_provider_death

    dead = [
        'LLMError: LLM provider deepseek error: ERR_009 - litellm.BadRequestError: DeepseekException - '
        '{"error":{"message":"Insufficient Balance (request_id: b5b0466d-1ced-4e03-960e-bec2955f2ccd)",'
        '"type":"unknown_error","param":null,"code":"invalid_request_error"}}',
        "litellm.RateLimitError: OpenAIException - You have no credits remaining.",
        "litellm.AuthenticationError: invalid_api_key",
    ]
    alive = [
        "LLMError: ERR_009 - Structured output extraction failed: the LLM's tool call "
        "could not be parsed into AgentSystemDesignResponse. overview Field required "
        "[type=missing, input_value={}, input_type=dict]",
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
```

- Register in `run_selfchecks()` (:572-593): add `ok &= anchor_provider_death()` after `anchor_failure_policy()`.
- Note: the 429 string `"rate limit exceeded, retry after"` must NOT match any signature — it doesn't; this is asserted. If a provider ever phrases a *permanent* quota error as "rate limit", add that provider's exact phrase to `PROVIDER_DEATH_SIGNATURES` (one-line addition), never a bare numeric token.

### 7. `tests/benchmark/README.md`: provider runbook section

After the "Failure policy and warmup" section (which ends ~:145 with the shutdown note), add `## Dead generator provider (fail-fast + runbook)`:

- The live arm aborts with `ProviderDeathError` + exit code 3 + `aborted.json` when the generator is permanently dead (pre-warmup preflight, or first matching scenario failure). Stochastic faults keep per-scenario tolerance.
- Runbook: (a) top up DeepSeek at platform.deepseek.com (DeepSeek error docs: 402 = insufficient balance, fix = top up; verify with `curl https://api.deepseek.com/user/balance -H "Authorization: Bearer $DEEPSEEK_API_KEY"`); or (b) switch generator via env, e.g. verified MiniMax fallback:
  `GENERATOR_PROVIDER=minimax GENERATOR_MODEL=minimax/MiniMax-M2.7 GENERATOR_BASE_URL=https://api.minimax.io/v1` (key from `MINIMAXAI_API_KEY` via config expansion) plus `RETRIEVAL_USE_LEAN_WIRE_SCHEMA=true` (MiniMax emits malformed JSON on the fat `AgentSystemDesignResponse`; lean wire schema mitigates — known from 2026-09-27 live runs).
- Existing `--fail-fast` unchanged.

### 8. Env prerequisite (not a code edit)

The actual benchmarks/base rerun needs a funded provider. Default execution: keep DeepSeek defaults but require `DEEPSEEK_API_KEY` with positive balance (check via `/user/balance` first); if unfunded, run the verification arm against MiniMax env above. Provider choice stays env-driven; nothing is hardcoded.

## Critical files & anchors

- `tests/benchmark/harness/live.py` — `run_live_corpus` :207-263 (preflight call + mid-run classifier), `LiveComponents` :43-52 (+`agent` field), `build_live_components` :65-130 (return agent), new `ProviderDeathError` / `PROVIDER_DEATH_SIGNATURES` / `is_permanent_provider_death` / `preflight_generator`.
- `tests/benchmark/harness/main.py` — `_run_live` :313-391 (dedicated `ProviderDeathError` handler before :386), `EXIT_PROVIDER_DEAD = 3` near :36, lazy import at :325.
- `tests/benchmark/harness/selfcheck.py` — new `anchor_provider_death`, register in `run_selfchecks` :572-593.
- `tests/benchmark/README.md` — new runbook section after "Failure policy and warmup" (:120-145).
- `Makefile` — read-only reference: `benchmark-live` recipe ~:331-349 defaults `GENERATOR_PROVIDER=deepseek`; no edit needed (env-overridable already).

## Verification

Working dir: repo root. Prereqs: TEI bench sidecars up (`make benchmark-sidecars-up`); `CONFIG_PATH=$PWD/config/config.json` is set by the Makefile recipe.

1. `make benchmark-selfcheck` → exit 0, now 52 anchors (51 + `anchor_provider_death`), including "provider-death signatures match balance/credits/auth faults" PASS.
2. Abort path, dead provider (no funds needed — reproducible today): `GENERATOR_PROVIDER=openai GENERATOR_MODEL=gpt-4o-mini make benchmark-live LIMIT=1 OUT=benchmarks/deadprov FORCE=1` with the no-credits `OPENAI_API_KEY` → aborts in ≤ ~2 min (preflight: one tenacity cascade ~30 s then classifier hit), prints `ABORTED — generator provider permanently failed`, `benchmarks/deadprov/aborted.json` exists with `ProviderDeathError` reason, exit code 3. Confirm the abort happens BEFORE any scenario artifact is written (only aborted.json/env/manifest-lite files present).
3. Mid-run death path (optional, only if step 4 funded run shows it naturally): not separately staged — the classifier code path is identical to preflight classification; step 2's abort proves `ProviderDeathError` propagation + `mark_aborted` + exit 3.
4. Green path, funded provider: check balance first (`curl https://api.deepseek.com/user/balance -H "Authorization: Bearer $DEEPSEEK_API_KEY"` → `is_available: true`), then `make benchmark-live LIMIT=1 OUT=benchmarks/pfcheck FORCE=1` → exit 0, no `Thought generation failed` warnings, n=1 with a scored scenario (parse-fault tolerance may still zero a stochastic failure — acceptable, that is the designed policy; a provider-death abort is NOT acceptable here).
5. `make check-lint check-static-typing check-deadcode check-depcheck make test-unit` → all green (no `src/` changes, so gates should be unaffected; run to prove).
6. Delete throwaway dirs `benchmarks/deadprov`, `benchmarks/pfcheck` after evidence captured. Regenerate `benchmarks/base` only on user request (it currently holds the bad run as evidence).

## Assumptions & contingencies

- **Provider funding decision (user-overridable)**: plan assumes the user will either top up DeepSeek or run the MiniMax fallback env; the code change is provider-agnostic either way. Default documented in README; nothing hardcoded.
- If `_PreflightProbe` generation on a funded provider returns a parse-style failure (thinking model answering in prose): not a death signature → preflight passes silently; warmup/scenarios proceed as today. No action.
- If MiniMax fat-schema parse faults recur in the funded green-path run (step 4 on MiniMax): that is the known stochastic fault class — tolerated per policy, mitigated by `RETRIEVAL_USE_LEAN_WIRE_SCHEMA=true`; not a provider death, must NOT abort.
- If a new provider's permanent-death phrase is missing from `PROVIDER_DEATH_SIGNATURES` (e.g. Anthropic "credit balance too low"): add the exact phrase to the tuple + a `dead` case in `anchor_provider_death` in the same change; never add bare numeric tokens (request-id false positives, e.g. `b5b0466d`).
- `exit code 3` collides with nothing (`EXIT_REFUSAL=2`, offline `EXIT_INTEGRITY_FAILURE`, compare `EXIT_COMPARE_REFUSAL`); if a future gate needs 3, renumber then — not this change.
