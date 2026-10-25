"""Cost and latency from BigQuery Agent Analytics (Lab 4 Step 5).

    uv run python evals/analytics.py [--days 1] [--dataset agent_analytics]

Q1  cost by agent: model calls, tokens and USD per agent.
Q2  cost per agent run: Q1 divided by how many times each agent ran.
    Grouped by agent, not session: a specialist called as an AgentTool runs
    in its own session and trace, so a per-session sum leaves it out.
Q3  slowest agent runs, model calls and tool calls, longest first.
Q4  (own query) average prompt tokens per model call, by agent: what each
    agent's instruction + history costs on every call.

Prices come from evals/cost.py (check them before quoting the dollars).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from google.cloud import bigquery  # noqa: E402

from cost import cost  # noqa: E402

# Billed output includes thinking; v_llm_response's completion count doesn't.
Q1 = """
SELECT agent, model_version AS model, COUNT(*) AS calls,
  SUM(usage_prompt_tokens) AS prompt, SUM(IFNULL(usage_cached_tokens, 0)) AS cached,
  SUM(usage_completion_tokens) AS output, SUM(IFNULL(usage_thinking_tokens, 0)) AS thinking
FROM `{ds}.v_llm_response`
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
GROUP BY agent, model ORDER BY agent
"""

RUNS = """
SELECT agent, COUNT(*) AS runs
FROM `{ds}.agent_events`
WHERE event_type = 'AGENT_COMPLETED'
  AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
GROUP BY agent
"""

Q3 = """
SELECT event_type, agent, JSON_VALUE(attributes, '$.model_version') AS model,
  CAST(JSON_VALUE(latency_ms, '$.total_ms') AS INT64) AS ms
FROM `{ds}.agent_events`
WHERE event_type IN ('AGENT_COMPLETED', 'LLM_RESPONSE', 'TOOL_COMPLETED')
  AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
ORDER BY ms DESC NULLS LAST LIMIT 10
"""

Q4 = """
SELECT agent, COUNT(*) AS calls, ROUND(AVG(usage_prompt_tokens)) AS avg_prompt,
  ROUND(AVG(IFNULL(usage_thinking_tokens, 0))) AS avg_thinking,
  ROUND(AVG(usage_completion_tokens)) AS avg_output
FROM `{ds}.v_llm_response`
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
GROUP BY agent ORDER BY avg_prompt DESC
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--dataset", default=os.environ.get("BQ_ANALYTICS_DATASET", "agent_analytics"))
    args = parser.parse_args()
    project = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT_EVAL", "ai-devcamp-lab")
    client = bigquery.Client(project=project)
    ds = f"{project}.{args.dataset}"
    params = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("days", "INT64", args.days)])

    def run(sql):
        return list(client.query(sql.format(ds=ds), job_config=params).result())

    def usd(r) -> float:
        return cost(r.model or "", r.prompt or 0, r.cached, r.output or 0, r.thinking)

    q1 = run(Q1)
    runs = {r.agent: r.runs for r in run(RUNS)}
    total = sum(usd(r) for r in q1) or float("nan")
    print(f"Q1 cost by agent (last {args.days} day(s))")
    print(f"{'agent':28s} {'model':18s} {'calls':>5s} {'prompt':>8s} {'output':>7s} "
          f"{'thinking':>8s} {'USD':>8s} {'share':>6s}")
    for r in q1:
        c = usd(r)
        print(f"{r.agent:28s} {r.model or '?':18s} {r.calls:5d} {r.prompt or 0:8d} {r.output or 0:7d} "
              f"{r.thinking:8d} {c:8.5f} {100 * c / total:5.0f}%")
    print(f"TOTAL ${total:.5f}")

    print("\nQ2 cost per agent run")
    print(f"{'agent':28s} {'runs':>5s} {'calls/run':>9s} {'USD/run':>9s}")
    for r in q1:
        n = runs.get(r.agent, 0)
        if n:
            print(f"{r.agent:28s} {n:5d} {r.calls / n:9.1f} {usd(r) / n:9.5f}")

    print("\nQ3 slowest agent runs, model calls and tool calls")
    for r in run(Q3):
        print(f"{r.ms or 0:7d} ms  {r.event_type:16s} {r.agent:28s} {r.model or ''}")

    print("\nQ4 average tokens per model call, by agent")
    print(f"{'agent':28s} {'calls':>5s} {'prompt':>7s} {'thinking':>8s} {'output':>7s}")
    for r in run(Q4):
        print(f"{r.agent:28s} {r.calls:5d} {r.avg_prompt or 0:7.0f} {r.avg_thinking or 0:8.0f} {r.avg_output or 0:7.0f}")


if __name__ == "__main__":
    main()
