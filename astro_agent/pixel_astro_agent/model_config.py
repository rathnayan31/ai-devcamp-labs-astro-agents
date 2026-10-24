"""Model client configuration for local and deployed agents."""

from __future__ import annotations

import os

from google.adk.models import Gemini


def configured_model(model_name: str) -> str | Gemini:
    """Pin Vertex model requests to the configured location."""
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() not in {
        "true",
        "1",
        "yes",
    }:
        return model_name

    return Gemini(
        model=model_name,
        client_kwargs={
            "location": os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        },
    )
