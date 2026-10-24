from google.adk.models import Gemini

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


def test_non_vertex_model_keeps_existing_string_configuration(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "false")

    assert configured_model("gemini-2.5-flash") == "gemini-2.5-flash"
