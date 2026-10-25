# ai-devcamp-labs-astro-agents

Pixel Astro's multi-agent Vedic astrology assistant, built with Google's
Agent Development Kit (ADK) by following the
[AI DevCamp labs](https://sonikajanagill.com/ai-devcamp-labs/lab-1-build.html)
(Build → Scale → Govern → Optimise). All four labs are complete.

```
User
  │
  ▼
pixel_astro_root  (ADK orchestrator: collects inputs, routes, merges, refuses wallet/booking)
  ├─ [AgentTool] dasha_timing_agent          → state: dasha_findings
  ├─ [AgentTool] remedy_agent                → state: remedy_findings (reads dasha_findings)
  ├─ [sub-agent] chart_interpretation_agent
  └─ [sub-agent] compatibility_agent
                  │  MCP (Streamable HTTP, short-lived server-issued token, read-only tools)
                  ▼
Pixel Astro Node API  POST /api/v1/agent-mcp   (mcp/astroMcpServer.js)
```

## Layout

| Path | What it is |
|---|---|
| `astro_agent/` | The ADK agents, Agent Skills (`skills/*/SKILL.md`), safety rail and tests. See `astro_agent/README.md` to run it. |
| `mcp/` | The read-only MCP tool registry the agents call. **Reference copy:** it is mounted inside the Pixel Astro Node API and imports that app's models and services, so it doesn't run on its own. |

## Quick start

```bash
cd astro_agent
cp pixel_astro_agent/.env.example pixel_astro_agent/.env   # set project; app-server supplies MCP auth
uv sync
uv run pytest \
  tests/unit tests/test_safety.py tests/test_memory.py \
  tests/test_mcp_auth.py tests/test_runtime_services.py \
  tests/test_model_config.py tests/test_guardrails.py tests/test_analytics.py
./evals/run.sh          # golden eval set + gate (needs the Node API on :3000)
uv run uvicorn pixel_astro_agent.fast_api_app:app --host 127.0.0.1 --port 8000
```

## Labs

- ✅ **Build (Lab 1):** multi-agent ADK astrologer. The root orchestrator
  calls `dasha_timing_agent` and `remedy_agent` as `AgentTool`s (results
  shared through `output_key` state) and transfers to the chart-interpretation
  and compatibility sub-agents. Four Agent Skills (`skills/*/SKILL.md`),
  seven read-only MCP tools with per-agent `tool_filter`, and a safety rail
  (`SAFETY_POLICY` + tool allowlist callback; no wallet/booking access).
  Lab 1 assignment, adapted to Pixel Astro on purpose:

  | Assignment item | Here |
  |---|---|
  | Agent + hand-written function tool | `select_kundali` (and `remember_response_preference`, Lab 2) |
  | Own Agent Skill via `SkillToolset` | four skills: chart-interpretation, dasha-timing, kundali-compatibility, remedy-kb-search |
  | Built-in tool (`google_search`) in a sub-agent behind `AgentTool` | **replaced**: `remedy_agent` (an `AgentTool` specialist) grounds on the curated Vedic knowledge base through the read-only MCP tool `search_kb`, not the open web, so answers cite vetted sources only |
  | MCP side effect gated by `require_confirmation=True` | **not applicable**: the agent is read-only by design (no payments, bookings or writes; the Lab 3 `no-wallet-or-booking` policy). With no side-effect tool there is nothing to confirm; the read-only allowlist callback is the gate |

- ✅ **Scale (Lab 2):** deployed to Agent Runtime (`us-central1`) with Agent
  Identity, managed Sessions and preference-only Memory Bank (90-day TTL).
  Verified end to end by `astro_agent/verify_scale.py` (7/7).
- ✅ **Govern (Lab 3):** Model Armor on every Gemini call, Cloud DLP at the
  boundary, Agent Registry, the `no-wallet-or-booking` governance policy bound
  to the agent identity, and Agent Gateway ingress. Evidence and red-team
  scoresheet: `astro_agent/README.md`, `astro_agent/docs/`.
- ✅ **Optimise (Lab 4):** golden eval set (6 rule-per-case rubrics) behind a
  fail-closed gate, 4 frozen simulated-user scenarios, model right-sizing
  (root on Gemini 3.8 Flash, specialists on 3.5 Flash-Lite: ~54% cheaper, no
  regressions), BigQuery Agent Analytics with no message text, and an
  eval-gated deploy. Results: `astro_agent/docs/optimise-log.md`.
