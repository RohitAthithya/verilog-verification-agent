#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def run_cmd(cmd, cwd=None, allow_fail=False):
    print(f"[run] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=cwd)
    if not allow_fail and proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc.returncode


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def clone_iteration_from_manual(root: Path, problem: str, tag: str):
    manual_dir = root / "outputs" / problem / "iterations" / "manual"
    target_dir = root / "outputs" / problem / "iterations" / tag
    ensure_dir(target_dir)

    if not manual_dir.exists():
        return target_dir

    generated_tb = manual_dir / "generated_tb.v"
    if generated_tb.exists():
        shutil.copy2(generated_tb, target_dir / "generated_tb.v")

    return target_dir


def summarize_statuses(summary_path: Path):
    if not summary_path.exists():
        return None

    data = read_json(summary_path)
    results = data.get("results", [])

    counts = {
        "pass": 0,
        "fail": 0,
        "compile_error": 0,
        "run_error": 0,
        "unknown": 0,
    }

    for r in results:
        status = r.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1

    total = len(results)
    pass_count = counts.get("pass", 0)
    fail_count = counts.get("fail", 0)

    is_golden = (
        total > 0 and
        pass_count == 1 and
        fail_count == total - 1 and
        counts.get("compile_error", 0) == 0 and
        counts.get("run_error", 0) == 0 and
        counts.get("unknown", 0) == 0
    )

    return {
        "total": total,
        "counts": counts,
        "is_golden": is_golden,
    }


def write_iteration_note(root: Path, problem: str, tag: str, note: str):
    out = root / "outputs" / problem / "iterations" / tag / "iteration_note.txt"
    out.write_text(note, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Run iterative Codex -> simulation -> analysis loop until golden TB or max iterations.")
    ap.add_argument("--problem", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--max-iters", type=int, default=3)
    ap.add_argument("--start-index", type=int, default=1)
    ap.add_argument("--seed-from-manual", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    problem = args.problem

    print(f"[info] Root: {root}")
    print(f"[info] Problem: {problem}")
    print(f"[info] Max iterations: {args.max_iters}")

    for idx in range(args.start_index, args.start_index + args.max_iters):
        tag = f"iter_{idx:02d}"
        print("\n" + "=" * 72)
        print(f"[info] Starting iteration: {tag}")
        print("=" * 72)

        if args.seed_from_manual:
            clone_iteration_from_manual(root, problem, tag)

        run_cmd(
            ["python3", "scripts/prepare_agent_iteration.py", "--problem", problem, "--root", str(root), "--tag", tag],
            cwd=root,
        )

        run_cmd(
            ["bash", "scripts/run_codex_refinement.sh", problem, tag, str(root)],
            cwd=root,
        )

        run_cmd(
            ["python3", "scripts/run_simulation.py", "--problem", problem, "--root", str(root), "--tag", tag],
            cwd=root,
        )

        run_cmd(
            ["python3", "scripts/collect_results.py", "--problem", problem, "--root", str(root), "--tag", tag],
            cwd=root,
        )

        run_cmd(
            ["python3", "scripts/summarize_iteration.py", "--problem", problem, "--root", str(root), "--tag", tag],
            cwd=root,
        )

        summary_path = root / "outputs" / problem / "iterations" / tag / "simulation" / "summaries" / "simulation_summary.json"
        summary = summarize_statuses(summary_path)

        if summary is None:
            write_iteration_note(
                root, problem, tag,
                "Iteration completed, but simulation_summary.json was not found."
            )
            print(f"[warn] Missing summary file for {tag}: {summary_path}")
            continue

        counts = summary["counts"]
        note = (
            f"Iteration {tag}\n"
            f"Total candidates: {summary['total']}\n"
            f"Pass: {counts['pass']}\n"
            f"Fail: {counts['fail']}\n"
            f"Compile errors: {counts['compile_error']}\n"
            f"Run errors: {counts['run_error']}\n"
            f"Unknown: {counts['unknown']}\n"
            f"Golden: {summary['is_golden']}\n"
        )
        write_iteration_note(root, problem, tag, note)

        print(f"[info] Result counts for {tag}: {counts}")
        print(f"[info] Golden discriminator found: {summary['is_golden']}")

        if summary["is_golden"]:
            final_dir = root / "outputs" / problem / "final"
            ensure_dir(final_dir)

            tb_src = root / "outputs" / problem / "iterations" / tag / "generated_tb.v"
            tb_dst = final_dir / "golden_tb.v"
            if tb_src.exists():
                shutil.copy2(tb_src, tb_dst)
                print(f"[success] Copied golden testbench to: {tb_dst}")
            else:
                print(f"[warn] Golden iteration found but generated_tb.v missing at: {tb_src}")

            print(f"[success] Stopping after {tag}")
            return

    print("[done] Reached max iterations without a golden discriminator.")


if __name__ == "__main__":
    main()