#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="${1:-$PWD}"

mkdir -p "$ROOT_DIR"

mkdir -p \
  "$ROOT_DIR/soft_constraints" \
  "$ROOT_DIR/problems/problem_1/spec" \
  "$ROOT_DIR/problems/problem_1/rtl" \
  "$ROOT_DIR/problems/problem_1/expected" \
  "$ROOT_DIR/problems/problem_2/spec" \
  "$ROOT_DIR/problems/problem_2/rtl" \
  "$ROOT_DIR/problems/problem_2/expected" \
  "$ROOT_DIR/scripts" \
  "$ROOT_DIR/agent_runtime/prompts" \
  "$ROOT_DIR/agent_runtime/parsers" \
  "$ROOT_DIR/agent_runtime/analyzers" \
  "$ROOT_DIR/agent_runtime/templates" \
  "$ROOT_DIR/outputs/problem_1/iterations" \
  "$ROOT_DIR/outputs/problem_1/final" \
  "$ROOT_DIR/outputs/problem_1/reports" \
  "$ROOT_DIR/outputs/problem_2/iterations" \
  "$ROOT_DIR/outputs/problem_2/final" \
  "$ROOT_DIR/outputs/problem_2/reports" \
  "$ROOT_DIR/memory/lessons" \
  "$ROOT_DIR/memory/summaries" \
  "$ROOT_DIR/logs/system" \
  "$ROOT_DIR/logs/runs" \
  "$ROOT_DIR/tests"

touch \
  "$ROOT_DIR/README.md" \
  "$ROOT_DIR/AGENTS.md" \
  "$ROOT_DIR/Dockerfile" \
  "$ROOT_DIR/docker-compose.yml" \
  "$ROOT_DIR/requirements.txt" \
  "$ROOT_DIR/verifier" \
  "$ROOT_DIR/soft_constraints/global_soft_constraints.md" \
  "$ROOT_DIR/problems/problem_1/spec/spec.txt" \
  "$ROOT_DIR/problems/problem_1/expected/README.md" \
  "$ROOT_DIR/problems/problem_2/expected/README.md" \
  "$ROOT_DIR/scripts/bootstrap_env.py" \
  "$ROOT_DIR/scripts/run_problem.py" \
  "$ROOT_DIR/scripts/run_simulation.py" \
  "$ROOT_DIR/scripts/collect_results.py" \
  "$ROOT_DIR/scripts/summarize_iteration.py" \
  "$ROOT_DIR/scripts/finalize_report.py" \
  "$ROOT_DIR/scripts/load_memory.py" \
  "$ROOT_DIR/memory/lessons/cumulative_lessons.md"

chmod +x \
  "$ROOT_DIR/verifier" \
  "$ROOT_DIR/scripts/bootstrap_env.py" \
  "$ROOT_DIR/scripts/run_problem.py" \
  "$ROOT_DIR/scripts/run_simulation.py" \
  "$ROOT_DIR/scripts/collect_results.py" \
  "$ROOT_DIR/scripts/summarize_iteration.py" \
  "$ROOT_DIR/scripts/finalize_report.py" \
  "$ROOT_DIR/scripts/load_memory.py"

printf 'Scaffold created at: %s\n' "$ROOT_DIR"
