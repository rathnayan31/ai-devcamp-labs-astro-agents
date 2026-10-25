"""Screen the user's message before ADK sees it (Lab 3: Govern).

Pure ASGI middleware on every route that carries a user message:

    /run, /run_sse                   ADK API (the Pixel Astro server uses these)
    /api/stream_reasoning_engine     native streamQuery
    /a2a/pixel_astro_agent           A2A JSON-RPC

1. Cloud DLP redacts contact details and ID numbers (pii.py, PII_REDACTION=on),
   so raw values never reach Gemini, the session store or Memory Bank.
2. In api mode, Model Armor screens the redacted message against the request
   template (guardrails.py). A match is answered with the polite refusal, in
   the route's own response shape, and never reaches the agent.

Both fail closed: if DLP or Model Armor can't be reached, the request gets 503
and the message is never passed on unscreened.
"""

from __future__ import annotations

import json
import logging
import uuid

from starlette.responses import JSONResponse, Response

from .guardrails import BLOCKED_REPLY, ScreeningUnavailable, api_screening, screen_user_message
from .pii import RedactionUnavailable, pii_redaction_enabled, redact_texts

log = logging.getLogger(__name__)

NATIVE_PATH = "/api/stream_reasoning_engine"
A2A_PATH = "/a2a/pixel_astro_agent"
UNAVAILABLE = {
    "error": "Message screening is unavailable right now, so it wasn't sent. Please try again shortly."
}


def _message_slots(path: str, payload: dict):
    """(container, key) pairs holding user text in an agent request."""
    if path == NATIVE_PATH:
        args = payload.get("input")
        if isinstance(args, dict) and isinstance(args.get("message"), str):
            yield args, "message"
        return
    if path == A2A_PATH:
        message = (payload.get("params") or {}).get("message") or {}
    else:
        message = payload.get("new_message") or payload.get("newMessage") or {}
    if message.get("role", "user") not in ("user", "ROLE_USER"):
        return
    for part in message.get("parts") or []:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            yield part, "text"


def _refusal(path: str, payload: dict) -> Response:
    """The polite refusal as one agent reply, shaped like the route's response."""
    if path == A2A_PATH:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "result": {
                "kind": "message",
                "role": "agent",
                "messageId": str(uuid.uuid4()),
                "parts": [{"kind": "text", "text": BLOCKED_REPLY}],
            },
        })
    event = {
        "id": str(uuid.uuid4()),
        "invocationId": f"e-{uuid.uuid4()}",
        "author": "pixel_astro_root",
        "content": {"role": "model", "parts": [{"text": BLOCKED_REPLY}]},
    }
    if path == "/run_sse":
        return Response(f"data: {json.dumps(event)}\n\n", media_type="text/event-stream")
    if path == NATIVE_PATH:
        return Response(json.dumps(event) + "\n", media_type="application/json")
    return JSONResponse([event])


class ScreenUserMessages:
    """Raw ASGI, not BaseHTTPMiddleware, because the body is rewritten. The
    handler gets the new body once and then the real ``receive``, so it still
    sees the client disconnect; answering every later receive() with an empty
    body instead makes streaming responses spin."""

    PATHS = frozenset({"/run", "/run_sse", NATIVE_PATH, A2A_PATH})

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] not in self.PATHS
            or not (pii_redaction_enabled() or api_screening())
        ):
            return await self.app(scope, receive, send)

        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            if not message.get("more_body"):
                break

        try:
            payload = json.loads(body)
        except ValueError:
            payload = None  # not JSON: the handler rejects it, nothing to screen
        if isinstance(payload, dict):
            path = scope["path"]
            slots = list(_message_slots(path, payload))
            try:
                redacted = await redact_texts([c[k] for c, k in slots])
                blocked = await screen_user_message("\n".join(redacted))
            except (RedactionUnavailable, ScreeningUnavailable) as e:
                log.error("Screening unavailable, refusing message: %s", e)
                return await JSONResponse(UNAVAILABLE, status_code=503)(scope, receive, send)
            if blocked:
                log.warning("Model Armor blocked a user message (%s)", blocked)
                return await _refusal(path, payload)(scope, receive, send)
            changed = [(c, k, new) for (c, k), new in zip(slots, redacted) if c[k] != new]
            if changed:
                for container, key, new in changed:
                    container[key] = new
                log.info("Redacted personal data in %d message part(s)", len(changed))
                body = json.dumps(payload).encode()

        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        headers = [(k, v) for k, v in scope["headers"] if k != b"content-length"]
        headers.append((b"content-length", str(len(body)).encode()))
        await self.app({**scope, "headers": headers}, replay, send)
