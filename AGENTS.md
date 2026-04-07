# Agent: AI-Assisted Design Verification Agent

## Goal

Build and refine a Verilog testbench for a given verification problem.

For each problem:
- read the natural-language specification,
- inspect all RTL candidates named mutants...v/ mutants...sv,
- generate a complete self-checking Verilog testbench,
- run simulation across all candidates,
- analyze the outputs,
- refine the testbench iteratively,
- stop only when exactly one RTL passes and all others fail.

The final output must be a golden testbench that uniquely identifies the correct RTL candidate.

---

## Project Context

This repository implements a Topic 2 design-verification agent.

Each verification problem contains:
- one natural-language specification,
- multiple RTL candidates,
- exactly one correct RTL implementation.

The agent must generate a Verilog testbench that:
- passes for the correct RTL,
- fails for the incorrect RTLs,
- and can therefore distinguish the correct implementation from the wrong ones.

The workflow is fully automated after launch.

---

## Inputs

For a selected problem, the agent may use:

- `problems/<problem_name>/spec/spec.txt`
- `problems/<problem_name>/rtl/*.v`
- `soft_constraints/global_soft_constraints.md`
- `memory/lessons/cumulative_lessons.md`

---

## Outputs

For a selected problem, the agent is expected to produce:

- generated testbench versions for each iteration,
- simulation-aware refinements,
- iteration notes,
- a final golden testbench,
- detailed and short reports,
- summarized lessons for future problems.

---

## High-Level Behavior

The agent must follow this reasoning pattern:

1. Read and understand the specification.
2. Inspect the RTL candidates and infer the common interface.
3. Use the global soft constraints as guidance for verification planning.
4. Use cumulative summarized lessons from prior problems if available.
5. Generate a complete self-checking Verilog testbench.
6. Trigger simulation using the provided scripts.
7. Read raw simulation outputs and structured summaries.
8. Determine whether exactly one RTL passed and all others failed.
9. If not, analyze why the current testbench is insufficient.
10. Improve the testbench and try again.
11. Record what changed in each iteration.
12. Stop only when a perfect discriminator is found.
13. Summarize lessons from the solved problem for future use.

---

## Required Rules

### Rule 1: Never stop early
Do not stop after generating the first testbench unless the stopping condition is already satisfied.

### Rule 2: Use real simulation feedback
Do not assume correctness from reasoning alone. Use the simulator outputs and refinement loop.

### Rule 3: Treat soft constraints as guidance only
The global soft-constraint document is helpful guidance, not a strict rulebook. Use it strongly, but do not follow it blindly if the simulation evidence suggests a better approach.

### Rule 4: Preserve iteration history
Each iteration must leave behind a clear artifact trail:
- generated testbench,
- simulation outputs,
- structured result summary,
- iteration note describing what changed and why.

### Rule 5: Use cumulative lessons carefully
Use previous summarized lessons to improve first-pass behavior, but do not copy old solutions directly.

### Rule 6: Stop only on a perfect discriminator
A problem is solved only when:
- exactly one RTL candidate passes,
- all remaining RTL candidates fail.

Anything less than that is not success.

---

## Testbench Expectations

The generated testbench should be:

- complete,
- self-checking,
- readable,
- simulation-ready,
- focused on distinguishing behavioral differences among RTL candidates.

The testbench should not be a partial skeleton or a placeholder.

---

## Iteration Strategy

When refining the testbench, the agent should think in terms of:

- missing behavioral coverage,
- edge cases not yet tested,
- reset behavior,
- timing/sequence-sensitive behavior,
- corner cases implied by the specification,
- input combinations not yet exercised,
- weak or ambiguous checks,
- insufficient assertions or pass/fail conditions.

The agent should strengthen the testbench based on observed failures and unexplored behavior.

---

## Cross-Problem Learning

After solving a problem, the agent should extract summarized lessons such as:

- useful verification categories,
- failure patterns,
- successful refinement strategies,
- helpful testbench organization ideas,
- common mistakes to avoid in future problems.

Only summarized lessons should be carried forward, not entire old artifacts.

---

## Files the agent should read first

For a selected problem, read files in this order:

1. `soft_constraints/global_soft_constraints.md`
2. `memory/lessons/cumulative_lessons.md` if it exists and is non-empty
3. `problems/<problem_name>/spec/spec.txt`
4. all RTL files inside `problems/<problem_name>/rtl/`

---

## Files the agent should write during execution

The agent should write outputs inside:

- `outputs/<problem_name>/iterations/iter_XX/`
- `outputs/<problem_name>/final/`
- `outputs/<problem_name>/reports/`

It should also update:

- `memory/lessons/cumulative_lessons.md`

---

## Interaction with scripts

The agent should rely on repository scripts for deterministic tasks such as:

- environment checks,
- simulator invocation,
- result collection,
- output directory preparation,
- final report assembly.

The agent should focus on:
- reasoning,
- testbench generation,
- refinement decisions,
- interpretation of results,
- lesson summarization.

---

## Console behavior

During execution, the system should print concise and useful progress messages such as:

- environment check started
- inputs loaded
- testbench generation started
- simulation started
- iteration result summary
- refinement started
- stopping condition met
- final artifacts written

The agent should support a workflow that is easy for a user or evaluator to follow from the terminal.

---

## Final objective

The final objective is not only to solve one problem, but to improve the verification agent itself.

The repository should evolve toward:
- stronger first-pass testbench generation,
- better iterative refinement,
- clearer reports,
- and better cross-problem verification strategy over time.