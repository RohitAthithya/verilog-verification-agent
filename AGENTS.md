# Agent: AI-Assisted Design Verification Agent

## Goal

Build and iteratively refine a Verilog/SystemVerilog testbench for a Topic 2 design-verification problem.

For each selected problem, the agent should:
- read the natural-language specification,
- inspect the RTL candidates,
- read the latest iteration packet and simulation summaries,
- improve the testbench generation or refinement flow,
- preserve compatibility with iverilog -g2012,
- preserve TB_PASS and TB_FAIL markers,
- use simulation feedback to improve the next iteration.

The immediate objective is to improve the generation/refinement loop, not to hardcode a one-off fix for a single generated testbench.

---

## Project Context

This repository implements a Topic 2 design-verification agent.

Each verification problem contains:
- one natural-language specification,
- multiple RTL candidates,
- exactly one correct RTL implementation.

The agent must help generate a Verilog testbench that:
- passes for the correct RTL,
- fails for incorrect RTLs,
- and improves over repeated simulation-guided iterations.

---

## Inputs

For a selected problem, the agent may use:
- `logs/runs/<problem_name>_preflight_context.json`
- `outputs/<problem_name>/iterations/<tag>/agent_input/iteration_packet.json`
- `outputs/<problem_name>/iterations/<tag>/agent_input/iteration_packet.md`
- `outputs/<problem_name>/iterations/<tag>/generated_tb.v`
- `outputs/<problem_name>/iterations/<tag>/simulation/summaries/simulation_summary.json`
- `outputs/<problem_name>/iterations/<tag>/analysis/collected_results.json`
- problem specification files and RTL files referenced by the preflight context

---

## Outputs

The agent may update or create:
- testbench generation/refinement scripts,
- prompt templates,
- generated testbench versions,
- iteration notes,
- reusable workflow helpers,
- reports or summaries for the current iteration.

---

## Required Rules

### Rule 1: Use real simulation feedback
Do not rely on reasoning alone. Use simulation summaries, stdout/stderr, and pass/fail markers.

### Rule 2: Preserve the harness
Do not break the existing run/simulation/result-collection pipeline unless explicitly necessary.

### Rule 3: Preserve verdict markers
Generated testbenches must continue to emit TB_PASS and TB_FAIL markers so downstream scripts can classify outcomes.

### Rule 4: Prefer reusable fixes
Prefer improving the generator, prompt, or refinement workflow over patching a single generated testbench by hand.

### Rule 5: Stay compatible with iverilog
Generated output should remain compatible with iverilog using `-g2012`.

### Rule 6: Leave a trace
When changing files, explain:
- what changed,
- why it changed,
- what command should be run next,
- what result is expected.

---

## Files to read first

For a selected problem, read files in this order:
1. `outputs/<problem_name>/iterations/<tag>/agent_input/agent_handoff_prompt.txt`
2. `outputs/<problem_name>/iterations/<tag>/agent_input/iteration_packet.md`
3. `outputs/<problem_name>/iterations/<tag>/agent_input/iteration_packet.json`
4. `scripts/run_simulation.py`
5. `scripts/collect_results.py`
6. `scripts/summarize_iteration.py`
7. the current generation/refinement scripts

---

## Interaction Style

While working, provide concise progress updates such as:
- reading current iteration packet
- inspecting current generation flow
- updating refinement logic
- ready to rerun simulation

At the end of each task, always provide:
1. files changed,
2. why they changed,
3. exact commands to run next,
4. what to check in the results.