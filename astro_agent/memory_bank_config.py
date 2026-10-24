"""Inspect or apply the preference-only Memory Bank config to Agent Runtime."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import vertexai
from pixel_astro_agent.memory_config import memory_bank_config
from vertexai._genai.types import AgentEngineConfig, ReasoningEngineContextSpec

METADATA_PATH = Path(__file__).with_name("deployment_metadata.json")


def _engine_id_from_metadata() -> str | None:
    if not METADATA_PATH.is_file():
        return None
    with METADATA_PATH.open(encoding="utf-8") as metadata_file:
        metadata = json.load(metadata_file)
    return metadata.get("remote_agent_runtime_id")


def _resource_name(project: str, location: str, engine_id: str) -> str:
    if engine_id.startswith("projects/"):
        return engine_id
    return f"projects/{project}/locations/{location}/reasoningEngines/{engine_id}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect or configure Memory Bank on the Pixel Astro Agent Runtime."
    )
    parser.add_argument("action", choices=("apply", "show"))
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument(
        "--location",
        default=os.environ.get("AGENT_ENGINE_LOCATION", "us-central1"),
    )
    parser.add_argument(
        "--engine-id",
        default=os.environ.get("AGENT_ENGINE_ID") or _engine_id_from_metadata(),
    )
    args = parser.parse_args()
    if not args.project or not args.engine_id:
        parser.error(
            "Set GOOGLE_CLOUD_PROJECT and AGENT_ENGINE_ID or pass --project and --engine-id."
        )

    client = vertexai.Client(project=args.project, location=args.location)
    name = _resource_name(args.project, args.location, args.engine_id)
    engine = client.agent_engines.get(name=name)

    if args.action == "apply":
        engine = client.agent_engines.update(
            name=name,
            config=AgentEngineConfig(
                context_spec=ReasoningEngineContextSpec(
                    memory_bank_config=memory_bank_config,
                )
            ),
        )

    context_spec = getattr(engine.api_resource, "context_spec", None)
    configured_memory = getattr(context_spec, "memory_bank_config", None)
    print(f"Agent Runtime engine: {name}")
    print(f"Memory Bank configuration: {configured_memory or 'not configured'}")


if __name__ == "__main__":
    main()
