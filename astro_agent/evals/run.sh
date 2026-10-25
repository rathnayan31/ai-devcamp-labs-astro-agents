#!/usr/bin/env bash
# Run an eval set against the local agent and gate on the result.
#
#   ./evals/run.sh [eval_set.json[:case,case]]     (default: evals/golden.evalset.json)
#
# Needs the Pixel Astro Node API on localhost:3000 (AGENT_MCP_ENABLED=true):
# chart tools call its MCP endpoint. A fresh 1h MCP token for the test user
# is minted per run with the server's own scripts/mintAgentMcpToken.js
# (PIXEL_ASTRO_SERVER_DIR; nothing in the server is changed) and passed to the
# agent through the environment, so no token is ever written to a file.
# EVAL_TOOL_TOKEN (CI) skips minting.
#
# Runs against the lab project with the deployed agent's settings (Gemini 3.8
# Flash on global, Model Armor and DLP on); every one can be overridden from
# the environment, e.g. ROOT_MODEL / SPECIALIST_MODEL for Step 4.
#
# The exit code is evals/gate.sh's verdict on the log, never adk eval's.
# The full log is kept in evals/.runs/ for reading failures.
set -uo pipefail

cd "$(dirname "$0")/.."
SET_ARG="${1:-evals/golden.evalset.json}"
SET_FILE="${SET_ARG%%:*}"
USER_ID="${EVAL_USER_ID:-6ad50ba9489d31a61484e9a1}"
SERVER_DIR="${PIXEL_ASTRO_SERVER_DIR:-$HOME/Pixel_Astro/pixel_astro_server}"

export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT_EVAL:-ai-devcamp-lab}"
export PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION_EVAL:-global}"
export ROOT_MODEL="${ROOT_MODEL:-gemini-3.8-flash}"
export SPECIALIST_MODEL="${SPECIALIST_MODEL:-gemini-3.8-flash}"
export MODEL_ARMOR_TEMPLATE_ID="${MODEL_ARMOR_TEMPLATE_ID:-pixel-astro-guardrails}"
export PII_REDACTION="${PII_REDACTION:-on}"
export PIXEL_ASTRO_MCP_URL="${PIXEL_ASTRO_MCP_URL:-http://localhost:3000/api/v1/agent-mcp}"

mkdir -p evals/.runs
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="evals/.runs/$(basename "$SET_FILE" .json)-$STAMP.log"

TOKEN="${EVAL_TOOL_TOKEN:-}"
[[ -n "$TOKEN" ]] || TOKEN="$(cd "$SERVER_DIR" && AGENT_MCP_TOKEN_TTL=1h node scripts/mintAgentMcpToken.js "$USER_ID" 2>/dev/null)" \
  || { echo "GATE: FAIL (could not mint an MCP token from $SERVER_DIR)"; exit 1; }
export PIXEL_ASTRO_AGENT_MCP_TOKEN="$TOKEN"

echo "Running $SET_ARG (log: $LOG)"
echo "Project: $GOOGLE_CLOUD_PROJECT  models: root=$ROOT_MODEL specialists=$SPECIALIST_MODEL" \
  "@$GOOGLE_CLOUD_LOCATION  model armor: $MODEL_ARMOR_TEMPLATE_ID  pii: $PII_REDACTION"
USAGE="${LOG%.log}.usage.jsonl"
START=$SECONDS
PIXEL_ASTRO_USAGE_LOG="$PWD/$USAGE" uv run adk eval pixel_astro_agent "$SET_ARG" \
  --config_file_path evals/eval_config.json --print_detailed_results >"$LOG" 2>&1
ADK_EXIT=$?
ELAPSED=$((SECONDS - START))

sed -n '/^Eval Run Summary/,/failed:/p' "$LOG"
grep -E "^(Eval Id|Overall Eval Status):" "$LOG" | paste - - | sed 's/\t/  /'
echo "Elapsed: ${ELAPSED}s (adk eval exit code: $ADK_EXIT, not used by the gate)"
CASE_COUNT="$(grep -cE '^Eval Id:' "$LOG")"
[[ -s "$USAGE" ]] && uv run python evals/cost.py "$USAGE" --cases "$CASE_COUNT"

./evals/gate.sh "$LOG"
