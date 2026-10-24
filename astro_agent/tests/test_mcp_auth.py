"""Offline checks for the app-server MCP token contract."""

from types import SimpleNamespace

from pixel_astro_agent.mcp_auth import AGENT_MCP_TOKEN_STATE_KEY
from pixel_astro_agent.toolsets import _auth_headers


def test_mcp_header_uses_short_lived_token_from_server_state_delta():
    context = SimpleNamespace(
        state={AGENT_MCP_TOKEN_STATE_KEY: " server-minted-agent-token "}
    )

    assert _auth_headers(context) == {
        "Authorization": "Bearer server-minted-agent-token"
    }


def test_missing_state_token_does_not_use_raw_user_jwt_or_runtime_env(monkeypatch):
    monkeypatch.setenv(
        "APP_URL",
        "https://us-central1-aiplatform.googleapis.com/"
        "reasoningEngines/v1/projects/123/locations/us-central1/"
        "reasoningEngines/456/api",
    )
    monkeypatch.setenv("PIXEL_ASTRO_USER_TOKEN", "raw-app-jwt")
    monkeypatch.setenv("PIXEL_ASTRO_AGENT_MCP_TOKEN", "static-runtime-token")

    assert _auth_headers(SimpleNamespace(state={})) == {}


def test_local_development_may_use_an_explicit_mcp_only_token(monkeypatch):
    monkeypatch.delenv("APP_URL", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_AGENT_ENGINE_ID", raising=False)
    monkeypatch.delenv("PIXEL_ASTRO_USER_TOKEN", raising=False)
    monkeypatch.setenv("PIXEL_ASTRO_AGENT_MCP_TOKEN", "local-agent-mcp-token")

    assert _auth_headers(SimpleNamespace(state={})) == {
        "Authorization": "Bearer local-agent-mcp-token"
    }
