#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SUPPORTED_SPEC_SUFFIXES = {".md", ".txt", ".rst"}
SUPPORTED_RTL_SUFFIXES = {".v"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load one verification problem and prepare normalized inputs."
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


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def load_spec_bundle(spec_dir: Path) -> tuple[list[dict], str]:
    spec_files = sorted(
        [
            p for p in spec_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_SPEC_SUFFIXES
        ]
    )

    records = []
    combined_sections = []

    for path in spec_files:
        content = read_text_file(path)
        record = {
            "file_name": path.name,
            "path": str(path),
            "suffix": path.suffix.lower(),
            "num_chars": len(content),
            "content": content,
        }
        records.append(record)

        combined_sections.append(f"# BEGIN SPEC FILE: {path.name}")
        combined_sections.append(content if content else "[EMPTY FILE]")
        combined_sections.append(f"# END SPEC FILE: {path.name}")
        combined_sections.append("")

    combined_text = "\n".join(combined_sections).strip()
    return records, combined_text


def load_rtl_bundle(rtl_dir: Path) -> list[dict]:
    rtl_files = sorted(
        [
            p for p in rtl_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_RTL_SUFFIXES
        ]
    )

    records = []
    for path in rtl_files:
        content = read_text_file(path)
        records.append(
            {
                "file_name": path.name,
                "path": str(path),
                "num_chars": len(content),
                "content": content,
            }
        )
    return records


def main() -> int:
    args = parse_args()

    root = Path(args.root).resolve()
    problem = args.problem

    problem_dir = root / "problems" / problem
    spec_dir = problem_dir / "spec"
    rtl_dir = problem_dir / "rtl"

    soft_constraints_file = root / "soft_constraints" / "global_soft_constraints.md"
    memory_file = root / "memory" / "lessons" / "cumulative_lessons.md"

    outputs_problem_dir = root / "outputs" / problem
    iterations_dir = outputs_problem_dir / "iterations"
    final_dir = outputs_problem_dir / "final"
    reports_dir = outputs_problem_dir / "reports"

    logs_runs_dir = root / "logs" / "runs"

    if not problem_dir.exists():
        print(f"[error] Problem directory not found: {problem_dir}")
        return 1

    if not spec_dir.exists():
        print(f"[error] Spec directory not found: {spec_dir}")
        return 1

    if not rtl_dir.exists():
        print(f"[error] RTL directory not found: {rtl_dir}")
        return 1

    spec_records, combined_spec_text = load_spec_bundle(spec_dir)
    rtl_records = load_rtl_bundle(rtl_dir)

    if not spec_records:
        print(f"[error] No supported spec files found in: {spec_dir}")
        return 1

    if not rtl_records:
        print(f"[error] No RTL .v files found in: {rtl_dir}")
        return 1

    soft_constraints_text = ""
    if soft_constraints_file.exists():
        soft_constraints_text = read_text_file(soft_constraints_file)

    memory_text = ""
    if memory_file.exists():
        memory_text = read_text_file(memory_file)

    iterations_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    logs_runs_dir.mkdir(parents=True, exist_ok=True)

    preflight_context = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "problem": problem,
        "project_root": str(root),
        "problem_dir": str(problem_dir),
        "spec_dir": str(spec_dir),
        "rtl_dir": str(rtl_dir),
        "spec_files": [
            {
                "file_name": r["file_name"],
                "path": r["path"],
                "suffix": r["suffix"],
                "num_chars": r["num_chars"],
            }
            for r in spec_records
        ],
        "rtl_files": [
            {
                "file_name": r["file_name"],
                "path": r["path"],
                "num_chars": r["num_chars"],
            }
            for r in rtl_records
        ],
        "soft_constraints_file": str(soft_constraints_file),
        "soft_constraints_present": bool(soft_constraints_text),
        "memory_file": str(memory_file),
        "memory_present": bool(memory_text),
        "status": "loaded",
    }

    combined_spec_path = reports_dir / "combined_spec_context.md"
    combined_spec_path.write_text(combined_spec_text + "\n", encoding="utf-8")

    preflight_json_path = logs_runs_dir / f"{problem}_preflight_context.json"
    preflight_json_path.write_text(
        json.dumps(preflight_context, indent=2),
        encoding="utf-8",
    )

    print(f"[info] Loaded problem: {problem}")
    print(f"[info] Spec files loaded: {len(spec_records)}")
    for record in spec_records:
        print(f"[info]   - {record['file_name']} ({record['num_chars']} chars)")

    print(f"[info] RTL files loaded: {len(rtl_records)}")
    print(f"[info] Combined spec context written to: {combined_spec_path}")
    print(f"[info] Preflight context written to: {preflight_json_path}")

    print("[info] Problem inputs are ready for the next stage.")
    print("[info] Next stage will generate the first-pass testbench from this context.")

    return 0


if __name__ == "__main__":
    sys.exit(main())