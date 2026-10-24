"""Toolsets shared by the Pixel Astro agents.

* MCP: the read-only tool registry served by the Node API at
  ``/api/v1/agent-mcp`` (see ``mcp/astroMcpServer.js``). Each agent gets its
  own ``McpToolset`` narrowed with ``tool_filter`` to only the tools it needs.
* Skills: ``SKILL.md`` folders under ``astro_agent/skills``, loaded on demand
  through ``SkillToolset`` (progressive disclosure).
"""

from __future__ import annotations

import os
import pathlib

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.skills import load_skill_from_dir
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.skill_toolset import SkillToolset

from .mcp_auth import get_agent_mcp_token, is_agent_runtime

SKILLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills"

MCP_URL = os.environ.get(
    "PIXEL_ASTRO_MCP_URL", "http://localhost:3000/api/v1/agent-mcp"
)

# Read-only tools the Node MCP server exposes (mcp/astroMcpServer.js).
MCP_READ_ONLY_TOOLS = frozenset(
    {
        "list_my_kundalis",
        "get_chart_houses",
        "get_dasha_periods",
        "get_transits",
        "get_yogas",
        "match_kundali",
        "search_kb",
    }
)

# Skill tools we allow. `run_skill_script` is deliberately excluded:
# skills here are instructions only, never code execution.
SKILL_TOOLS = frozenset({"list_skills", "load_skill", "load_skill_resource"})


def _auth_headers(ctx: ReadonlyContext) -> dict[str, str]:
    """Forward the app server's short-lived, MCP-scoped token."""
    token = get_agent_mcp_token(ctx.state)
    if not token and not is_agent_runtime():
        token = os.environ.get("PIXEL_ASTRO_AGENT_MCP_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def astro_mcp_tools(*tool_names: str) -> McpToolset:
    unknown = set(tool_names) - MCP_READ_ONLY_TOOLS
    if unknown:
        raise ValueError(f"Not a read-only Pixel Astro MCP tool: {sorted(unknown)}")
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=MCP_URL, timeout=30),
        tool_filter=list(tool_names),
        header_provider=_auth_headers,
    )


def skills(*skill_names: str) -> SkillToolset:
    return SkillToolset(
        skills=[load_skill_from_dir(SKILLS_DIR / name) for name in skill_names],
        tool_filter=sorted(SKILL_TOOLS),
    )
