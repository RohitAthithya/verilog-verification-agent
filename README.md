# AI-Assisted Design Verification Agent

## Project Overview

This project implements an AI-assisted verification agent for hardware design verification.

The system targets **Topic 2: AI for Design Verification**:\
Where the *input* is:
- **Spec**:         a natural-language hardware specification
- **Mutants**:      multiple RTL implementations of the same design
- **Golden RTL**:   exactly one RTL implementation is correct out of all the mutants

The goal of the system is to automatically generate a **complete Verilog testbench** that:
- passes for the *correct* RTL implementation,
- fails for *all the other incorrect* RTL implementations,
- and can therefore identify the correct design automatically.

The project is designed as a **fully automated verification workflow**. \
A user should be able to run a single command such as:

```bash
./verifier --problem problem_1
```

---

## Problem Statement

Verification is one of the most expensive and time-consuming stages in chip design.

This project explores whether an AI agent can:
- understand a natural-language specification,
- inspect a set of RTL candidates,
- reason about verification strategies,
- generate a self-checking Verilog testbench,
- analyze simulation failures,
- refine the generated testbench over multiple iterations,
- and improve its future first-pass behavior using summarized lessons from previously solved problems.

The final objective is not only to solve one verification problem, but also to build a verification agent that improves over time and can later be used as a reliable product-style tool.

---

## Inputs to the System

For each problem, the system receives:

- `spec/spec.txt`  
  A natural-language description of the required RTL behavior.\
  It can be a simple textual description as well.

- `rtl/*.v`  
  Mutants: Multiple RTL candidate implementations for the same problem.

- `soft_constraints/global_soft_constraints.md`  
  A one-time global soft-constraint document containing senior-engineer-style verification guidance, strategy hints, checklist ideas, and test-planning structure.

- `memory/lessons/cumulative_lessons.md`  
  A cumulative summary of lessons learned from previously solved problems.\
  For the first problem the agent solves, this is empty/blank.

---

## Outputs of the System

For each problem, the system generates:

- a first-pass generated Verilog testbench,
- refined testbench versions across iterations,
- simulation logs,
- structured result summaries,
- iteration-by-iteration comparison notes,
- a final golden testbench,
- a detailed report,
- a short professor-facing summary report.

---

## Evaluation Method

A problem is considered solved only when:

- exactly one RTL implementation passes the generated testbench, and
- all other RTL implementations fail.

This project does **not** accept partial discrimination as success.

If a perfect discriminator is not found, the generated testbench is considered insufficient and the workflow must be refined.

---

## System Workflow

The end-to-end workflow is:

1. User runs the verifier command for a selected problem such as problem_1.
2. Environment and dependencies are checked.
3. The problem specification and RTL candidates are loaded.
4. The global soft constraints are loaded once as guidance.
5. Previously learned summarized lessons are loaded.
6. The agent generates an initial self-checking testbench.
7. The system runs simulation on all RTL candidates.
8. The system collects raw results and structured summaries.
9. The agent analyzes the failures and weaknesses of the current testbench.
10. The agent produces the next improved testbench version.
11. The loop repeats until exactly one RTL passes and all others fail.
12. The final golden testbench, reports, and iteration logs are emitted.
13. The system updates the cumulative lesson summary for future problems.

---

## Repository Structure

```text
.
├── README.md
├── AGENTS.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── verifier
├── soft_constraints/
│   └── global_soft_constraints.md
├── problems/
│   ├── problem_1/
│   │   ├── spec/
│   │   │   └── spec.txt
│   │   ├── rtl/
│   │   └── expected/
│   └── problem_2/
├── scripts/
│   ├── bootstrap_env.py
│   ├── run_problem.py
│   ├── run_simulation.py
│   ├── collect_results.py
│   ├── summarize_iteration.py
│   ├── finalize_report.py
│   └── load_memory.py
├── agent_runtime/
│   ├── prompts/
│   ├── parsers/
│   ├── analyzers/
│   └── templates/
├── outputs/
├── memory/
├── logs/
└── tests/
```

---

## Important Design Choices

### 1. Fully automated execution
Once the user runs the command, the workflow should continue automatically without requiring manual intervention during iterations.

### 2. One-time soft constraints
A senior-engineer style guidance is provided once for the project as a global soft-constraint document.\
It is meant to guide the agent, not rigidly constrain it.

### 3. Iterative refinement
The system improves the current testbench version using real simulation outputs and structured iteration notes.

### 4. Cross-problem learning
After solving a problem, the system stores only **summarized lessons** from that problem and uses them to improve first-pass performance on future problems.

### 5. Strict stopping condition
The loop stops only when exactly one RTL passes and all others fail.

---

## Tools and Technologies

The project uses:

- **Python** for orchestration, scripting, result handling, and pipeline control.
- **Icarus Verilog (`iverilog`)** for Verilog compilation and simulation.
- **Codex CLI / agent workflow** for repository-based agent reasoning and iterative generation.
- **Docker** for reproducible execution and evaluation.
- **WSL/Linux shell workflow** for local development and command execution.

---

## Running the Project

The intended interface is:

```bash
./verifier --problem problem_1
```

---

## Expected Final Artifacts

At the end of a successful run, the user should receive:

- the final golden testbench,
- all iteration logs,
- simulation summaries,
- detailed report,
- short evaluation summary.

---

## Current Status

Current development focus:
- defining the end-to-end lifecycle,
- building the repository structure,
- defining the responsibilities of all files and folders,
- creating the initial runnable project skeleton,
- and implementing the first version of the automation pipeline.

---

## Long-Term Goal

The long-term goal of this project is to build a reliable AI-assisted verification agent that:
- solves the current benchmark problems,
- improves through cumulative summarized lessons,
- and can later be used as a reusable verification tool for future hardware design tasks.