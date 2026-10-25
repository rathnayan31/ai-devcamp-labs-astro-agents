#!/usr/bin/env bash
# The eval gate: read an `adk eval --print_detailed_results` log, exit 0 only
# if it passed.
#
#   ./evals/gate.sh evals/.runs/<run>.log
#
# Never trusts adk eval's exit code (it's 0 even when cases fail): it reads
# "Tests failed: N". Fails closed: a missing or empty log, or no "Tests
# failed" line (a crash, an auth error, a typo'd case id), is a FAIL. A
# rubric metric reported NOT_EVALUATED (the judge errored; ADK still counts
# the case as passed) is a FAIL too. Used by run.sh and cloudbuild.yaml.
set -uo pipefail

LOG="${1:-}"
if [[ -z "$LOG" || ! -s "$LOG" ]]; then
  echo "GATE: FAIL (no eval log at '${LOG}')"; exit 1
fi
FAILED="$(grep -Eo 'Tests failed: [0-9]+' "$LOG" | tail -1 | grep -Eo '[0-9]+$')"
if [[ -z "$FAILED" ]]; then
  echo "GATE: FAIL (no 'Tests failed' line; see $LOG)"; tail -20 "$LOG"; exit 1
elif [[ "$FAILED" -gt 0 ]]; then
  echo "GATE: FAIL ($FAILED case(s) failed)"; exit 1
fi
UNSCORED="$(grep -cE '^Metric: rubric_[a-z0-9_]+, Status: NOT_EVALUATED' "$LOG")"
if [[ "$UNSCORED" -gt 0 ]]; then
  echo "GATE: FAIL ($UNSCORED rubric metric(s) NOT_EVALUATED; the judge errored, see $LOG)"; exit 1
fi
echo "GATE: PASS"
