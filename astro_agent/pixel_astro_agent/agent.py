"""Pixel Astro multi-agent astrologer (Build and Scale).

    root_agent (orchestrator + safety policy)
      ├── [AgentTool] dasha_timing_agent    skill: dasha-timing           tools: get_dasha_periods, get_transits, get_chart_houses
      ├── [AgentTool] remedy_agent          skill: remedy-kb-search       tools: search_kb, get_yogas
      ├── [sub-agent] chart_interpretation_agent  skill: chart-interpretation   tools: get_chart_houses, get_yogas
      └── [sub-agent] compatibility_agent   skill: kundali-compatibility  tools: match_kundali, list_my_kundalis

Dasha timing and remedies are tool calls (``AgentTool``): the root keeps
control, so one turn can chain them ("when does my Saturn period start, and
what can I do about it?"). Their answers land in session state through
``output_key`` (``dasha_findings``, ``remedy_findings``), and remedy_agent reads
``dasha_findings`` to fit remedies to the running period. An AgentTool call
gets only its ``request`` text, not the chat history, but it does get a copy of
session state (including the active kundali and the app server's short-lived,
MCP-only token). The server refreshes that token in ``state_delta`` each turn;
the user's app JWT is never sent to this agent.

Chart interpretation and compatibility stay LLM-driven transfers: they're
conversational, and the user talks to them directly until they hand back.
Every agent shares the same safety policy and tool allowlist callback.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.load_memory_tool import LoadMemoryTool
from google.adk.tools.tool_context import ToolContext

from .guardrails import content_config, guard_reply
from .memory import remember_response_preference, save_explicit_preference
from .model_config import configured_model
from .safety import SAFETY_POLICY, enforce_tool_allowlist
from .toolsets import astro_mcp_tools, skills

ROOT_MODEL = os.environ.get("ROOT_MODEL", "gemini-3.8-flash")
SPECIALIST_MODEL = os.environ.get("SPECIALIST_MODEL", "gemini-3.8-flash")

ACTIVE_KUNDALI_KEY = "active_kundali_id"
DASHA_FINDINGS_KEY = "dasha_findings"
REMEDY_FINDINGS_KEY = "remedy_findings"

CHART_CONTEXT = """
The chart under discussion has kundali_id `{active_kundali_id?}` (blank means
none is selected yet). Pass it as `kundali_id` to every chart tool.
""".strip()

# Specialists reached by transfer talk to the user and can hand back.
TRANSFER_SPECIALIST_RULES = f"""
{CHART_CONTEXT} If it's blank, transfer back to `pixel_astro_root` to select one.

If the user's question is outside your specialty, transfer back to
`pixel_astro_root`.
""".strip()

# Specialists reached through AgentTool run once per request and return text
# to the orchestrator; they can't transfer and never see the chat history.
TOOL_SPECIALIST_RULES = f"""
{CHART_CONTEXT} If it's blank, reply only "No kundali selected." and stop.

You are called by the Pixel Astro orchestrator, not by the user directly. The
request you receive is the whole question; you can't see earlier messages.
Answer it completely in one reply, in the voice your skill describes, because
the orchestrator relays your answer to the user. If the request is outside your
specialty, say so in one sentence.
""".strip()


def select_kundali(
    kundali_id: str, display_name: str, tool_context: ToolContext
) -> dict:
    """Remember which of the user's kundalis the conversation is about.

    Args:
        kundali_id: The kundaliId returned by list_my_kundalis.
        display_name: The native's name, for confirmation.
    """
    tool_context.state[ACTIVE_KUNDALI_KEY] = kundali_id
    tool_context.state["active_kundali_name"] = display_name
    # Findings belong to the previous chart; don't let them leak into this one.
    tool_context.state[DASHA_FINDINGS_KEY] = ""
    tool_context.state[REMEDY_FINDINGS_KEY] = ""
    return {"selected": kundali_id, "name": display_name}


def _specialist(
    *,
    name: str,
    description: str,
    focus: str,
    skill: str,
    tools: tuple[str, ...],
    as_tool: bool,
    output_key: str | None = None,
    extra_context: str = "",
) -> Agent:
    rules = TOOL_SPECIALIST_RULES if as_tool else TRANSFER_SPECIALIST_RULES
    instruction = "\n\n".join(
        part
        for part in (
            focus,
            f"Before answering, load the `{skill}` skill and follow it.",
            rules,
            extra_context,
            SAFETY_POLICY,
        )
        if part
    )
    return Agent(
        name=name,
        model=configured_model(SPECIALIST_MODEL),
        description=description,
        instruction=instruction,
        tools=[astro_mcp_tools(*tools), skills(skill)],
        output_key=output_key,
        # Replies screened by Model Armor; input is the root's own request.
        generate_content_config=content_config(screen_input=False),
        after_model_callback=guard_reply,
        before_tool_callback=enforce_tool_allowlist,
        # Tool specialists have no parent to transfer to; transfer specialists
        # may only go back to the root.
        disallow_transfer_to_parent=as_tool,
        disallow_transfer_to_peers=True,
    )


dasha_timing_agent = _specialist(
    name="dasha_timing_agent",
    description="Answers WHEN questions: timing of marriage, children, career change, wealth, property, "
    "foreign travel, and what the current or upcoming dasha and transits bring. "
    "Pass the user's question as a self-contained request, including the life event asked about.",
    focus="You are the timing specialist of a Vedic astrology team (Parashara school).",
    skill="dasha-timing",
    tools=("get_dasha_periods", "get_transits", "get_chart_houses"),
    as_tool=True,
    output_key=DASHA_FINDINGS_KEY,
)

remedy_agent = _specialist(
    name="remedy_agent",
    description="Suggests grounded remedies (mantra, charity, fasting, lifestyle, gemstone cautions) "
    "for doshas, weak planets or a difficult dasha period, using the Pixel Astro knowledge base. "
    "Pass the user's concern as a self-contained request.",
    focus="You are the remedies specialist of a Vedic astrology team.",
    skill="remedy-kb-search",
    tools=("search_kb", "get_yogas"),
    as_tool=True,
    output_key=REMEDY_FINDINGS_KEY,
    extra_context="""
Timing findings from this conversation (may be blank): {dasha_findings?}
If they name a running or upcoming difficult period, prefer remedies for that
period's planets, and say which period the remedy is for.
""".strip(),
)

chart_interpretation_agent = _specialist(
    name="chart_interpretation_agent",
    description="Explains the natal chart: personality, ascendant, houses, planet strengths, "
    "yogas and doshas, and what a life area (career, relationships, health, wealth) looks like.",
    focus="You are the natal chart interpretation specialist of a Vedic astrology team.",
    skill="chart-interpretation",
    tools=("get_chart_houses", "get_yogas"),
    as_tool=False,
)

compatibility_agent = _specialist(
    name="compatibility_agent",
    description="Kundali matching between two people: Ashtakoota guna score, Nadi/Bhakoot/Manglik "
    "doshas and relationship compatibility.",
    focus="You are the kundali-matching (compatibility) specialist of a Vedic astrology team.",
    skill="kundali-compatibility",
    tools=("match_kundali", "list_my_kundalis"),
    as_tool=False,
)


root_agent = Agent(
    name="pixel_astro_root",
    model=configured_model(ROOT_MODEL),
    description="Pixel Astro's AI astrologer: routes each question to the right Vedic astrology specialist.",
    instruction=f"""
You are the front desk of Pixel Astro's AI astrology team. You never do chart
analysis yourself, and you never state an astrological fact (planet, house,
dasha, year, age, score, dosha, remedy) that a specialist didn't return.
Your jobs:

At the start of every user turn (small talk included), before any other tool
or reply, call `load_memory` once with the query "response style preference",
then apply what it returns only to response style. Never use memory as chart
data or authorization.
Only call `remember_response_preference` when the user explicitly asks you to
remember a response-style preference, and choose one supported style. Do not
save chart facts, birth details, kundali IDs, credentials, or other free-form
personal information.

1. Collect the required inputs before delegating. Every chart is a saved
   kundali (birth date, time and place) in the user's Pixel Astro account.
   The active kundali is `{{active_kundali_id?}}` ({{active_kundali_name?}}).
   If it's blank, call `list_my_kundalis`:
   - exactly one kundali: call `select_kundali` with it;
   - several: ask which person the question is about, then `select_kundali`;
   - none, or not the person asked about: ask for their birth date, exact
     birth time and birth place, and explain they need to save it as a
     kundali in the Pixel Astro app first. You can't create one, and you never
     analyse a chart from details typed into chat.
   If the user switches to a different person, select that kundali.
   For compatibility, also confirm the partner has a saved kundali (check
   `list_my_kundalis`); if not, ask for the partner's birth details and point
   them to the app in the same way, before transferring.
2. Route the question:
   - Timing ("when will…", current/next dasha, transits): call the
     `dasha_timing_agent` tool.
   - Remedies (upaya, mantras, gemstones, "what can I do about…"): call the
     `remedy_agent` tool.
   - Both in one question (e.g. "when does my Saturn period start and what can
     I do?"): call `dasha_timing_agent` first, then `remedy_agent`.
   - Personality, houses, planets, yogas, doshas, "what does my chart say
     about…": transfer to `chart_interpretation_agent`.
   - Matching two kundalis, guna milan, partner compatibility: transfer to
     `compatibility_agent`.
3. When you call a specialist tool, write its `request` so it stands alone:
   the specialist can't see this conversation. Include the person's name, the
   life event or concern, and any detail the user gave earlier (e.g. "already
   married in 2019").
4. Merge specialist answers into one coherent reply: if you called two, lead
   with the timing, then the remedies tied to it, without repeating
   yourself. Keep every year, age, planet and remedy exactly as the specialist
   gave it. Don't add, round or infer any. If a specialist says data is
   missing, pass that on rather than filling the gap.
5. Payments, wallet balance, recharges, refunds, orders, and booking
   consultations or poojas are out of scope. Don't route them to any
   specialist. Say you can't do that here and point the user to the Pixel
   Astro app.
6. Answer small talk and questions about what you can do briefly yourself.
   Anything else non-astrological: politely decline.

{SAFETY_POLICY}
""".strip(),
    tools=[
        astro_mcp_tools("list_my_kundalis"),
        select_kundali,
        LoadMemoryTool(),
        remember_response_preference,
        AgentTool(agent=dasha_timing_agent),
        AgentTool(agent=remedy_agent),
    ],
    sub_agents=[chart_interpretation_agent, compatibility_agent],
    # The user's message and every reply screened by Model Armor.
    generate_content_config=content_config(screen_input=True),
    after_model_callback=guard_reply,
    before_tool_callback=enforce_tool_allowlist,
    after_agent_callback=save_explicit_preference,
)

app = App(root_agent=root_agent, name="pixel_astro_agent")
