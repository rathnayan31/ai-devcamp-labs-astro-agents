"""BigQuery Agent Analytics (Lab 4 Step 5): one row per agent event.

    BQ_ANALYTICS_DATASET   dataset for the agent_events table, e.g. agent_analytics
                           (unset: no plugin, nothing logged)
    BQ_ANALYTICS_LOCATION  dataset location (default: US)

The dataset must exist (``bq mk``); the plugin creates the table and its views
(v_llm_response and others). Plugins attach to the App (agent.py), so every
runner must be built from the App, not root_agent: a runner built from the
agent alone loads no plugin and logs nothing, with no error.

What's logged: who, when, which agent, model, tool, latency and token counts.
What isn't: any text. By default the plugin logs prompts, replies, tool
arguments and results, and session state, and would keep the user's birth
details and ``user:pixel_astro_token`` (an MCP token). So every event's
content keeps only KEPT_FIELDS, session metadata is off, and STATE_DELTA
events (which carry the token) aren't logged at all.
"""

from __future__ import annotations

import os
from typing import Any

from google.adk.plugins.base_plugin import BasePlugin

from .gcp import project_id

TABLE = "agent_events"
# Content fields worth keeping: token counts (the views read content.usage),
# which tool, and where it came from.
KEPT_FIELDS = frozenset({"usage", "tool", "tool_origin"})
NOT_LOGGED = "not logged"


def content_without_text(content: Any, event_type: str) -> Any:
    """content_formatter: keep KEPT_FIELDS, mark everything else as not logged."""
    if isinstance(content, dict):
        return {k: (v if k in KEPT_FIELDS else NOT_LOGGED) for k, v in content.items()}
    return None if content is None else NOT_LOGGED


def analytics_plugins() -> list[BasePlugin]:
    dataset = os.environ.get("BQ_ANALYTICS_DATASET", "").strip()
    if not dataset:
        return []
    from google.adk.plugins.bigquery_agent_analytics_plugin import (
        BigQueryAgentAnalyticsPlugin,
        BigQueryLoggerConfig,
    )

    return [
        BigQueryAgentAnalyticsPlugin(
            project_id=project_id(),
            dataset_id=dataset,
            location=os.environ.get("BQ_ANALYTICS_LOCATION", "US"),
            config=BigQueryLoggerConfig(
                table_id=TABLE,
                content_formatter=content_without_text,
                log_session_metadata=False,
                event_denylist=["STATE_DELTA"],
                log_multi_modal_content=False,
            ),
        )
    ]
