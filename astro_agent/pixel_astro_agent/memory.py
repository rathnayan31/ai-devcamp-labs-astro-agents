"""Explicit, allowlisted response-style preferences for Memory Bank."""

from __future__ import annotations

from typing import Literal, get_args

from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.tools.tool_context import ToolContext
from google.genai import types

ResponsePreference = Literal[
    "concise",
    "detailed",
    "warm",
    "formal",
    "bullet_points",
    "prose",
]
PENDING_PREFERENCE_KEY = "temp:pending_response_preference"


def remember_response_preference(
    preference: ResponsePreference,
    tool_context: ToolContext,
) -> dict[str, str]:
    """Queue an explicitly requested, supported response-style preference."""
    if preference not in get_args(ResponsePreference):
        raise ValueError("Unsupported response preference cannot be saved.")
    tool_context.state[PENDING_PREFERENCE_KEY] = preference
    return {"status": "queued", "preference": preference}


async def save_explicit_preference(callback_context: CallbackContext) -> None:
    """Send only the canonical preference event, never the conversation."""
    preference = callback_context.state.get(PENDING_PREFERENCE_KEY)
    if preference is None:
        return
    if preference not in get_args(ResponsePreference):
        raise ValueError("Unsupported response preference cannot be saved.")

    event = Event(
        author="user",
        content=types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=f"Explicitly requested response-style preference: {preference}."
                )
            ],
        ),
    )
    await callback_context.add_events_to_memory(events=[event])
    callback_context.state[PENDING_PREFERENCE_KEY] = None
