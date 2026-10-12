"""Offline checks of the safety rail and agent wiring (no model, no network)."""

from types import SimpleNamespace

import pytest
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.skill_toolset import SkillToolset

from pixel_astro_agent.agent import root_agent
from pixel_astro_agent.safety import ALLOWED_TOOLS, enforce_tool_allowlist
from pixel_astro_agent.toolsets import MCP_READ_ONLY_TOOLS, astro_mcp_tools

ALL_AGENTS = [
    root_agent,
    *root_agent.sub_agents,
    *(t.agent for t in root_agent.tools if isinstance(t, AgentTool)),
]


def _ctx():
    return SimpleNamespace(agent_name="test_agent")


@pytest.mark.parametrize("tool_name", ["debit_wallet", "book_consultation", "create_order", "run_skill_script"])
def test_allowlist_blocks_side_effect_tools(tool_name):
    result = enforce_tool_allowlist(SimpleNamespace(name=tool_name), {}, _ctx())
    assert result and "not permitted" in result["error"]


@pytest.mark.parametrize("tool_name", sorted(ALLOWED_TOOLS))
def test_allowlist_passes_read_only_tools(tool_name):
    assert enforce_tool_allowlist(SimpleNamespace(name=tool_name), {}, _ctx()) is None


def test_every_agent_has_the_allowlist_callback():
    for agent in ALL_AGENTS:
        assert agent.before_tool_callback is enforce_tool_allowlist, agent.name


def test_toolsets_only_reach_allowlisted_tools():
    for agent in ALL_AGENTS:
        for tool in agent.tools:
            if isinstance(tool, McpToolset):
                assert set(tool.tool_filter) <= MCP_READ_ONLY_TOOLS, agent.name
            elif isinstance(tool, SkillToolset):
                assert "run_skill_script" not in tool.tool_filter, agent.name
                assert set(tool.tool_filter) <= ALLOWED_TOOLS, agent.name


def test_unknown_mcp_tool_is_rejected_at_build_time():
    with pytest.raises(ValueError):
        astro_mcp_tools("get_wallet_balance")


def test_specialists_route_back_through_root_only():
    assert {a.name for a in root_agent.sub_agents} == {"chart_interpretation_agent", "compatibility_agent"}
    for agent in root_agent.sub_agents:
        assert agent.disallow_transfer_to_peers is True


def test_dasha_and_remedy_are_agent_tools_writing_to_state():
    agent_tools = {t.agent.name: t.agent for t in root_agent.tools if isinstance(t, AgentTool)}
    assert set(agent_tools) == {"dasha_timing_agent", "remedy_agent"}
    assert agent_tools["dasha_timing_agent"].output_key == "dasha_findings"
    assert agent_tools["remedy_agent"].output_key == "remedy_findings"
    assert "{dasha_findings?}" in agent_tools["remedy_agent"].instruction
    for name, agent in agent_tools.items():
        assert agent.disallow_transfer_to_parent and agent.disallow_transfer_to_peers, name
        assert name in ALLOWED_TOOLS, name
