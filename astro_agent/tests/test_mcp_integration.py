"""End-to-end ADK Runner -> McpToolset -> Node MCP endpoint, with a scripted
fake model (no Gemini calls). Checks the server-minted MCP token travels from
session state to the MCP endpoint, tools return structured facts, and the
allowlist holds.

Skipped unless PIXEL_ASTRO_MCP_URL, PIXEL_ASTRO_TEST_AGENT_TOKEN and
PIXEL_ASTRO_TEST_KUNDALI_ID are set.
"""

import json
import os
from typing import AsyncGenerator

import pytest
from google.adk.agents import Agent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types
from pixel_astro_agent.mcp_auth import AGENT_MCP_TOKEN_STATE_KEY
from pixel_astro_agent.safety import enforce_tool_allowlist
from pixel_astro_agent.toolsets import astro_mcp_tools

pytestmark = pytest.mark.skipif(
    not all(
        os.environ.get(k)
        for k in (
            "PIXEL_ASTRO_MCP_URL",
            "PIXEL_ASTRO_TEST_AGENT_TOKEN",
            "PIXEL_ASTRO_TEST_KUNDALI_ID",
        )
    ),
    reason="needs a running MCP endpoint",
)


class ScriptedLlm(BaseLlm):
    """Emits the scripted function calls in order, then a final text answer."""

    calls: list[tuple[str, dict]]
    seen_tools: list[str] = []

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.seen_tools = sorted(llm_request.tools_dict)
        turn = sum(1 for c in llm_request.contents if c.role == "model")
        if turn < len(self.calls):
            name, args = self.calls[turn]
            part = types.Part(function_call=types.FunctionCall(name=name, args=args))
        else:
            part = types.Part.from_text(text="done")
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


async def _run(llm: ScriptedLlm, *tool_names: str) -> list:
    agent = Agent(
        name="probe",
        model=llm,
        instruction="probe",
        tools=[astro_mcp_tools(*tool_names)],
        before_tool_callback=enforce_tool_allowlist,
    )
    runner = InMemoryRunner(agent=agent, app_name="probe")
    session = await runner.session_service.create_session(
        app_name="probe",
        user_id="u1",
        state={AGENT_MCP_TOKEN_STATE_KEY: os.environ["PIXEL_ASTRO_TEST_AGENT_TOKEN"]},
    )
    events = [
        e
        async for e in runner.run_async(
            user_id="u1",
            session_id=session.id,
            new_message=types.Content(
                role="user", parts=[types.Part.from_text(text="go")]
            ),
        )
    ]
    await runner.close()
    return [r for e in events for r in e.get_function_responses()]


def _payload(fn_response) -> dict:
    resp = fn_response.response
    if "content" in resp:
        return json.loads(resp["content"][0]["text"])
    return resp


async def test_tool_call_reaches_server_with_agent_mcp_token():
    kid = os.environ["PIXEL_ASTRO_TEST_KUNDALI_ID"]
    llm = ScriptedLlm(
        model="scripted",
        calls=[("get_dasha_periods", {"kundali_id": kid, "planets": ["Jupiter"]})],
    )
    responses = await _run(llm, "get_dasha_periods", "search_kb")

    assert llm.seen_tools == ["get_dasha_periods", "search_kb"]
    data = _payload(responses[0])
    assert data["mahadashas"], data
    assert "missing" in data


async def test_non_allowlisted_call_is_blocked_before_reaching_server():
    llm = ScriptedLlm(model="scripted", calls=[("debit_wallet", {"amount": 500})])
    responses = await _run(llm, "search_kb")
    assert "not permitted" in json.dumps(responses[0].response)
