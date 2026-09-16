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
Self-healing validation with Pydantic lax mode and retry loop.

When LLM-structured output fails Pydantic validation, this module formats
the error into a correction prompt and retries generation with feedback.

The retry loop:
    1. Attempt structured generation via LiteLLM.as_structured_llm
    2. On ValidationError, extract error details → correction prompt
    3. Retry with corrected user prompt (up to max_retries)
    4. Return best-effort result or raise

Additionally, when the raw LLM output fails JSON *parsing* (pydantic
``json_invalid`` — e.g. unquoted object keys, trailing commas, or code
fences around the payload), :func:`repair_json_validation_error` applies a
bounded tolerant cleanup to the raw text and revalidates against the
schema before any new LLM call is spent on the failure.

Used by: AgentSystemArchitect.generate_structured
"""

import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.agent import LLMError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def format_validation_errors(exc: ValidationError) -> str:
    """
    Format a Pydantic ValidationError into a human-readable correction prompt.

    Args:
        exc: Pydantic ValidationError from failed model validation

    Returns:
        Plain-text description of each field error for inclusion in retry prompt
    """
    lines = ["The following fields failed validation:"]
    for err in exc.errors():
        loc = ".".join(str(l) for l in err["loc"])
        msg = err["msg"]
        inp = repr(err["input"])[:80]
        lines.append(f"  - {loc}: {msg} (got: {inp})")
    return "\n".join(lines)


# Unquoted object key after `{` or `,`: `{type: "object"}`. Key chars and the
# following colon are matched explicitly; the rewrite itself is done by a
# string-aware scanner so quoted values are never touched.
_BARE_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]*\s*:")
# Markdown code fences some models wrap payloads in.
_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9]*\s*|\s*```\s*$")

_WS = " \t\r\n"


def _match_bare_key(text: str, start: int) -> tuple[int, int, str] | None:
    """Match a bare object key (plus colon) after optional whitespace.

    Returns ``(ws_start, next_index, quoted_key)`` where ``ws_start`` is the
    first whitespace char position, ``next_index`` the index just past the
    colon, and ``quoted_key`` the key rewritten with double quotes — or None
    when no bare key starts at ``start``.
    """
    j = start
    n = len(text)
    while j < n and text[j] in _WS:
        j += 1
    match = _BARE_KEY_RE.match(text, j)
    if match is None:
        return None
    key_part = match.group(0)
    colon_at = key_part.rindex(":")
    return start, j + len(key_part), f'"{key_part[:colon_at].rstrip()}":'


def _copy_string(text: str, start: int, out: list[str]) -> int:
    """Copy the JSON string starting at ``text[start]`` (a double quote) into
    ``out``, honouring backslash escapes; return the index just past the
    closing quote."""
    i = start + 1
    n = len(text)
    out.append('"')
    while i < n:
        ch = text[i]
        out.append(ch)
        i += 1
        if ch == "\\" and i < n:
            out.append(text[i])
            i += 1
            continue
        if ch == '"':
            break
    return i


def _tolerant_json_loads(text: str) -> dict[str, Any] | None:
    """Best-effort parse of slightly-malformed LLM JSON output.

    Applies two bounded, string-aware fixes before a plain ``json.loads``:

    - quote unquoted object keys (``{type: "object"}`` →
      ``{"type": "object"}``), the defect pydantic reports as
      ``json_invalid: key must be a string``;
    - drop trailing commas before closing brackets.

    Quoted values are copied atomically (``"we {care: deeply}"`` is left
    untouched). Returns the parsed object, or None when the payload still
    fails to parse.
    """
    candidate = _FENCE_RE.sub("", text).strip()
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        return None
    candidate = candidate[start : end + 1]

    out: list[str] = []
    i, n = 0, len(candidate)
    while i < n:
        ch = candidate[i]
        if ch == '"':
            i = _copy_string(candidate, i, out)
            continue

        if ch == "{":
            out.append(ch)
            i += 1
            found = _match_bare_key(candidate, i)
            if found:
                ws_end, nxt, quoted = found
                out.append(candidate[i:ws_end])
                out.append(quoted)
                i = nxt
            continue

        if ch == ",":
            found = _match_bare_key(candidate, i + 1)
            if found:
                ws_start, nxt, quoted = found
                out.append(",")
                out.append(candidate[i + 1 : ws_start])
                out.append(quoted)
                i = nxt
                continue
            j = i + 1
            while j < n and candidate[j] in _WS:
                j += 1
            if j < n and candidate[j] in "}]":
                i = j  # trailing comma before a closing bracket: drop it
            else:
                out.append(ch)
                i += 1
            continue

        out.append(ch)
        i += 1

    try:
        payload = json.loads("".join(out))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def repair_json_validation_error(
    exc: ValidationError, response_schema: type[BaseModel]
) -> BaseModel | None:
    """Attempt tolerant recovery of an LLM output that failed JSON *parsing*.

    pydantic ``json_invalid`` errors (unquoted object keys, trailing commas,
    code fences, stray prose around the payload) carry the full raw text in
    the first error entry's ``input``. This applies a bounded cleanup to that
    text and revalidates against the schema — cheaper and more reliable than
    spending another LLM call on a repair prompt that does not mention the
    defect.

    Args:
        exc: ValidationError whose errors() include a ``json_invalid`` entry
             with the raw output text as ``input``.
        response_schema: The schema to revalidate the repaired payload against.

    Returns:
        A validated model instance, or None when the error is not a
        JSON-parsing failure or the cleanup cannot produce valid JSON.
    """
    raw: Any | None = None
    for err in exc.errors():
        if err.get("type") == "json_invalid" and isinstance(err.get("input"), str):
            raw = err["input"]
            break
    if raw is None:
        return None

    payload = _tolerant_json_loads(raw)
    if payload is None:
        logger.warning("Tolerant JSON repair could not produce valid JSON")
        return None

    try:
        repaired = response_schema.model_validate(payload)
    except ValidationError as repair_exc:
        logger.warning(
            "Tolerant JSON repair produced parseable but invalid payload",
            extra={"errors": repair_exc.errors(include_url=False)[:3]},
        )
        return None

    logger.warning(
        "Recovered LLM output via tolerant JSON repair (unquoted keys / "
        "trailing commas cleaned up before schema validation)"
    )
    return repaired


async def validate_with_retries(  # noqa: UP047
    initial_caller: Callable[[], Awaitable[T]],
    repair_caller: Callable[[str, str], Awaitable[T]],
    response_schema: type[T],
    *,
    max_retries: int = 3,
    system_prompt: str = "",
    user_prompt: str = "",
) -> T:
    """
    Generate a structured response with self-healing async retry on validation failure.

    Calls initial_caller for the first attempt. On ValidationError or LLMError,
    calls repair_caller with corrected prompts up to max_retries times.

    Args:
        initial_caller: Zero-arg async callable returning first structured generation attempt.
                        Raises ValidationError or LLMError on failure.
        repair_caller: Async callable(system_prompt, user_prompt) for repair attempts.
                       Must NOT retry — only one attempt per call.
        response_schema: Pydantic model class used for validation (for error messages).
        max_retries: Maximum self-healing retry attempts (default 3).
        system_prompt: Original system prompt (forwarded unchanged to repair_caller).
        user_prompt: Original user prompt (used as base; repair appends error context).

    Returns:
        Validated Pydantic model instance.

    Raises:
        ValidationError: If all attempts (including repairs) fail validation.
        LLMError: If all attempts fail with provider errors after retries exhausted.
    """
    last_error: Exception | None = None
    original_error: Exception | None = None

    try:
        return await initial_caller()
    except ValidationError as exc:
        last_error = exc
        original_error = exc
    except LLMError as exc:
        last_error = exc
        original_error = exc

    for attempt in range(max_retries):
        if original_error is None:
            raise RuntimeError("validate_with_retries: original_error is None")

        if isinstance(original_error, ValidationError):
            errors_str = format_validation_errors(original_error)
            repair_user_prompt = (
                f"{user_prompt}\n\n"
                "IMPORTANT: Your previous response failed validation.\n"
                f"{errors_str}\n\n"
                f"Please produce a new response that conforms exactly to the schema "
                f"for {response_schema.__name__}. "
                "Double-check every field before responding."
            )
        elif isinstance(original_error, LLMError):
            errors_str = f"LLM provider error: {original_error.provider_message}"
            repair_user_prompt = (
                f"{user_prompt}\n\n"
                f"IMPORTANT: previous LLM call failed with: {original_error.provider_message}\n"
                f"Please produce a new response conforming to {response_schema.__name__}."
            )
        else:
            raise original_error from None

        logger.debug(
            "Self-healing repair attempt %d",
            attempt + 1,
            extra={"error": errors_str[:200]},
        )

        try:
            return await repair_caller(system_prompt, repair_user_prompt)
        except ValidationError as exc:
            last_error = exc
        except LLMError as exc:
            last_error = exc
        except Exception as exc:
            logger.warning("Self-healing repair call failed: %s", exc)
            last_error = exc

    if original_error is not None:
        raise original_error from None
    raise RuntimeError(
        f"validate_with_retries: all {max_retries + 1} attempts failed without known error"
    )
