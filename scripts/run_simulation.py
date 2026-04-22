#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SUPPORTED_RTL_SUFFIXES = {".v", ".sv"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run iverilog/vvp for all RTL candidates."
    )
    parser.add_argument("--problem", required=True)
    parser.add_argument(
        "--tb",
        default="",
        help="Generated testbench path. Defaults to outputs/<problem>/iterations/<tag>/generated_tb.v",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--tag", default="manual")
    return parser.parse_args()


def load_preflight(root: Path, problem: str) -> dict:
    path = root / "logs" / "runs" / f"{problem}_preflight_context.json"

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("problem", problem)
                data.setdefault("preflight_available", True)
                return data
            print(
                f"[warn] Preflight context at {path} is not a JSON object; "
                "falling back to inferred context."
            )
        except Exception as exc:
            print(
                f"[warn] Failed to parse preflight context {path}: {exc}; "
                "falling back to inferred context."
            )

    print(f"[warn] Preflight context not found: {path}, continuing with inferred context.")

    candidates = [
        root / "problems" / problem,
        root / problem,
    ]

    problem_dir = None
    for candidate in candidates:
        if candidate.exists():
            problem_dir = candidate
            break

    if problem_dir is None:
        problem_dir = root / "problems" / problem

    spec_dir = problem_dir / "spec"
    rtl_dir = problem_dir / "rtl"

    rtl_files = []
    if rtl_dir.exists():
        rtl_files = sorted(
            str(path)
            for path in rtl_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_RTL_SUFFIXES
        )

    return {
        "problem": problem,
        "preflight_available": False,
        "problem_dir": str(problem_dir),
        "spec_dir": str(spec_dir),
        "rtl_dir": str(rtl_dir),
        "rtl_files": rtl_files,
        "rtl_candidates": rtl_files,
    }


def resolve_tb_path(root: Path, problem: str, tag: str, tb_arg: str) -> Path:
    if tb_arg:
        tb_path = Path(tb_arg)
        return tb_path if tb_path.is_absolute() else (root / tb_path).resolve()

    return (
        root / "outputs" / problem / "iterations" / tag / "generated_tb.v"
    ).resolve()


def extract_rtl_paths(preflight: dict) -> list[Path]:
    rtl_items = preflight.get("rtl_files") or preflight.get("rtl_candidates") or []
    rtl_paths: list[Path] = []

    for item in rtl_items:
        if isinstance(item, dict):
            path_text = item.get("path", "")
        else:
            path_text = str(item)

        if not path_text:
            continue

        path = Path(path_text)
        if path.suffix.lower() not in SUPPORTED_RTL_SUFFIXES:
            continue

        rtl_paths.append(path)

    return rtl_paths


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    problem = args.problem
    tag = args.tag
    tb_path = resolve_tb_path(root, problem, tag, args.tb)

    if not tb_path.exists():
        print(f"[error] Testbench not found: {tb_path}")
        return 1

    print(f"[info] Running simulation for problem: {problem}")
    print(f"[info] Testbench: {tb_path}")

    preflight = load_preflight(root, problem)
    rtl_files = extract_rtl_paths(preflight)

    if not rtl_files:
        print(f"[error] No RTL candidates found for {problem}")
        return 1

    print(f"[info] RTL candidates found: {len(rtl_files)}")

    sim_dir = root / "outputs" / problem / "iterations" / tag / "simulation"
    build_dir = sim_dir / "build"
    logs_dir = sim_dir / "logs"
    summaries_dir = sim_dir / "summaries"

    build_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for rtl_path in rtl_files:
        candidate_name = rtl_path.stem
        out_file = build_dir / f"{candidate_name}.out"
        compile_cmd = [
            "iverilog",
            "-g2012",
            "-o",
            str(out_file),
            str(rtl_path),
            str(tb_path),
        ]
        run_cmd = ["vvp", str(out_file)]

        compile_proc = subprocess.run(compile_cmd, capture_output=True, text=True)
        compile_rc = compile_proc.returncode
        compile_stdout = compile_proc.stdout or ""
        compile_stderr = compile_proc.stderr or ""

        run_rc = None
        run_stdout = ""
        run_stderr = ""

        if compile_rc != 0:
            status = "compile_error"
        else:
            run_proc = subprocess.run(run_cmd, capture_output=True, text=True)
            run_rc = run_proc.returncode
            run_stdout = run_proc.stdout or ""
            run_stderr = run_proc.stderr or ""

            combined_output = f"{run_stdout}\n{run_stderr}"

            if run_rc != 0:
                status = "run_error"
            elif "TB_FAIL" in combined_output:
                status = "fail"
            elif "TB_PASS" in combined_output:
                status = "pass"
            else:
                status = "unknown"

        log_payload = {
            "candidate": candidate_name,
            "rtl_file": str(rtl_path),
            "compile_cmd": compile_cmd,
            "run_cmd": run_cmd if compile_rc == 0 else None,
            "compile_rc": compile_rc,
            "compile_stdout": compile_stdout,
            "compile_stderr": compile_stderr,
            "run_rc": run_rc,
            "run_stdout": run_stdout,
            "run_stderr": run_stderr,
            "status": status,
        }

        (logs_dir / f"{candidate_name}.json").write_text(
            json.dumps(log_payload, indent=2),
            encoding="utf-8",
        )

        results.append(log_payload)

        print(
            f"[info] {candidate_name}: compile_rc={compile_rc} "
            f"run_rc={run_rc if run_rc is not None else 'NA'} status={status}"
        )

    summary = {
        "problem": problem,
        "tb_path": str(tb_path),
        "tag": tag,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_candidates": len(results),
        "results": results,
    }

    summary_path = summaries_dir / "simulation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[info] Simulation summary written to: {summary_path}")
    print("[info] Simulation stage completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
