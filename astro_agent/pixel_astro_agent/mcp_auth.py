"""Agent MCP authorization supplied by the Pixel Astro app server."""

from __future__ import annotations

import os
from collections.abc import Mapping

AGENT_MCP_TOKEN_STATE_KEY = "user:pixel_astro_token"


def get_agent_mcp_token(state: Mapping[str, object]) -> str | None:
    """Read the short-lived MCP-only token set by the app server in state_delta."""
    token = state.get(AGENT_MCP_TOKEN_STATE_KEY)
    return token.strip() if isinstance(token, str) and token.strip() else None


def is_agent_runtime() -> bool:
    return bool(
        os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID")
        or "reasoningEngines" in os.environ.get("APP_URL", "")
    )
