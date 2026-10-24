"""Offline checks for Agent Runtime service identity parsing."""

import pytest
from pixel_astro_agent.app_utils.services import _agent_engine_details


def test_agent_runtime_details_come_from_app_url_not_model_location(monkeypatch):
    monkeypatch.setenv(
        "APP_URL",
        "https://us-central1-aiplatform.googleapis.com/"
        "reasoningEngines/v1/projects/123/locations/us-central1/"
        "reasoningEngines/456/api",
    )
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")

    assert _agent_engine_details() == ("123", "us-central1", "456")


def test_invalid_runtime_app_url_fails_explicitly(monkeypatch):
    monkeypatch.setenv("APP_URL", "https://example.test/reasoningEngines/not-an-engine")

    with pytest.raises(ValueError, match="invalid Agent Runtime resource name"):
        _agent_engine_details()


def test_local_app_url_uses_in_memory_services(monkeypatch):
    monkeypatch.setenv("APP_URL", "http://127.0.0.1:8000")
    monkeypatch.delenv("GOOGLE_CLOUD_AGENT_ENGINE_ID", raising=False)

    assert _agent_engine_details() is None
