#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${1:-mini-project2-topic2-agent}"

echo "Creating project: $PROJECT_NAME"

mkdir -p "$PROJECT_NAME"/{docs,data,agent,prompts,scripts,results,runs,tests}
mkdir -p "$PROJECT_NAME"/results/{visible,hidden,summaries}
mkdir -p "$PROJECT_NAME"/runs/{logs,prompts,generated_tb}

# Example initial problem folders
for p in problem_01 problem_02; do
  mkdir -p "$PROJECT_NAME"/data/$p/{spec,rtl,tb,meta}
  touch "$PROJECT_NAME"/data/$p/spec/spec.txt
  touch "$PROJECT_NAME"/data/$p/tb/generated_tb.v
  touch "$PROJECT_NAME"/data/$p/meta/notes.md
done

# Top-level files
cat > "$PROJECT_NAME"/README.md <<'README'
# Mini Project 2 - Topic 2

AI agent for hardware design verification.

## Goal
Generate a Verilog testbench from a natural-language specification so that the testbench passes the correct RTL implementation and fails incorrect RTL implementations.

## Planned workflow
1. Read the spec.
2. Read candidate RTL files.
3. Generate a self-checking testbench.
4. Run simulation with iverilog.
5. Analyze pass/fail behavior.
6. Refine the testbench iteratively.

## Folder overview
- `docs/` -> planning, workflow, evaluation notes
- `data/` -> per-problem spec, RTL, TB, metadata
- `agent/` -> core Python agent modules
- `prompts/` -> LLM prompt templates
- `scripts/` -> utility runners
- `results/` -> visible/hidden outputs and summaries
- `runs/` -> logs, prompts, generated testbenches
README

cat > "$PROJECT_NAME"/requirements.txt <<'REQ'
openai
python-dotenv
pytest
REQ

cat > "$PROJECT_NAME"/.gitignore <<'GI'
__pycache__/
*.pyc
.env
.venv/
*.out
*.vvp
results/
runs/
GI

# Docs
cat > "$PROJECT_NAME"/docs/phase1_problem_definition.md <<'DOC'
# Phase 1 Problem Definition

## Topic
Topic 2: AI for Design Verification

## Problem
Build an AI agent that takes a natural-language hardware specification and multiple RTL implementations, and generates a Verilog testbench that passes the correct RTL and fails the incorrect RTL implementations.

## Inputs
- Natural-language specification
- Folder of RTL implementations
- Optional simulation logs from previous iterations

## Outputs
- Complete Verilog testbench
- Simulation results for all RTL candidates
- Logs and intermediate reasoning artifacts

## Evaluation
- Testbench compiles successfully
- Testbench passes the correct RTL
- Testbench fails incorrect RTLs
- Quality measured by discrimination ability across problems
DOC

cat > "$PROJECT_NAME"/docs/workflow_design.md <<'DOC'
# Workflow Design

Spec -> parse requirements -> generate testbench -> simulate across RTLs -> analyze results -> refine testbench
DOC

cat > "$PROJECT_NAME"/docs/evaluation_plan.md <<'DOC'
# Evaluation Plan

## Primary checks
- Does the generated testbench compile?
- Does it pass the correct RTL?
- Does it fail incorrect RTLs?

## Later metrics
- Compile success rate
- Number of incorrect RTLs rejected
- Number of iterations required
- Common failure modes
DOC

cat > "$PROJECT_NAME"/docs/paper_notes.md <<'DOC'
# Paper Notes

Use this file to summarize key ideas from:
- AutoBench
- ChipNeMo
- ReAct
- Tree of Thoughts
- Other verification / agent papers
DOC

# Agent files
cat > "$PROJECT_NAME"/agent/main.py <<'PY'
def main():
    # 1. Load one problem
    # 2. Read spec
    # 3. Read RTL candidates
    # 4. Generate testbench
    # 5. Run simulation
    # 6. Save results
    pass

if __name__ == "__main__":
    main()
PY

cat > "$PROJECT_NAME"/agent/spec_parser.py <<'PY'
def parse_spec(spec_text: str):
    # Placeholder for spec parsing logic
    return {}
PY

cat > "$PROJECT_NAME"/agent/rtl_reader.py <<'PY'
def read_rtl_files(rtl_dir: str):
    # Placeholder for RTL file discovery and parsing
    return []
PY

cat > "$PROJECT_NAME"/agent/tb_generator.py <<'PY'
def generate_testbench(spec_text: str, rtl_files):
    # Placeholder for LLM-based testbench generation
    return ""
PY

cat > "$PROJECT_NAME"/agent/sim_runner.py <<'PY'
def run_simulation(testbench_path: str, rtl_paths):
    # Placeholder for iverilog/vvp execution
    return {}
PY

cat > "$PROJECT_NAME"/agent/result_analyzer.py <<'PY'
def analyze_results(sim_results):
    # Placeholder for pass/fail analysis
    return {}
PY

cat > "$PROJECT_NAME"/agent/config.py <<'PY'
MODEL_NAME = "set-me"
IVERILOG_BIN = "iverilog"
VVP_BIN = "vvp"
PY

# Prompt templates
cat > "$PROJECT_NAME"/prompts/parse_spec_prompt.txt <<'TXT'
Extract the hardware requirements from the natural-language specification.
Identify:
- Inputs and outputs
- Reset behavior
- Clocking behavior
- Sequential vs combinational behavior
- Edge cases
- Any examples in the spec
TXT

cat > "$PROJECT_NAME"/prompts/generate_tb_prompt.txt <<'TXT'
Generate a complete self-checking Verilog testbench for the DUT.
The testbench should:
- Instantiate the DUT
- Generate clock/reset if needed
- Apply directed tests
- Check expected outputs
- Print enough debug information for iteration
TXT

cat > "$PROJECT_NAME"/prompts/analyze_failures_prompt.txt <<'TXT'
Analyze the simulation results and identify what behaviors are still not being distinguished by the current testbench.
TXT

cat > "$PROJECT_NAME"/prompts/refine_tb_prompt.txt <<'TXT'
Refine the testbench so it better distinguishes the correct RTL from the incorrect RTL implementations.
TXT

# Utility scripts
cat > "$PROJECT_NAME"/scripts/run_single_problem.py <<'PY'
# Placeholder for running one problem end-to-end
PY

cat > "$PROJECT_NAME"/scripts/run_all_problems.py <<'PY'
# Placeholder for batch execution across all problems
PY

cat > "$PROJECT_NAME"/scripts/compile_tb.py <<'PY'
# Placeholder for compile helper
PY

cat > "$PROJECT_NAME"/scripts/collect_results.py <<'PY'
# Placeholder for summarizing experiment outputs
PY

echo
echo "Project created successfully."
echo "Next:"
echo "  cd $PROJECT_NAME"
echo "  tree ."
