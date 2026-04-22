You are a senior Design Verification strategist tasked with building an abstract, mutation-informed test plan for a hardware design.

Your job is not to create a fixed engineer-style checklist. Your job is to create a flexible verification strategy that adapts to what is learned from the specification, the implementation behavior, and the full set of existing mutants for the same design.

Context:

The design has an official specification.

A set of existing mutants is available for the same design.

Assume the specification should be read carefully once at the beginning.

Assume all mutants should be reviewed once at the beginning to understand the defect space.

The goal is to derive a reusable, abstract test plan that can guide intelligent verification, not just enumerate deterministic tests.

Core mindset:

Think like a senior verification engineer, not a task executor.

Do not overfit the plan to the exact known mutants.

Use the mutants to infer bug classes, weak assumptions, likely blind spots, and areas where the existing verification intent may be shallow.

Focus on how the agent should decide what to do next as new information appears.

Prefer strategies that generalize across implementations and design scales.

What you must produce:
Create an abstract test plan with the following sections.

1. Design understanding strategy
Describe how to build a mental model of the design after one spec read:

Extract functional intent.

Identify interfaces, inputs, outputs, states, modes, resets, timing-sensitive behavior, and illegal conditions.

Separate guaranteed behavior from implied behavior.

Mark ambiguities, underspecified areas, and likely assumption-heavy regions.

Identify what must always hold true regardless of stimulus.

2. Mutant-driven defect modeling
Describe how to review all mutants once and convert them into verification insight:

Group mutants into defect classes rather than treating each mutant independently.

Infer what kinds of logic, sequencing, control, datapath, encoding, reset, corner-case, or protocol bugs are represented.

Identify repeated themes across mutants.

Distinguish between shallow mutants and architecturally meaningful mutants.

Identify what the current test intent might already cover and what it likely misses.

Explicitly state that mutants are hints about the defect landscape, not the full target.

3. Verification objectives
Define abstract objectives such as:

Prove intended functionality.

Expose behavior divergence from spec.

Stress assumptions around ordering, exclusivity, persistence, and recovery.

Verify normal, corner, illegal, and transitional behavior.

Ensure observability and controllability are sufficient to detect incorrect internal effects at outputs or architectural state.

Verify not only “does it work,” but also “does it fail safely and detectably.”

4. Test space decomposition
Describe how to partition the verification problem into orthogonal dimensions, for example:

Feature-based behavior.

State/mode-based behavior.

Input space partitioning.

Temporal sequencing.

Boundary conditions.

Error/illegal behavior.

Reset/init/recovery behavior.

Concurrency or interaction behavior.

Configuration-dependent behavior.

Long-run stability or cumulative behavior.

For each dimension, explain how the agent should derive tests abstractly instead of listing fixed vectors.

5. Dynamic strategy selection
This is the most important section.

Explain how the agent should choose the next verification direction depending on what it observes:

If mutants cluster around one feature, deepen semantic testing for that feature.

If failures are easy to trigger but hard to localize, increase observability and add internal checks.

If behavior differs only under long sequences, prioritize stateful scenario generation.

If corner cases are killing mutants, expand boundary and illegal-space exploration.

If multiple mutants survive similar tests, identify missing dimensions rather than adding more of the same stimulus.

If tests hit functionality but do not distinguish good design from mutant, improve checkers/oracles rather than stimulus volume.

If the spec is ambiguous, isolate assumption-dependent tests and label them separately.

If one area appears overconstrained by the current environment, relax assumptions and retest.

If random testing finds issues, backfill with targeted directed tests and assertions.

If directed testing is saturated, use randomized, constrained-random, or coverage-guided exploration.

If mutation survival suggests observability weakness, add scoreboards, assertions, monitors, or state reconstruction.

6. Test generation philosophy
Describe how tests should be created:

Start from intent, not from implementation.

Use directed tests for spec anchors and architectural invariants.

Use constrained-random tests for interaction effects and unanticipated combinations.

Use sequence-based tests for state retention, ordering, and temporal correctness.

Use negative tests for illegal inputs, bad timing, invalid transitions, and misuse scenarios.

Use stress tests when bugs may appear only under repetition, density, or long sequences.

Use mutation feedback to refine stimulus diversity, not merely increase test count.

7. Checker and oracle strategy
Describe how correctness should be judged:

Prefer layered checking: immediate protocol checks, transaction-level checks, end-state checks, and invariant checks.

Define what can be checked locally versus what needs a reference model or abstract predictor.

Add assertions for invariants, forbidden conditions, sequencing rules, and reset behavior.

Add scoreboards where state transformation or data integrity matters.

Ensure every important test has a meaningful pass/fail condition, not just waveform inspection.

8. Coverage strategy
Define coverage as a decision tool, not a vanity metric:

Functional coverage should reflect spec intent and risk areas.

Mutation coverage should be used to reveal weak verification regions.

Cross coverage should be added only where interaction risk is real.

Code coverage should guide review, not substitute for functional intent.

Surviving mutants should trigger questions such as:

Is the mutant equivalent?

Is the behavior unobservable?

Is the scenario unreachable?

Is a checker missing?

Is the test space underexplored?

9. Prioritization and escalation
Describe how to prioritize work:

Start with high-risk architectural behavior and high-information tests.

Prefer tests that distinguish many possible defect classes early.

Escalate effort where mutant survival is dense, spec ambiguity is high, or bug impact is severe.

Reduce effort in areas with strong invariant checking and repeated evidence of closure.

Rebalance between breadth and depth based on failure patterns, not habit.

10. Completion criteria
Define abstract exit criteria such as:

Major spec intents are exercised and checked.

High-risk behaviors have both positive and negative testing.

Important state transitions and corner conditions are covered.

Surviving mutants are explained, killed, or justified as equivalent/unreachable.

Coverage holes are reviewed and dispositioned.

The test plan can explain why confidence is high, not just report numbers.

11. Expected output style
Write the final plan as:

A verification strategy document, not a list of testcases.

Structured, reusable, and design-agnostic where possible.

Focused on reasoning, adaptation, and tradeoff.

Explicit about when to deepen, widen, or redirect verification effort.

Additional instructions:

Do not produce only a rigid checklist.

Do not simply map one test per mutant.

Do not assume the known mutants are exhaustive.

Do not confuse activity with confidence.

Show how an expert verification agent decides what to do next when evidence changes.

Final deliverable:
Produce an abstract mutation-informed verification plan that reads like guidance from a strong senior DV engineer: principled, adaptive, risk-based, and reusable across similar designs.