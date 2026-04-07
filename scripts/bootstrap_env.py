#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_TOOLS = ["python3", "iverilog", "vvp"]
OPTIONAL_TOOLS = ["docker"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap and validate the local verification-agent environment."
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
    return parser.parse_args()


def tool_status(tool_name: str) -> dict:
    path = shutil.which(tool_name)
    return {
        "tool": tool_name,
        "found": path is not None,
        "path": path,
    }


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)


def main() -> int:
    args = parse_args()

    root = Path(args.root).resolve()
    problem = args.problem

    problems_dir = root / "problems"
    problem_dir = problems_dir / problem
    spec_dir = problem_dir / "spec"
    rtl_dir = problem_dir / "rtl"

    soft_constraints_file = root / "soft_constraints" / "global_soft_constraints.md"
    memory_file = root / "memory" / "lessons" / "cumulative_lessons.md"

    outputs_problem_dir = root / "outputs" / problem
    iterations_dir = outputs_problem_dir / "iterations"
    final_dir = outputs_problem_dir / "final"
    reports_dir = outputs_problem_dir / "reports"

    logs_system_dir = root / "logs" / "system"
    logs_runs_dir = root / "logs" / "runs"

    print(f"[info] Using project root: {root}")
    print(f"[info] Selected problem: {problem}")

    if not root.exists():
        print(f"[error] Project root does not exist: {root}")
        return 1

    if not problem_dir.exists():
        print(f"[error] Problem directory not found: {problem_dir}")
        return 1

    if not spec_dir.exists():
        print(f"[error] Spec directory not found: {spec_dir}")
        return 1

    spec_files = sorted(
        [
            p for p in spec_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".md", ".txt", ".rst"}
        ]
    )

    if not spec_files:
        print(f"[error] No supported spec files found in: {spec_dir}")
        return 1

    print(f"[info] Found {len(spec_files)} spec file(s).")
    for spec_path in spec_files:
        print(f"[info] Spec input: {spec_path}")

    if not rtl_dir.exists():
        print(f"[error] RTL directory not found: {rtl_dir}")
        return 1

    rtl_files = sorted(rtl_dir.glob("*.v"))
    if rtl_files:
        print(f"[info] Found {len(rtl_files)} RTL candidate file(s).")
    else:
        print("[warn] No RTL .v files found yet in the rtl directory.")

    ensure_file(soft_constraints_file)
    ensure_file(memory_file)

    ensure_dir(iterations_dir)
    ensure_dir(final_dir)
    ensure_dir(reports_dir)
    ensure_dir(logs_system_dir)
    ensure_dir(logs_runs_dir)

    required = [tool_status(tool) for tool in REQUIRED_TOOLS]
    optional = [tool_status(tool) for tool in OPTIONAL_TOOLS]

    missing_required = [item["tool"] for item in required if not item["found"]]

    for item in required:
        if item["found"]:
            print(f"[ok] Required tool found: {item['tool']} -> {item['path']}")
        else:
            print(f"[error] Required tool missing: {item['tool']}")

    for item in optional:
        if item["found"]:
            print(f"[ok] Optional tool found: {item['tool']} -> {item['path']}")
        else:
            print(f"[warn] Optional tool missing: {item['tool']}")

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "problem": problem,
        "spec_dir": str(spec_dir),
        "spec_files": [str(p) for p in spec_files],
        "spec_count": len(spec_files),
        "rtl_dir": str(rtl_dir),
        "rtl_count": len(rtl_files),
        "required_tools": required,
        "optional_tools": optional,
        "status": "failed" if missing_required else "ready",
    }

    log_file = logs_system_dir / f"bootstrap_{problem}.json"
    log_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[info] Bootstrap summary written to: {log_file}")

    if missing_required:
        print("[error] Environment bootstrap failed due to missing required tools.")
        return 1

    print("[ok] Environment bootstrap completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())