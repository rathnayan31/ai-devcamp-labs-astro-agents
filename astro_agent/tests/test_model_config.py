from google.adk.models import Gemini

from pixel_astro_agent.guardrails import GuardedGemini
from pixel_astro_agent.model_config import configured_model


def test_vertex_model_uses_configured_cloud_location(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    model = configured_model("gemini-2.5-flash")

    assert isinstance(model, Gemini)
    assert model.model == "gemini-2.5-flash"
    assert model.client_kwargs == {"location": "us-central1"}


def test_vertex_model_defaults_to_global_when_location_is_not_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)

    model = configured_model("gemini-2.5-flash")

    assert isinstance(model, Gemini)
    assert model.client_kwargs == {"location": "global"}


def test_guarded_model_carries_model_armor_retries(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("MODEL_ARMOR_TEMPLATE_ID", "pixel-astro-guardrails")
    monkeypatch.setenv("PROJECT_ID", "ai-devcamp-lab")

    model = configured_model("gemini-3.8-flash")

    assert isinstance(model, GuardedGemini)
    assert model.retry_options.attempts == 8


def test_non_vertex_model_keeps_existing_string_configuration(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "false")

    assert configured_model("gemini-2.5-flash") == "gemini-2.5-flash"
