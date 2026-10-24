"""Offline checks for preference-only Memory Bank behavior."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pixel_astro_agent.memory import (
    PENDING_PREFERENCE_KEY,
    remember_response_preference,
    save_explicit_preference,
)
from pixel_astro_agent.memory_config import MEMORY_TTL, memory_bank_config
from vertexai._genai.types import ManagedTopicEnum


def test_memory_bank_only_enables_user_preferences():
    topics = memory_bank_config.customization_configs[0].memory_topics
    assert len(topics) == 1
    assert (
        topics[0].managed_memory_topic.managed_topic_enum
        is ManagedTopicEnum.USER_PREFERENCES
    )


def test_memories_expire_after_90_days():
    assert MEMORY_TTL == "7776000s"
    assert memory_bank_config.ttl_config.default_ttl == MEMORY_TTL


def test_preference_tool_stages_only_supported_values():
    context = SimpleNamespace(state={})

    result = remember_response_preference("concise", context)

    assert result == {"status": "queued", "preference": "concise"}
    assert context.state == {PENDING_PREFERENCE_KEY: "concise"}


def test_preference_tool_rejects_free_form_values():
    with pytest.raises(ValueError, match="Unsupported response preference"):
        remember_response_preference("birth details", SimpleNamespace(state={}))


def test_callback_sends_only_the_canonical_preference_event():
    add_events_to_memory = AsyncMock()
    context = SimpleNamespace(
        state={PENDING_PREFERENCE_KEY: "concise"},
        add_events_to_memory=add_events_to_memory,
    )

    asyncio.run(save_explicit_preference(context))

    events = add_events_to_memory.await_args.kwargs["events"]
    assert len(events) == 1
    assert events[0].author == "user"
    assert events[0].content.parts[0].text == (
        "Explicitly requested response-style preference: concise."
    )
    assert context.state[PENDING_PREFERENCE_KEY] is None


def test_callback_does_not_write_an_invalid_preference():
    add_events_to_memory = AsyncMock()
    context = SimpleNamespace(
        state={PENDING_PREFERENCE_KEY: "personal chart"},
        add_events_to_memory=add_events_to_memory,
    )

    with pytest.raises(ValueError, match="Unsupported response preference"):
        asyncio.run(save_explicit_preference(context))

    add_events_to_memory.assert_not_awaited()
