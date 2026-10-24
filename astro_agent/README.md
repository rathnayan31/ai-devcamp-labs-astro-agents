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
  copy of session state (including the active kundali and the server-issued
  short-lived MCP token), not the chat history. The server refreshes this
  token through `state_delta` each turn; the raw app JWT never reaches ADK.
  Chart interpretation and compatibility are LLM-driven transfers that can
  only hand back to the root.
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
   cp pixel_astro_agent/.env.example pixel_astro_agent/.env   # set project; server proxy supplies MCP auth
   gcloud auth application-default login
   uv sync
   ```
3. Launch the ADK dev UI and Scale-aware FastAPI server:
   ```bash
   uv run uvicorn pixel_astro_agent.fast_api_app:app --host 127.0.0.1 --port 8000
   ```
   Pick `pixel_astro_agent`. Use the Trace tab to watch routing, `load_skill`
   calls and MCP tool calls. Use port 8000 because the API already uses 3000.
   The integrated app flow is the existing server's
   `POST /api/v1/astro-agent/chat/stream`; direct local ADK tool calls need a
   short-lived `PIXEL_ASTRO_AGENT_MCP_TOKEN` in the local environment, never a
   user's app JWT.

Sample prompts:
- "When is a good time for my marriage?" → dasha_timing_agent
- "What does my chart say about my career?" → chart_interpretation_agent
- "Match my kundali with Priya's" → compatibility_agent
- "I have Mangal dosha, what can I do?" → remedy_agent
- "Please deduct ₹500 from my wallet" → refused (no wallet access)

## Tests

```bash
uv run pytest \
  tests/unit tests/test_safety.py tests/test_memory.py \
  tests/test_mcp_auth.py tests/test_runtime_services.py
# End-to-end Runner → MCP over HTTP (scripted model, no Gemini calls):
PIXEL_ASTRO_MCP_URL=http://localhost:3000/api/v1/agent-mcp \
PIXEL_ASTRO_TEST_AGENT_TOKEN=<short-lived-mcp-token> PIXEL_ASTRO_TEST_KUNDALI_ID=<id> uv run pytest tests/test_mcp_integration.py
```

From the repo root, the Node MCP server tests are `npx jest mcp/`.

## Next phases

- **Scale (Lab 2):** deployed to Agent Runtime in `us-central1` with Agent
  Identity, managed Sessions, and Memory Bank restricted to explicitly saved
  response-style preferences. The lab consumes the existing server's
  short-lived, read-only MCP token from ADK `state_delta`; the server alone
  handles the app JWT and remains the browser-facing proxy. No Pixel Astro
  server files are changed by this lab.
- **Govern (Lab 3):**
  - Model Armor templates on Gemini calls.
  - Cloud DLP redaction at the boundary.
  - Agent Gateway with an authz extension.
  - A governance policy such as "never give medical guarantees".
  - Evaluate Auth Manager for user authorization without weakening the existing
    per-user MCP ownership checks.

### Intended server integration contract

The browser should use the authenticated server route
`POST /api/v1/astro-agent/chat/stream`, not Agent Runtime directly. The server
authenticates the app JWT, creates or resumes the managed session, mints an
audience-bound short-lived read-only Agent MCP token, and places it in ADK
`state_delta` under `user:pixel_astro_token` for each turn. The lab agent
forwards that token only to `/api/v1/agent-mcp`; the raw app JWT and Google
credentials never reach the agent or browser. The server should stream its
existing SSE response format back to the app.

Agent Runtime A2A inference is verified with Gemini 3.8 Flash at the global
Vertex endpoint; `us-central1` returns 404 for that model, so use
`GOOGLE_CLOUD_LOCATION=global`. Gemini 2.5 publisher models still return 404 in
`ai-devcamp-lab`, and a Cloud Support case could not be opened because the
project is not eligible for that support channel. The browser-to-server-to-agent
path is not verified end to end because the Runtime has no
`PIXEL_ASTRO_MCP_URL`. Do not modify the server checkout as part of this lab.
