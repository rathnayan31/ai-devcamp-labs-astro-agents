# ai-devcamp-labs-astro-agents

Pixel Astro's multi-agent Vedic astrology assistant, built with Google's
Agent Development Kit (ADK) by following the
[AI DevCamp labs](https://sonikajanagill.com/ai-devcamp-labs/lab-1-build.html)
(Build → Scale → Govern → Optimise). This repo is the **Build** phase.

```
User
  │
  ▼
pixel_astro_root  (ADK orchestrator: collects inputs, routes, merges, refuses wallet/booking)
  ├─ [AgentTool] dasha_timing_agent          → state: dasha_findings
  ├─ [AgentTool] remedy_agent                → state: remedy_findings (reads dasha_findings)
  ├─ [sub-agent] chart_interpretation_agent
  └─ [sub-agent] compatibility_agent
                  │  MCP (Streamable HTTP, user's JWT forwarded, read-only tools)
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
cp pixel_astro_agent/.env.example pixel_astro_agent/.env   # set project + PIXEL_ASTRO_USER_TOKEN
uv sync
uv run pytest                    # offline: safety rail + wiring
uv run adk web --port 8000 .     # needs the Node API running with AGENT_MCP_ENABLED=true
```

## Roadmap

- **Scale (Lab 2):** Agent Runtime deployment, Sessions + Memory Bank.
- **Govern (Lab 3):** Agent Gateway, Model Armor, Agent Identity, Auth Manager,
  read-only / no-wallet policy enforced at the gateway.
- **Optimise (Lab 4):** evals with `agents-cli eval`.
