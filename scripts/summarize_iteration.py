#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from problem_context import load_problem_context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create one iteration-level summary for a verification run."
    )
    parser.add_argument(
        "--problem",
        required=True,
        help="Problem name such as problem_1",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Project root directory",
    )
    parser.add_argument(
        "--tag",
        default="manual",
        help="Iteration tag such as manual or iter_001",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def optional_read_json(path: Path) -> dict:
    if path.exists():
        return read_json(path)
    return {}


def main() -> int:
    args = parse_args()

    root = Path(args.root).resolve()
    problem = args.problem
    tag = args.tag

    preflight_path = root / "logs" / "runs" / f"{problem}_preflight_context.json"
    sim_summary_path = (
        root
        / "outputs"
        / problem
        / "iterations"
        / tag
        / "simulation"
        / "summaries"
        / "simulation_summary.json"
    )
    collected_results_path = (
        root
        / "outputs"
        / problem
        / "iterations"
        / tag
        / "analysis"
        / "collected_results.json"
    )

    if not sim_summary_path.exists():
        print(f"[error] Simulation summary not found: {sim_summary_path}")
        return 1

    if not collected_results_path.exists():
        print(f"[error] Collected results not found: {collected_results_path}")
        return 1

    preflight, preflight_path = load_problem_context(root, problem, warn=print)
    sim_summary = optional_read_json(sim_summary_path)
    collected = optional_read_json(collected_results_path)

    spec_files = preflight.get("spec_files", [])
    rtl_files = preflight.get("rtl_files", [])
    combined_spec_path = preflight.get("combined_spec_output", "")
    preflight_available = bool(preflight.get("preflight_available", False))
    context_source = preflight.get("context_source", "unknown")

    total_candidates = collected.get("total_candidates", 0)
    num_passed = collected.get("num_passed", 0)
    num_failed = collected.get("num_failed", 0)
    num_compile_errors = collected.get("num_compile_errors", 0)
    num_run_errors = collected.get("num_run_errors", collected.get("num_run_not_started", 0))
    num_unknown = collected.get("num_unknown", 0)
    overall_status = collected.get("status", "unknown")

    passed_candidates = collected.get("passed_candidates", [])
    failed_candidates = collected.get("failed_candidates", [])
    compile_error_candidates = collected.get("compile_error_candidates", [])
    run_error_candidates = collected.get("run_error_candidates", collected.get("run_not_started_candidates", []))
    unknown_candidates = collected.get("unknown_candidates", [])

    iteration_summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "problem": problem,
        "tag": tag,
        "overall_status": overall_status,
        "inputs": {
            "num_spec_files": len(spec_files),
            "num_rtl_files": len(rtl_files),
            "combined_spec_output": combined_spec_path,
            "preflight_available": preflight_available,
            "context_source": context_source,
        },
        "simulation": {
            "total_candidates": total_candidates,
            "num_passed": num_passed,
            "num_failed": num_failed,
            "num_compile_errors": num_compile_errors,
            "num_run_errors": num_run_errors,
            "num_unknown": num_unknown,
        },
        "decision": {
            "ready_for_finalization": overall_status == "solved",
            "needs_new_testbench_or_refinement": overall_status != "solved",
        },
        "key_candidates": {
            "passed_candidates": passed_candidates,
            "failed_candidates": failed_candidates,
            "compile_error_candidates": compile_error_candidates,
            "run_error_candidates": run_error_candidates,
            "unknown_candidates": unknown_candidates,
        },
        "artifact_paths": {
            "preflight_context": str(preflight_path),
            "simulation_summary": str(sim_summary_path),
            "collected_results": str(collected_results_path),
        },
    }

    report_lines = [
        f"# Iteration Summary: {problem} / {tag}",
        "",
        f"- Timestamp (UTC): {iteration_summary['timestamp_utc']}",
        f"- Overall status: {overall_status}",
        "",
        "## Inputs",
        f"- Context source: {context_source}",
        f"- Preflight available: {'yes' if preflight_available else 'no'}",
        f"- Spec files loaded: {len(spec_files)}",
        f"- RTL candidates loaded: {len(rtl_files)}",
        f"- Combined spec artifact: {combined_spec_path if combined_spec_path else 'N/A'}",
        "",
        "## Simulation Outcome",
        f"- Total candidates: {total_candidates}",
        f"- Passed: {num_passed}",
        f"- Failed: {num_failed}",
        f"- Compile errors: {num_compile_errors}",
        f"- Run errors: {num_run_errors}",
        f"- Unknown: {num_unknown}",
        "",
        "## Decision",
        f"- Ready for finalization: {'yes' if overall_status == 'solved' else 'no'}",
        f"- Needs new testbench or refinement: {'yes' if overall_status != 'solved' else 'no'}",
        "",
        "## Passing Candidates",
    ]

    if passed_candidates:
        report_lines.extend(f"- {name}" for name in passed_candidates)
    else:
        report_lines.append("- None")

    report_lines.extend([
        "",
        "## Failed Candidates",
    ])

    if failed_candidates:
        report_lines.extend(f"- {name}" for name in failed_candidates)
    else:
        report_lines.append("- None")

    report_lines.extend([
        "",
        "## Compile Error Candidates",
    ])

    if compile_error_candidates:
        report_lines.extend(f"- {name}" for name in compile_error_candidates)
    else:
        report_lines.append("- None")

    report_lines.extend([
        "",
        "## Run Error Candidates",
    ])

    if run_error_candidates:
        report_lines.extend(f"- {name}" for name in run_error_candidates)
    else:
        report_lines.append("- None")

    report_lines.extend([
        "",
        "## Unknown Candidates",
    ])

    if unknown_candidates:
        report_lines.extend(f"- {name}" for name in unknown_candidates)
    else:
        report_lines.append("- None")

    out_dir = root / "outputs" / problem / "iterations" / tag / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_json_path = out_dir / "iteration_summary.json"
    summary_md_path = out_dir / "iteration_summary.md"

    summary_json_path.write_text(
        json.dumps(iteration_summary, indent=2),
        encoding="utf-8",
    )
    summary_md_path.write_text(
        "\n".join(report_lines) + "\n",
        encoding="utf-8",
    )

    print(f"[info] Preflight context: {preflight_path}")
    if not preflight_available:
        print("[info] Iteration summary used inferred problem context.")
    print(f"[info] Simulation summary: {sim_summary_path}")
    print(f"[info] Collected results: {collected_results_path}")
    print(f"[info] Overall status: {overall_status}")
    print(f"[info] Iteration summary JSON written to: {summary_json_path}")
    print(f"[info] Iteration summary report written to: {summary_md_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
