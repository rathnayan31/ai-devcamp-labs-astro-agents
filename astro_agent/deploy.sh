#!/usr/bin/env bash
# Eval-gated deploy to Agent Runtime (Lab 4 Step 6): the golden set must pass
# before agents-cli deploys anything.
#
#   [ROOT_MODEL=...] [SPECIALIST_MODEL=...] ./deploy.sh [extra agents-cli deploy flags]
#
# Same gate as cloudbuild.yaml (evals/gate.sh): a failing, unscored or crashed
# eval exits non-zero and nothing is deployed. Needs what run.sh needs (the
# Node API on localhost:3000 and its checkout for the token). EVAL_SET picks
# another set.
#
# What ships is what was tested: the deploy sets the same models, location,
# Model Armor and DLP settings run.sh evaluated, plus the Lab 3 gateway
# binding, every time (an omitted setting isn't relied on to carry over).
set -uo pipefail
cd "$(dirname "$0")"

export ROOT_MODEL="${ROOT_MODEL:-gemini-3.8-flash}"
export SPECIALIST_MODEL="${SPECIALIST_MODEL:-gemini-3.8-flash}"
PROJECT=ai-devcamp-lab
GATEWAY="projects/${PROJECT}/locations/us-central1/agentGateways/agw-pixel-astro"
ENV_VARS="GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_LOCATION=global,PROJECT_ID=${PROJECT}"
ENV_VARS+=",ROOT_MODEL=${ROOT_MODEL},SPECIALIST_MODEL=${SPECIALIST_MODEL}"
ENV_VARS+=",MODEL_ARMOR_TEMPLATE_ID=${MODEL_ARMOR_TEMPLATE_ID:-pixel-astro-guardrails},MODEL_ARMOR_REGION=us-central1"
ENV_VARS+=",PII_REDACTION=${PII_REDACTION:-on}"
ENV_VARS+=",PIXEL_ASTRO_MCP_URL=${DEPLOY_MCP_URL:-http://localhost:3000/api/v1/agent-mcp}"
ENV_VARS+=",OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental"

if ! ./evals/run.sh "${EVAL_SET:-evals/golden.evalset.json}"; then
  echo "DEPLOY: blocked by the eval gate. Nothing was deployed."
  exit 1
fi
echo "DEPLOY: eval gate passed; deploying root=${ROOT_MODEL} specialists=${SPECIALIST_MODEL}."
exec ${AGENTS_CLI:-agents-cli} deploy --project "$PROJECT" --region us-central1 \
  --service-name pixel-astro-agent --agent-identity --update-only --no-confirm-project \
  --agent-gateway-ingress "$GATEWAY" --update-env-vars "$ENV_VARS" "$@"
