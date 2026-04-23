# AI-Assisted Design Verification Agent

This repository implements an agentic verification loop for Topic 2 style design-verification problems. Given a natural-language specification and a set of RTL candidates with exactly one correct implementation, the system asks Codex to generate or refine a Verilog/SystemVerilog testbench, simulates that testbench against every candidate with Icarus Verilog, and keeps iterating until exactly one RTL passes.

The main user-facing entrypoint in the current codebase is:

```bash
./verifier --problem problem_1
```

## What The Current Code Actually Does

The current primary flow is implemented in [scripts/verifier.py](/mnt/c/Personal/MSE_ASU/sem2/SEM2_VLSI_DESIGN_AUTOMATION/project_2/scripts/verifier.py). On each iteration it:

1. Reads the selected problem's `spec/` files and all RTL files in `rtl/`.
2. Reads `soft_constraints/global_soft_constraints.md`.
3. Builds a Codex prompt for either first-pass generation or refinement from the previous iteration.
4. Runs `codex exec --full-auto`.
5. Expects Codex to write a complete testbench to `outputs/<problem>/iterations/iter_xx/generated_tb.v`.
6. Runs `iverilog -g2012` and `vvp` on every RTL candidate.
7. Classifies outcomes using `TB_PASS` and `TB_FAIL`.
8. Writes simulation, analysis, and summary artifacts.
9. Stops when exactly one candidate passes and all others fail with no compile/run/unknown statuses.

If a golden discriminator is found, the testbench is copied to:

```text
outputs/<problem>/final/golden_tb.v
```

## Current Status And Scope

This README is based on the current code, not just the original scaffold idea.

- `./verifier` is the recommended entrypoint.
- `scripts/bootstrap_env.py` is useful for preflight checks, but it currently validates `python3`, `iverilog`, and `vvp` only. It does not check for `codex`.
- `scripts/iterate_to_golden.py` is a lower-level alternative loop that creates explicit `agent_input/iteration_packet.*` files before calling `scripts/run_codex_refinement.sh`.
- `memory/lessons/cumulative_lessons.md`, `scripts/load_memory.py`, and `scripts/finalize_report.py` exist, but they are not the main driver of the current one-command path.
- `Dockerfile` and `docker-compose.yml` are placeholders right now, so the README below focuses on local setup.

## Success Condition

A run is considered solved only when:

- exactly one RTL candidate passes,
- every other RTL candidate fails,
- there are no compile errors,
- there are no run errors,
- there are no unknown verdicts caused by missing `TB_PASS` or `TB_FAIL`.

## Repository Layout

```text
.
├── AGENTS.md
├── README.md
├── requirements.txt
├── verifier
├── problems/
│   └── problem_x/
│       ├── spec/
│       └── rtl/
├── scripts/
│   ├── verifier.py
│   ├── bootstrap_env.py
│   ├── run_simulation.py
│   ├── collect_results.py
│   ├── summarize_iteration.py
│   ├── iterate_to_golden.py
│   ├── prepare_agent_iteration.py
│   └── run_codex_refinement.sh
├── soft_constraints/
│   └── global_soft_constraints.md
├── memory/
│   └── lessons/
├── outputs/
└── logs/
```

## Core Requirements

To run the current verifier flow, you need:

- `python3`
- `pip`
- `iverilog`
- `vvp`
- `node` and `npm`
- OpenAI Codex CLI available as `codex`
- an authenticated Codex session via `codex login`

The verifier also assumes a Unix-like shell because it relies on Bash scripts and paths. That is why Windows users should use WSL instead of native PowerShell for the actual verifier run.

## Quick Start

If you already have the toolchain installed:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/bootstrap_env.py --problem problem_1 --root .
codex --help
./verifier --problem problem_1 --max-iters 3
```

Use any problem directory that exists under `problems/` and contains both `spec/` and `rtl/`.

## Follow-Along Setup For Viewers

- [Windows Setup](#windows-users-use-wsl)
- [macOS Setup](#macos-users)
- [Linux Setup](#linux-users)

### Windows Users: Use WSL
The Agentic Flow implementation depends on a linux based system, hence use WSL.

Run `./verifier` inside Ubuntu on WSL, not in PowerShell.\
Install WSL once from an elevated PowerShell window:

```powershell
wsl --install -d Ubuntu
```

Then Skip to the instructions for linux users @ [Linux Setup](#linux-users)
### macOS Users

Run this in Terminal:

```bash
xcode-select --install
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install git python node icarus-verilog
git clone <your-repo-url> project_2
cd project_2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install -g @openai/codex
codex login
python3 scripts/bootstrap_env.py --problem problem_1 --root .
./verifier --problem problem_1 --max-iters 3
```

### Linux Users

These commands assume Ubuntu or Debian:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip iverilog nodejs npm
git clone <your-repo-url> project_2
cd project_2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install -g @openai/codex
codex login
python3 scripts/bootstrap_env.py --problem problem_1 --root .
./verifier --problem problem_1 --max-iters 3
```

If the run succeeds, the final testbench is written to `outputs/problem_1/final/golden_tb.v`.

## What A Run Produces

A typical successful or partial run writes artifacts like these:

```text
outputs/problem_1/
├── final/
│   └── golden_tb.v
├── iterations/
│   └── iter_01/
│       ├── codex_prompt.txt
│       ├── generated_tb.v
│       ├── iteration_meta.json
│       ├── codex/
│       │   ├── final_message.txt
│       │   ├── events.jsonl
│       │   ├── live_output.log
│       │   └── stderr.log
│       ├── simulation/
│       │   └── summaries/simulation_summary.json
│       ├── analysis/
│       │   └── collected_results.json
│       └── reports/
│           ├── iteration_summary.json
│           └── iteration_summary.md
```

## Manual Commands You May Want

Run environment preflight:

```bash
python3 scripts/bootstrap_env.py --problem problem_1 --root .
```

Run a manual simulation for one generated testbench:

```bash
python3 scripts/run_simulation.py \
  --problem problem_1 \
  --root . \
  --tag iter_01 \
  --tb outputs/problem_1/iterations/iter_01/generated_tb.v
```

Collect normalized results:

```bash
python3 scripts/collect_results.py --problem problem_1 --root . --tag iter_01
```

Create the iteration summary:

```bash
python3 scripts/summarize_iteration.py --problem problem_1 --root . --tag iter_01
```

Run the packetized refinement loop instead of the direct verifier:

```bash
python3 scripts/iterate_to_golden.py --problem problem_1 --root . --max-iters 3
```

That alternative flow is the one that writes `agent_input/iteration_packet.json` and `agent_input/agent_handoff_prompt.txt`.

## Troubleshooting

- If `bootstrap_env.py` passes but `./verifier` fails immediately, check whether `codex` is installed and logged in.
- If simulations compile but end as `unknown`, the generated testbench probably did not emit `TB_PASS` or `TB_FAIL`.
- If everything fails to compile, inspect `outputs/<problem>/iterations/<tag>/simulation/logs/*.json`.
- If Codex generated no testbench, inspect `outputs/<problem>/iterations/<tag>/codex/final_message.txt` and `events.jsonl`.
- If you are on Windows, make sure you are inside WSL when running Bash commands.

## External Setup References Used For This README

- OpenAI Codex CLI getting started: https://help.openai.com/en/articles/11096431-openai-codex-ci-getting-started
- OpenAI Codex CLI sign-in flow: https://help.openai.com/en/articles/11381614
- Microsoft WSL install guide: https://learn.microsoft.com/en-us/windows/wsl/install
- Microsoft WSL command reference: https://learn.microsoft.com/en-us/windows/wsl/basic-commands
- Homebrew install page: https://brew.sh/
- Homebrew installation docs: https://docs.brew.sh/Installation.html
- Homebrew `icarus-verilog` formula: https://formulae.brew.sh/formula/icarus-verilog
- Node.js download/install hub: https://nodejs.org/en/download/package-manager
