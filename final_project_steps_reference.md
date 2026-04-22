# Final Project Steps Reference

## Overview

This project targets Topic 2: AI for Design Verification, where the system receives a natural-language specification and multiple RTL implementations, then generates a Verilog testbench that passes the correct RTL and fails the incorrect RTLs.[cite:1][cite:2]

The workflow follows the iterative agent pattern described in the project materials: read inputs, generate an artifact, run simulation, analyze outputs, update the artifact, and repeat until the stopping condition is met.[cite:1][cite:3]

## End-to-End Lifecycle

### Step 1: Define the product contract
Define the tool as a one-command verifier such as `verifier --problem problem_1`, where the system automatically prepares the environment, runs the agent workflow, iterates until a single correct RTL is isolated, and returns final artifacts.[cite:1][cite:2]

### Step 2: Freeze the problem definition
Lock the project around Topic 2: one natural-language specification, multiple RTL implementations, exactly one correct implementation, and a generated Verilog testbench that passes the correct RTL and fails the incorrect RTLs.[cite:1][cite:2]

### Step 3: Choose the agent runtime
Use Codex CLI as the main agent interface, since the course materials explicitly allow Codex CLI and the provided template demonstrates a Codex-style iterative agent workflow.[cite:1][cite:3]

### Step 4: Choose the execution boundary
Use Docker as the reproducible execution boundary so the same dependencies, simulator, and scripts can run consistently.[cite:2]

### Step 5: Define the permanent inputs
Treat the following as permanent, version-controlled inputs: the problem specification, the RTL candidates, the one-time global soft-constraint document, the repository instructions for the agent, and the deterministic scripts used for simulation and reporting.

### Step 6: Define the generated artifacts
Treat the following as generated outputs of each run: initial testbench, refined testbench versions, simulation results, failure analyses, iteration comparison notes, final golden testbench, and the short professor-facing report.[cite:1]

### Step 7: Organize the repository around the runtime flow
Structure the repository so the agent can clearly find problem inputs, write generated testbenches, store run logs, and preserve cross-problem learning summaries.[cite:2][cite:3]

### Step 8: Create the agent instruction layer
Add an `AGENTS.md` file that tells Codex exactly how to behave inside the repository: read the spec, consult the soft constraints, inspect RTL candidates, generate a self-checking testbench, run or trigger simulation, analyze failures, revise the testbench, record what changed, and stop only when a perfect discriminator is found.[cite:3]

### Step 9: Ingest the one-time soft constraints
At the beginning of the project, load the global soft-constraint document and treat it as senior-engineer guidance for verification planning, test categorization, code organization, and refinement strategy.

### Step 10: Internalize, don’t repeatedly reread
After the initial use of the soft constraints, operate on summarized internal lessons rather than re-consuming the original global note on every iteration.

### Step 11: Generate the first-pass testbench
For a selected problem, read the spec and RTL candidates, infer interface and behavior, and generate the first complete self-checking Verilog testbench.[cite:1][cite:2]

### Step 12: Run simulation automatically
Compile and run the generated testbench against all RTL candidates using Icarus Verilog in a script-driven and deterministic way.[cite:1][cite:2]

### Step 13: Collect raw outputs
Capture raw artifacts such as compilation status, runtime status, console outputs, assertion messages, and related diagnostics so the agent can analyze tool outputs directly.[cite:1]

### Step 14: Analyze iteration quality
After each run, determine whether exactly one RTL passed and all others failed, and classify why the current testbench is still insufficient if that goal was not achieved.[cite:1][cite:2]

### Step 15: Produce an iteration comparison note
At the end of every iteration, create a structured note describing what changed in the testbench, why it changed, what verification categories were added or strengthened, and how the pass/fail signature evolved.[cite:1]

### Step 16: Refine the testbench autonomously
Use the previous testbench, simulation evidence, and iteration comparison note to create the next testbench version without requiring any new human input.[cite:1][cite:3]

### Step 17: Stop only on a perfect discriminator
Stop only when exactly one RTL passes and every other RTL fails under the generated testbench.[cite:1][cite:2]

### Step 18: Emit the final deliverables
Emit the golden testbench, the detailed report, all iteration logs, and a short professor-facing evaluation note.[cite:1]

### Step 19: Extract cross-problem lessons
After solving a problem, distill only the summarized lessons from that run into a reusable learning artifact for future problems.[cite:1]

### Step 20: Apply cumulative learning to the next problem
When the next problem is launched, use the cumulative summarized lessons from all prior solved problems to improve first-pass planning and testbench generation.[cite:1]

## Verification Checkpoints

### Checkpoint 1: Setup correctness
Verify that one command can initialize the environment, locate the chosen problem, load the global soft constraints, and start the workflow without manual patching.[cite:2]

### Checkpoint 2: First-pass quality
Verify that the first generated testbench is syntactically valid, runs under Icarus Verilog, and produces useful discrimination data even if it is not yet perfect.[cite:1][cite:2]

### Checkpoint 3: Iteration quality
Verify that each iteration produces a better-informed next step rather than a random rewrite.[cite:1][cite:3]

### Checkpoint 4: Stop quality
Verify that the final testbench is a true perfect discriminator for the problem under test.[cite:1][cite:2]

### Checkpoint 5: Learning quality
Verify that the summarized lessons from solved problems are reusable and actually influence the first pass on later problems.[cite:1]

## MVP

The MVP should support one problem at a time, one global soft-constraint document, one fully automated command, one iterative loop, deterministic script-driven simulation, and a final output package containing the golden testbench plus logs and report.[cite:1][cite:2][cite:3]

The MVP is successful when it can solve at least one visible problem end to end with no manual intervention after launch.[cite:1][cite:2]

## Advanced Improvement

After the MVP works, strengthen the iteration engine so it reasons more explicitly about uncovered verification categories, edge cases, signal timing behavior, and gaps in the current testbench.[cite:1]

Add cumulative summarized lessons that shape future first-pass behavior without replaying every old artifact, and improve the short report so it highlights iteration-by-iteration changes and prior-lesson impact on later problems.[cite:1]

## Future Productization

Later work can improve user experience, robustness, and generalization across a broader set of verification tasks while preserving the same core agent workflow.[cite:1]
