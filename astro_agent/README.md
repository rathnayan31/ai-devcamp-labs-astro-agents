# Pixel Astro Agent (Google ADK)

A multi-agent Vedic astrologer built with the Agent Development Kit. The work
follows the AI DevCamp labs in three phases: **Build** (this phase), **Scale**
(Agent Runtime, Sessions, Memory Bank) and **Govern** (Model Armor, Agent
Gateway, policies).

## Architecture (Phase 1)

```
pixel_astro_root  (orchestrator + safety policy; tools: list_my_kundalis, select_kundali)
 ├─ [AgentTool] dasha_timing_agent          skill dasha-timing          → get_dasha_periods, get_transits, get_chart_houses   (output_key: dasha_findings)
 ├─ [AgentTool] remedy_agent                skill remedy-kb-search      → search_kb, get_yogas                                (output_key: remedy_findings, reads dasha_findings)
 ├─ [sub-agent] chart_interpretation_agent  skill chart-interpretation  → get_chart_houses, get_yogas
 └─ [sub-agent] compatibility_agent         skill kundali-compatibility → match_kundali, list_my_kundalis
                  │  MCP (Streamable HTTP, user's JWT forwarded)
                  ▼
Node API  POST /api/v1/agent-mcp   (mcp/astroMcpServer.js, read-only)
   └─ wraps KundaliEnhanced data, calculateKundaliMatch, knowledge_base_chunks.json
```

- **Routing:** timing and remedies are tool calls (`AgentTool`). The root
  keeps control, can chain dasha → remedy in one turn, and merges the answers.
  Their results go to session state through `output_key`, and `remedy_agent`
  reads `dasha_findings`. An AgentTool call sees only its `request` text plus a
  copy of session state (JWT, active kundali), not the chat history. Chart
  interpretation and compatibility are LLM-driven transfers that can only hand
  back to the root.
- **Tool registry:** the Node server exposes seven read-only MCP tools. Each
  agent's `McpToolset` uses `tool_filter` to keep only the tools it needs.
  Every kundali lookup is ownership-checked against the JWT user.
- **Skills:** `skills/*/SKILL.md` folders, loaded on demand through
  `SkillToolset`. `run_skill_script` is filtered out.
- **Safety rail:** two layers. `SAFETY_POLICY` is appended to every
  instruction: never invent numbers, say when data is missing, no
  wallet/booking access. The `enforce_tool_allowlist` `before_tool_callback`
  blocks any tool outside the read-only allowlist.

## Run locally

1. Start the API with the MCP endpoint enabled:
   ```bash
   AGENT_MCP_ENABLED=true npm run dev        # from the repo root
   ```
2. Configure the agent:
   ```bash
   cd astro_agent
   cp pixel_astro_agent/.env.example pixel_astro_agent/.env   # set project + PIXEL_ASTRO_USER_TOKEN
   gcloud auth application-default login
   uv sync
   ```
3. Launch the dev UI and open http://localhost:8000:
   ```bash
   uv run adk web --port 8000 .
   ```
   Pick `pixel_astro_agent`. Use the Trace tab to watch routing, `load_skill`
   calls and MCP tool calls. Use port 8000 because the API already uses 3000.

Sample prompts:
- "When is a good time for my marriage?" → dasha_timing_agent
- "What does my chart say about my career?" → chart_interpretation_agent
- "Match my kundali with Priya's" → compatibility_agent
- "I have Mangal dosha, what can I do?" → remedy_agent
- "Please deduct ₹500 from my wallet" → refused (no wallet access)

## Tests

```bash
uv run pytest                       # offline: safety rail + wiring
# End-to-end Runner → MCP over HTTP (scripted model, no Gemini calls):
PIXEL_ASTRO_MCP_URL=http://localhost:3000/api/v1/agent-mcp \
PIXEL_ASTRO_TEST_TOKEN=<jwt> PIXEL_ASTRO_TEST_KUNDALI_ID=<id> uv run pytest tests/test_mcp_integration.py
```

From the repo root, the Node MCP server tests are `npx jest mcp/`.

## Next phases

- **Scale (Lab 2):**
  - Deploy with `agents-cli deploy` to Agent Runtime with `--agent-identity`.
  - Add `VertexAiSessionService` and Memory Bank (`load_memory`).
  - The Node API (Cloud Run) calls the engine, passing the user's JWT into
    session state (`user:pixel_astro_token`).
- **Govern (Lab 3):**
  - Model Armor templates on Gemini calls.
  - Cloud DLP redaction at the boundary.
  - Agent Gateway with an authz extension.
  - A governance policy such as "never give medical guarantees".
  - Replace the forwarded JWT with Agent Identity and Auth Manager.
