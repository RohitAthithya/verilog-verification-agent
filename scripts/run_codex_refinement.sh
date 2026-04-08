#!/usr/bin/env bash
set -euo pipefail

PROBLEM="${1:-problem_1}"
TAG="${2:-manual}"
ROOT="${3:-.}"

ITER_DIR="${ROOT}/outputs/${PROBLEM}/iterations/${TAG}"
AGENT_INPUT_DIR="${ITER_DIR}/agent_input"
PROMPT_FILE="${AGENT_INPUT_DIR}/agent_handoff_prompt.txt"
CODEX_LOG_DIR="${ITER_DIR}/codex"
CODEX_MSG="${CODEX_LOG_DIR}/last_message.txt"
CODEX_EVENTS="${CODEX_LOG_DIR}/events.jsonl"

mkdir -p "${CODEX_LOG_DIR}"

if [ ! -f "${PROMPT_FILE}" ]; then
  echo "[error] Missing prompt file: ${PROMPT_FILE}"
  exit 1
fi

echo "[info] Running Codex refinement for ${PROBLEM} (${TAG})"
echo "[info] Prompt file: ${PROMPT_FILE}"

codex exec \
  -C "${ROOT}" \
  --full-auto \
  --json \
  -o "${CODEX_MSG}" \
  - < "${PROMPT_FILE}" | tee "${CODEX_EVENTS}"

echo "[info] Codex final message saved to: ${CODEX_MSG}"
echo "[info] Codex event log saved to: ${CODEX_EVENTS}"
