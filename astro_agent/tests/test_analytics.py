"""Offline checks for Lab 4: analytics logs no text, and the CI token minter."""

import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path

from pixel_astro_agent import analytics

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from mint_token import AUDIENCE, SCOPE, mint  # noqa: E402


def test_no_plugin_without_dataset(monkeypatch):
    monkeypatch.delenv("BQ_ANALYTICS_DATASET", raising=False)
    assert analytics.analytics_plugins() == []


def test_content_keeps_counts_and_tool_names_only():
    content = {
        "response": "You are running Rahu mahadasha",
        "usage": {"prompt": 1905, "completion": 18},
        "tool": "get_dasha_periods",
        "args": {"kundali_id": "6ad50bb0489d31a61484e9b2"},
        "result": {"token": "eyJhbGciOi"},
    }

    logged = analytics.content_without_text(content, "LLM_RESPONSE")

    assert logged["usage"] == {"prompt": 1905, "completion": 18}
    assert logged["tool"] == "get_dasha_periods"
    assert {logged["response"], logged["args"], logged["result"]} == {analytics.NOT_LOGGED}
    assert analytics.content_without_text("Which dasha am I in?", "USER_MESSAGE_RECEIVED") == analytics.NOT_LOGGED


def test_state_deltas_are_never_logged(monkeypatch):
    monkeypatch.setenv("BQ_ANALYTICS_DATASET", "agent_analytics")
    monkeypatch.setenv("PROJECT_ID", "ai-devcamp-lab")
    (plugin,) = analytics.analytics_plugins()
    config = plugin.config if hasattr(plugin, "config") else plugin._config

    assert "STATE_DELTA" in config.event_denylist
    assert config.log_session_metadata is False


def _b64decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def test_minted_token_matches_the_server_scheme():
    token = mint("6ad50ba9489d31a61484e9a1", "s3cret", ttl=60)
    header, payload, signature = token.split(".")
    claims = json.loads(_b64decode(payload))
    key = hmac.new(b"s3cret", f"{AUDIENCE}:v1".encode(), hashlib.sha256).hexdigest().encode()
    expected = hmac.new(key, f"{header}.{payload}".encode(), hashlib.sha256).digest()

    assert json.loads(_b64decode(header))["alg"] == "HS256"
    assert claims["sub"] == "6ad50ba9489d31a61484e9a1"
    assert claims["aud"] == AUDIENCE and claims["scope"] == SCOPE
    assert claims["exp"] - claims["iat"] == 60
    assert hmac.compare_digest(_b64decode(signature), expected)
