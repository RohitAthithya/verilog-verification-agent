#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Run iverilog/vvp for all RTL candidates.")
    p.add_argument("--problem", required=True)
    p.add_argument("--tb", required=True)
    p.add_argument("--root", default=".")
    p.add_argument("--tag", default="manual")
    return p.parse_args()


def load_preflight(root: Path, problem: str) -> dict:
    path = root / "logs" / "runs" / f"{problem}_preflight_context.json"
    if not path.exists():
        raise FileNotFoundError(f"Preflight context not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    problem = args.problem
    tb_path = (root / args.tb).resolve() if not Path(args.tb).is_absolute() else Path(args.tb)
    tag = args.tag

    print(f"[info] Running simulation for problem: {problem}")
    print(f"[info] Testbench: {tb_path}")

    preflight = load_preflight(root, problem)
    rtl_files = preflight.get("rtl_files", [])
    print(f"[info] RTL candidates found: {len(rtl_files)}")

    sim_dir = root / "outputs" / problem / "iterations" / tag / "simulation"
    build_dir = sim_dir / "build"
    logs_dir = sim_dir / "logs"
    summaries_dir = sim_dir / "summaries"

    build_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for item in rtl_files:
        rtl_path = Path(item["path"])
        candidate_name = rtl_path.stem

        out_file = build_dir / f"{candidate_name}.out"
        compile_cmd = ["iverilog", "-g2012", "-o", str(out_file), str(rtl_path), str(tb_path)]
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


if __name__ == "__main__":
    main()