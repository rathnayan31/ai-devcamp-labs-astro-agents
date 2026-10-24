"""Verify the Lab 2 (Scale) assignment against the deployed Agent Runtime.

Calls the engine the way the Pixel Astro server does (services/agentRuntimeClient.js):
ADK session routes plus /run with the server-minted MCP token in ``state_delta``.

  1. Session A: the user explicitly asks to remember a response style.
  2. Memory Bank: a USER_PREFERENCES memory appears for that user, with no
     credential or kundali ID in it.
  3. Session B (new session, same user): a chart question. The agent calls
     ``load_memory`` and answers from the read-only MCP tools.
  4. Session B is read back from managed Sessions by a separate request.

Usage:
  PIXEL_ASTRO_TEST_AGENT_TOKEN=<short-lived MCP token> \\
  uv run python verify_scale.py --user-id <pixel astro user id>
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

import google.auth
import google.auth.transport.requests

APP_NAME = "pixel_astro_agent"
TOKEN_STATE_KEY = "user:pixel_astro_token"
METADATA_PATH = Path(__file__).with_name("deployment_metadata.json")


class Engine:
    def __init__(self, resource: str, location: str) -> None:
        self.resource = resource
        self.api = f"https://{location}-aiplatform.googleapis.com/reasoningEngines/v1/{resource}/api"
        self.rest = f"https://{location}-aiplatform.googleapis.com/v1beta1/{resource}"
        self.credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

    def _call(self, method: str, url: str, body: dict | None = None) -> dict | list:
        self.credentials.refresh(google.auth.transport.requests.Request())
        request = urllib.request.Request(
            url,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.credentials.token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read() or b"{}")

    def new_session(self, user_id: str) -> str:
        return self._call("POST", f"{self.api}/apps/{APP_NAME}/users/{user_id}/sessions", {})["id"]

    def get_session(self, user_id: str, session_id: str) -> dict:
        return self._call("GET", f"{self.api}/apps/{APP_NAME}/users/{user_id}/sessions/{session_id}")

    def run(self, user_id: str, session_id: str, text: str, mcp_token: str) -> list[dict]:
        return self._call(
            "POST",
            f"{self.api}/run",
            {
                "app_name": APP_NAME,
                "user_id": user_id,
                "session_id": session_id,
                "new_message": {"role": "user", "parts": [{"text": text}]},
                "state_delta": {TOKEN_STATE_KEY: mcp_token},
            },
        )

    def memories(self, user_id: str) -> list[dict]:
        found = self._call("GET", f"{self.rest}/memories?pageSize=100").get("memories", [])
        return [m for m in found if m.get("scope", {}).get("user_id") == user_id]


def summarize(events: list[dict]) -> tuple[list[str], list[dict], str]:
    calls, responses, text = [], [], []
    for event in events:
        for part in (event.get("content") or {}).get("parts", []):
            if call := part.get("functionCall"):
                calls.append(call["name"])
            elif response := part.get("functionResponse"):
                responses.append(response)
            elif part.get("text") and not part.get("thought"):
                text.append(part["text"])
    return calls, responses, "\n".join(text)


def check(label: str, ok: bool) -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {label}")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--preference", default="concise")
    args = parser.parse_args()

    mcp_token = os.environ.get("PIXEL_ASTRO_TEST_AGENT_TOKEN", "")
    if not mcp_token:
        parser.error("Set PIXEL_ASTRO_TEST_AGENT_TOKEN to a short-lived MCP token.")
    resource = json.loads(METADATA_PATH.read_text())["remote_agent_runtime_id"]
    engine = Engine(resource, args.location)
    results = []

    print(f"Engine: {resource}\nUser:   {args.user_id}\n")

    session_a = engine.new_session(args.user_id)
    calls, _, text = summarize(
        engine.run(
            args.user_id,
            session_a,
            f"Please remember that I prefer {args.preference} answers.",
            mcp_token,
        )
    )
    print(f"[session A {session_a}] tools={calls}\n  {text[:200]}\n")
    results.append(check("preference saved via remember_response_preference",
                         "remember_response_preference" in calls))

    memories = []
    for _ in range(12):  # Memory generation is asynchronous.
        memories = engine.memories(args.user_id)
        if memories:
            break
        time.sleep(5)
    facts = [m.get("fact", "") for m in memories]
    print(f"[memory bank] {facts}\n")
    results.append(check("preference memory stored for this user", bool(facts)))
    results.append(check("memory holds no MCP token",
                         not any(mcp_token in f for f in facts)))

    session_b = engine.new_session(args.user_id)
    calls, responses, text = summarize(
        engine.run(args.user_id, session_b, "What does my chart say about my career?", mcp_token)
    )
    mcp_errors = [
        r["name"] for r in responses
        if r.get("response", {}).get("isError") or "error" in r.get("response", {})
    ]
    print(f"[session B {session_b}] tools={calls}\n  {text[:600]}\n")
    results.append(check("new session recalls memory via load_memory", "load_memory" in calls))
    results.append(check("chart data read through MCP tools",
                         any(c in calls for c in ("list_my_kundalis", "get_chart_houses"))
                         and not mcp_errors))
    results.append(check("agent produced an answer", bool(text.strip())))

    resumed = engine.get_session(args.user_id, session_b)
    results.append(check("session B resumed from managed Sessions",
                         len(resumed.get("events", [])) > 0))

    print(f"\n{sum(results)}/{len(results)} checks passed")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
