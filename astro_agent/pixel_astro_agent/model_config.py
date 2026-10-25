"""Model client configuration for local and deployed agents."""

from __future__ import annotations

import os

from google.adk.models import Gemini

from .guardrails import GuardedGemini, retry_options


def configured_model(model_name: str) -> str | Gemini:
    """Pin Vertex model requests to the configured location, with the Model
    Armor retry and no-streaming rules (guardrails.py)."""
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() not in {
        "true",
        "1",
        "yes",
    }:
        return model_name

    return GuardedGemini(
        model=model_name,
        client_kwargs={
            "location": os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        },
        retry_options=retry_options(),
    )
