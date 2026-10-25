"""Model Armor guardrails on every Gemini call (Lab 3: Govern).

Two templates (gcp-setup.sh): the request template screens the user's message
(injection, jailbreak, harmful content); the response template screens every
reply (harmful content only: injection detection fires on replies that merely
talk about injection).

Two ways to apply them, picked automatically:

- **inline** (the lab's route), when Gemini runs in the templates' region:
  each agent names the templates in ``generate_content_config`` and Gemini's
  service agent makes the call. The root screens input and output;
  specialists only output (their input is the root's own request).
- **api**, when Gemini runs anywhere else. In ai-devcamp-lab only Gemini 3.8
  Flash on ``global`` is available, and ``global`` can't use regional
  templates (400 TEMPLATE_NOT_FOUND). So screening.py screens the user's
  message with ``sanitizeUserPrompt`` before ADK sees it, and ``guard_reply``
  screens each reply with ``sanitizeModelResponse``. Both go over mTLS
  (gcp.py), which is what makes them work from inside Agent Runtime.

Either way a block becomes the same polite refusal, and both fail closed.

Streamed calls aren't screened inline, and a streamed reply would reach the
user before ``guard_reply`` saw all of it, so while guardrails are on
``GuardedGemini`` never streams. Replies arrive whole.

Configure with:
    MODEL_ARMOR_TEMPLATE_ID   request template, e.g. pixel-astro-guardrails
                              (blank or "off": guardrails off)
    MODEL_ARMOR_OUTPUT_TEMPLATE_ID  response template (default <request>-output)
    MODEL_ARMOR_REGION        template region (default us-central1)
    PROJECT_ID                project ID, not number (default GOOGLE_CLOUD_PROJECT)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import AsyncGenerator

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import Gemini, LlmRequest, LlmResponse
from google.genai import types

from .gcp import api_url, authorized_session, project_id

log = logging.getLogger(__name__)

BLOCKED_REPLY = (
    "I can't help with that request: it was flagged by our content safety checks. "
    "I'm happy to answer questions about your kundali, dashas, compatibility or remedies."
)


class ScreeningUnavailable(RuntimeError):
    """Model Armor couldn't be reached or answered with an error."""


def _template_id() -> str:
    value = os.environ.get("MODEL_ARMOR_TEMPLATE_ID", "").strip()
    return "" if value.lower() in ("", "off", "none", "false") else value


def _output_template_id() -> str:
    return os.environ.get("MODEL_ARMOR_OUTPUT_TEMPLATE_ID") or f"{_template_id()}-output"


def _region() -> str:
    return os.environ.get("MODEL_ARMOR_REGION", "us-central1")


def model_armor_enabled() -> bool:
    return bool(_template_id() and project_id())


def inline_screening() -> bool:
    """Inline only works when Gemini runs in the templates' region."""
    return model_armor_enabled() and os.environ.get("GOOGLE_CLOUD_LOCATION", "global") == _region()


def api_screening() -> bool:
    return model_armor_enabled() and not inline_screening()


def _template_path(template_id: str) -> str:
    return f"projects/{project_id()}/locations/{_region()}/templates/{template_id}"


def content_config(screen_input: bool = True) -> types.GenerateContentConfig | None:
    """Inline Model Armor templates for one agent, or None (off, or api mode)."""
    if not inline_screening():
        return None
    return types.GenerateContentConfig(
        model_armor_config=types.ModelArmorConfig(
            prompt_template_name=_template_path(_template_id()) if screen_input else None,
            response_template_name=_template_path(_output_template_id()),
        )
    )


def _sanitize(method: str, template_id: str, field: str, text: str) -> str | None:
    """The matched filters if ``template_id`` blocks ``text``, else None."""
    url = api_url(
        f"modelarmor.{_region()}.rep.googleapis.com",
        f"/v1/{_template_path(template_id)}:{method}",
    )
    try:
        resp = authorized_session().post(url, json={field: {"text": text}}, timeout=10)
    except Exception as e:  # noqa: BLE001  (network, credentials)
        raise ScreeningUnavailable(str(e)) from e
    if resp.status_code != 200:
        raise ScreeningUnavailable(f"Model Armor responded {resp.status_code}: {resp.text[:200]}")
    result = resp.json()["sanitizationResult"]
    if result.get("filterMatchState") != "MATCH_FOUND":
        return None
    return ", ".join(
        name
        for name, found in result.get("filterResults", {}).items()
        if any(isinstance(v, dict) and v.get("matchState") == "MATCH_FOUND" for v in found.values())
    ) or "match"


async def screen_user_message(text: str) -> str | None:
    """api mode: matched filters if the request template blocks ``text``.
    Raises ScreeningUnavailable."""
    if not api_screening() or not text.strip():
        return None
    return await asyncio.to_thread(
        _sanitize, "sanitizeUserPrompt", _template_id(), "userPromptData", text
    )


def _refusal(replaced: LlmResponse) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part.from_text(text=BLOCKED_REPLY)]),
        custom_metadata=replaced.custom_metadata,
    )


async def guard_reply(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> LlmResponse | None:
    """after_model_callback on every agent: replace a blocked reply with the refusal.

    inline: Model Armor's block comes back as ``error_code`` MODEL_ARMOR.
    api: the reply text is screened against the response template here; if
    Model Armor can't be reached, the reply is withheld (fail closed).
    """
    agent = callback_context.agent_name
    if llm_response.error_code == "MODEL_ARMOR":
        log.warning("Model Armor blocked a call by %s: %s", agent, llm_response.error_message)
        return _refusal(llm_response)
    if not api_screening() or llm_response.partial:
        return None
    parts = llm_response.content.parts if llm_response.content else None
    text = "".join(p.text for p in parts or [] if p.text and not p.thought)
    if not text.strip():
        return None
    try:
        blocked = await asyncio.to_thread(
            _sanitize, "sanitizeModelResponse", _output_template_id(), "modelResponseData", text
        )
    except ScreeningUnavailable as e:
        log.error("Model Armor unavailable, withholding reply by %s: %s", agent, e)
        return _refusal(llm_response)
    if blocked:
        log.warning("Model Armor blocked a reply by %s (%s)", agent, blocked)
        return _refusal(llm_response)
    return None


def retry_options() -> types.HttpRetryOptions | None:
    """Retries on the model object (set anywhere else, they're ignored once
    deployed). Inline, the template lookup intermittently fails with 400
    "template not found", so 400 is retried while guardrails are on."""
    if not model_armor_enabled():
        return None
    return types.HttpRetryOptions(
        attempts=8,
        initial_delay=0.3,
        max_delay=8.0,
        exp_base=2.0,
        jitter=0.3,
        http_status_codes=[400, 429] if inline_screening() else [429, 500, 503],
    )


def _log_usage(model: str, usage: types.GenerateContentResponseUsageMetadata) -> None:
    """Append one model call's token counts to PIXEL_ASTRO_USAGE_LOG (JSON lines).

    For costing eval runs (Lab 4 Step 4, evals/cost.py). Specialists called as
    AgentTools run in their own sessions, so the eval's own token count misses
    them; this sees every call. Off unless the variable is set.
    """
    path = os.environ.get("PIXEL_ASTRO_USAGE_LOG")
    if not path:
        return
    with open(path, "a") as f:
        f.write(json.dumps({
            "model": model,
            "prompt": usage.prompt_token_count or 0,
            "cached": usage.cached_content_token_count or 0,
            "output": usage.candidates_token_count or 0,
            "thinking": usage.thoughts_token_count or 0,
        }) + "\n")


class GuardedGemini(Gemini):
    """Gemini that doesn't stream while Model Armor is on (see module docstring)."""

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        async for response in super().generate_content_async(
            llm_request, stream=stream and not model_armor_enabled()
        ):
            if response.usage_metadata and not response.partial:
                _log_usage(self.model, response.usage_metadata)
            yield response
