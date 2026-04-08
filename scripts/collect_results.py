#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect and normalize simulation results for one problem run."
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
        help="Run tag used to locate simulation outputs",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()

    root = Path(args.root).resolve()
    problem = args.problem
    tag = args.tag

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

    if not sim_summary_path.exists():
        print(f"[error] Simulation summary not found: {sim_summary_path}")
        return 1

    sim_summary = read_json(sim_summary_path)
    results = sim_summary.get("results", [])

    passed = []
    failed = []
    compile_errors = []
    run_errors = []
    unknown = []

    for item in results:
        status = item.get("status")
        candidate_name = item.get("candidate") or item.get("candidate_name")

        if status == "pass":
            passed.append(candidate_name)
        elif status == "fail":
            failed.append(candidate_name)
        elif status == "compile_error":
            compile_errors.append(candidate_name)
        elif status == "run_error":
            run_errors.append(candidate_name)
        else:
            unknown.append(candidate_name)

    solved = len(passed) == 1 and len(failed) + len(compile_errors) + len(run_errors) + len(unknown) == len(results) - 1

    status_label = "solved" if solved else "unsolved"

    interpretation = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "problem": problem,
        "tag": tag,
        "status": status_label,
        "total_candidates": len(results),
        "num_passed": len(passed),
        "num_failed": len(failed),
        "num_compile_errors": len(compile_errors),
        "num_run_errors": len(run_errors),
        "num_unknown": len(unknown),
        "passed_candidates": passed,
        "failed_candidates": failed,
        "compile_error_candidates": compile_errors,
        "run_error_candidates": run_errors,
        "unknown_candidates": unknown,
        "decision": {
            "exactly_one_pass": len(passed) == 1,
            "ready_for_refinement": not solved,
            "ready_for_finalization": solved,
        },
        "notes": [
            "A valid final discriminator requires exactly one passing RTL candidate.",
            "All other candidates must fail or otherwise be rejected by the generated testbench.",
            "Compile errors are currently tracked separately from simulation failures.",
        ],
    }

    report_lines = [
        f"Problem: {problem}",
        f"Tag: {tag}",
        f"Overall status: {status_label}",
        "",
        f"Total candidates: {len(results)}",
        f"Passed: {len(passed)}",
        f"Failed: {len(failed)}",
        f"Compile errors: {len(compile_errors)}",
        f"Run errors: {len(run_errors)}",
        f"Unknown: {len(unknown)}",
        "",
        "Passed candidates:",
    ]

    if passed:
        report_lines.extend(f"- {name}" for name in passed)
    else:
        report_lines.append("- None")

    report_lines.extend([
        "",
        "Failed candidates:",
    ])

    if failed:
        report_lines.extend(f"- {name}" for name in failed)
    else:
        report_lines.append("- None")

    report_lines.extend([
        "",
        "Compile error candidates:",
    ])

    if compile_errors:
        report_lines.extend(f"- {name}" for name in compile_errors)
    else:
        report_lines.append("- None")

    report_lines.extend([
        "",
        "Run-error candidates:",
    ])

    if run_errors:
        report_lines.extend(f"- {name}" for name in run_errors)
    else:
        report_lines.append("- None")

    report_lines.extend([
        "",
        "Unknown candidates:",
    ])

    if unknown:
        report_lines.extend(f"- {name}" for name in unknown)
    else:
        report_lines.append("- None")

    out_dir = root / "outputs" / problem / "iterations" / tag / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    interpretation_json = out_dir / "collected_results.json"
    interpretation_md = out_dir / "collected_results.md"

    interpretation_json.write_text(
        json.dumps(interpretation, indent=2),
        encoding="utf-8",
    )
    interpretation_md.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"[info] Loaded simulation summary: {sim_summary_path}")
    print(f"[info] Total candidates: {len(results)}")
    print(f"[info] Passed: {len(passed)}")
    print(f"[info] Failed: {len(failed)}")
    print(f"[info] Compile errors: {len(compile_errors)}")
    print(f"[info] Run errors: {len(run_errors)}")
    print(f"[info] Unknown: {len(unknown)}")
    print(f"[info] Overall status: {status_label}")
    print(f"[info] Analysis JSON written to: {interpretation_json}")
    print(f"[info] Analysis report written to: {interpretation_md}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
