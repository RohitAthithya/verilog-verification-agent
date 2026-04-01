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
