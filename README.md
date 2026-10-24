# ai-devcamp-labs-astro-agents

Pixel Astro's multi-agent Vedic astrology assistant, built with Google's
Agent Development Kit (ADK) by following the
[AI DevCamp labs](https://sonikajanagill.com/ai-devcamp-labs/lab-1-build.html)
(Build → Scale → Govern → Optimise). The existing agent completed **Build**;
this repository is being extended for **Scale**.

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
  tests/test_mcp_auth.py tests/test_runtime_services.py
uv run uvicorn pixel_astro_agent.fast_api_app:app --host 127.0.0.1 --port 8000
```

## Roadmap

- **Scale (Lab 2):** Agent Runtime, Agent Identity, managed Sessions and
  preference-only Memory Bank.
- **Govern (Lab 3):** Agent Gateway, Model Armor, Auth Manager, and the
  read-only / no-wallet policy enforced at the gateway.
- **Optimise (Lab 4):** evals with `agents-cli eval`.
