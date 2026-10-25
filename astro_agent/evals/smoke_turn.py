"""Push one real turn through the agent's App (plugins included).

    BQ_ANALYTICS_DATASET=agent_analytics uv run python evals/smoke_turn.py ["question"]

Like the app: a session for the test user with a short-lived MCP token in
state (minted with the Pixel Astro server's scripts/mintAgentMcpToken.js;
PIXEL_ASTRO_SERVER_DIR). Needs the Node API on localhost:3000. With
BQ_ANALYTICS_DATASET set, the turn's events land in <dataset>.agent_events;
query them with evals/analytics.py.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
# The lab project and the deployed agent's settings; exported variables win.
for key, value in {
    "GOOGLE_GENAI_USE_VERTEXAI": "true",
    "GOOGLE_CLOUD_PROJECT": "ai-devcamp-lab",
    "PROJECT_ID": "ai-devcamp-lab",
    "GOOGLE_CLOUD_LOCATION": "global",
    "MODEL_ARMOR_TEMPLATE_ID": "pixel-astro-guardrails",
    "PII_REDACTION": "on",
}.items():
    os.environ.setdefault(key, value)

from google.adk.memory import InMemoryMemoryService  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

from pixel_astro_agent.agent import app  # noqa: E402

USER_ID = os.environ.get("EVAL_USER_ID", "6ad50ba9489d31a61484e9a1")
SERVER_DIR = os.environ.get("PIXEL_ASTRO_SERVER_DIR", os.path.expanduser("~/Pixel_Astro/pixel_astro_server"))
QUESTION = "What remedies should I do for my current dasha?"


async def main(question: str) -> None:
    token = subprocess.check_output(
        ["node", "scripts/mintAgentMcpToken.js", USER_ID], cwd=SERVER_DIR,
        env={**os.environ, "AGENT_MCP_TOKEN_TTL": "15m"}, text=True).strip()
    runner = Runner(app=app, session_service=InMemorySessionService(),
                    memory_service=InMemoryMemoryService())  # the agent calls load_memory first
    print("Plugins:", [p.name for p in runner.plugin_manager.plugins] or "none")
    session = await runner.session_service.create_session(
        app_name=app.name, user_id=USER_ID, state={"user:pixel_astro_token": token})
    try:
        async for event in runner.run_async(
            user_id=USER_ID, session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=question)]),
        ):
            for part in (event.content.parts if event.content else []):
                if part.function_call:
                    print(f"[{event.author}] -> {part.function_call.name}")
                elif part.text and not part.thought and event.author == app.root_agent.name:
                    print(f"[{event.author}] {part.text[:300]}")
    finally:
        await runner.close()  # flushes queued rows to BigQuery
    print("Session:", session.id)


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or QUESTION))
