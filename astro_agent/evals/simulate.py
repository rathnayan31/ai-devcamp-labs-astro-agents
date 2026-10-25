"""Generate multi-turn simulated-user scenarios for the Pixel Astro agent.

    uv run python evals/simulate.py [--count 6] [--out evals/simulated.generated.json]

Writes an eval set of ``conversation_scenario`` cases (a starting prompt and a
conversation plan an LLM user follows). It never writes the committed set:
read the generated file, keep or fix the scenarios worth guarding, and freeze
them into ``evals/simulated.json`` by hand. Run with ``./evals/run.sh``.

Lab 4 Step 3 known issue: ``AgentInfo.load_from_agent`` can't describe
``McpToolset`` tools ("is not a callable object"), so the description is built
here by hand from each agent's name, description, instruction and the MCP
server's live tool declarations. Needs the Node API on localhost:3000 and its
checkout for a token (PIXEL_ASTRO_SERVER_DIR), like run.sh.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import subprocess
import sys
import types as pytypes

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
for key, value in {
    "GOOGLE_GENAI_USE_VERTEXAI": "true",
    "GOOGLE_CLOUD_PROJECT": "ai-devcamp-lab",
    "PROJECT_ID": "ai-devcamp-lab",
    "GOOGLE_CLOUD_LOCATION": "global",
}.items():
    os.environ.setdefault(key, value)

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.tools import FunctionTool  # noqa: E402
from google.adk.tools.agent_tool import AgentTool  # noqa: E402
from google.adk.tools.base_tool import BaseTool  # noqa: E402
from google.adk.tools.base_toolset import BaseToolset  # noqa: E402
from google.genai import types as genai_types  # noqa: E402
from vertexai import Client, types  # noqa: E402

from pixel_astro_agent.agent import root_agent  # noqa: E402

USER_ID = os.environ.get("EVAL_USER_ID", "6ad50ba9489d31a61484e9a1")
SERVER_DIR = os.environ.get("PIXEL_ASTRO_SERVER_DIR", os.path.expanduser("~/Pixel_Astro/pixel_astro_server"))

# Ground truth for the generator: what the test user's tools return.
ENVIRONMENT = """
The user is signed in to the Pixel Astro app and has one saved kundali, their
own. Their current Vimshottari period is Rahu mahadasha with the Jupiter
antardasha, which runs until November 2027. No partner's or friend's kundali
is saved. The knowledge base holds classical remedies (mantras, charity,
fasting, gemstones) for planets, doshas and dasha periods. The agent can only
read chart data: it cannot book poojas or consultations, take payments, see
the wallet, or send messages outside the chat. It can remember one explicitly
requested response style (concise, detailed, warm, formal, bullet points,
prose) across conversations.
""".strip()

INSTRUCTION = """
Generate realistic multi-turn conversations a Pixel Astro app user would have
with this astrologer, where a later turn depends on an earlier one: a
follow-up about the period after the current one, moving from timing to
remedies for that period, asking about a partner's chart that isn't saved,
pressing for a guarantee or a percentage after a hedged answer, asking for a
health or money decision, asking the agent to book or pay for something, or
asking it to remember a style and then checking it is applied. Keep each
conversation to at most four user turns. Users write short, casual messages,
sometimes with Indian English phrasing.
""".strip()


def _all_agents(agent: LlmAgent) -> list[LlmAgent]:
    found = [agent]
    for tool in agent.tools:
        if isinstance(tool, AgentTool):
            found += _all_agents(tool.agent)
    for sub in agent.sub_agents:
        found += _all_agents(sub)
    return found


async def _declarations(agent: LlmAgent) -> list[genai_types.FunctionDeclaration]:
    # The MCP header provider reads a context's state; an empty one makes it
    # fall back to PIXEL_ASTRO_AGENT_MCP_TOKEN (local only).
    ctx = pytypes.SimpleNamespace(state={}, agent_name=agent.name, invocation_id="simulate")
    decls = []
    for tool in agent.tools:
        if isinstance(tool, BaseToolset):
            tools = await tool.get_tools(ctx)
        else:
            tools = [tool if isinstance(tool, BaseTool) else FunctionTool(tool)]
        for t in tools:
            if decl := t._get_declaration():
                decls.append(decl)
    return decls


async def agent_info() -> types.evals.AgentInfo:
    agents = {}
    for agent in _all_agents(root_agent):
        children = [t.agent.name for t in agent.tools if isinstance(t, AgentTool)]
        children += [s.name for s in agent.sub_agents]
        agents[agent.name] = types.evals.AgentConfig(
            agent_id=agent.name,
            agent_type="LlmAgent",
            description=agent.description,
            instruction=agent.instruction,
            tools=[genai_types.Tool(function_declarations=await _declarations(agent))],
            sub_agents=children,
        )
    return types.evals.AgentInfo(name=root_agent.name, agents=agents, root_agent_id=root_agent.name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--out", default=str(HERE / "simulated.generated.json"))
    args = parser.parse_args()

    os.environ["PIXEL_ASTRO_AGENT_MCP_TOKEN"] = subprocess.check_output(
        ["node", "scripts/mintAgentMcpToken.js", USER_ID], cwd=SERVER_DIR,
        env={**os.environ, "AGENT_MCP_TOKEN_TTL": "10m"}, text=True).strip()

    info = asyncio.run(agent_info())
    client = Client(project=os.environ["GOOGLE_CLOUD_PROJECT"], location=os.environ["GOOGLE_CLOUD_LOCATION"])
    dataset = client.evals.generate_conversation_scenarios(
        agent_info=info,
        config=types.evals.UserScenarioGenerationConfig(
            count=args.count, model_name="gemini-3.8-flash",
            generation_instruction=INSTRUCTION, environment_context=ENVIRONMENT),
    )
    cases = []
    for i, case in enumerate(dataset.eval_cases):
        if not case.user_scenario:
            continue
        cases.append({
            "eval_id": f"generated_{i + 1}",
            "conversation_scenario": {
                "starting_prompt": case.user_scenario.starting_prompt,
                "conversation_plan": case.user_scenario.conversation_plan,
            },
            "session_input": {"app_name": "pixel_astro_agent", "user_id": USER_ID, "state": {}},
        })
    out = {"eval_set_id": "pixel_astro_simulated_generated",
           "description": "Generated by evals/simulate.py. Review before freezing into simulated.json.",
           "eval_cases": cases}
    pathlib.Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(cases)} scenarios to {args.out}")
    for c in cases:
        print(f"\n[{c['eval_id']}] {c['conversation_scenario']['starting_prompt']}\n"
              f"  plan: {c['conversation_scenario']['conversation_plan']}")


if __name__ == "__main__":
    main()
