#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple


def run_cmd(
    cmd: List[str],
    cwd: Optional[Path] = None,
    stdin_text: Optional[str] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    print(f"[run] {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        input=stdin_text,
        text=True,
        capture_output=True,
    )
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n", file=sys.stderr)
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc


def resolve_problem_dir(root: Path, problem: str) -> Path:
    candidates = [
        root / problem,
        root / "problems" / problem,
    ]
    for cand in candidates:
        if (cand / "spec").is_dir() and (cand / "rtl").is_dir():
            return cand
    raise FileNotFoundError(
        f"Could not find problem directory for {problem}. Expected either "
        f"{root / problem} or {root / 'problems' / problem} with spec/ and rtl/."
    )


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def safe_read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    try:
        return read_text(path)
    except Exception:
        return default


def collect_spec_text(spec_dir: Path) -> str:
    files = sorted([p for p in spec_dir.rglob("*") if p.is_file()])
    if not files:
        raise FileNotFoundError(f"No spec files found under {spec_dir}")
    parts = []
    for p in files:
        parts.append(f"===== SPEC FILE: {p.relative_to(spec_dir)} =====\n{read_text(p)}")
    return "\n\n".join(parts)


def list_rtl_files(rtl_dir: Path) -> List[Path]:
    files = sorted([p for p in rtl_dir.iterdir() if p.is_file() and p.suffix in {'.v', '.sv'}])
    if not files:
        raise FileNotFoundError(f"No RTL files found under {rtl_dir}")
    return files


def read_soft_constraints(root: Path) -> str:
    path = root / "soft_constraints" / "global_soft_constraints.md"
    return safe_read_text(path, default="")


def next_iteration_dir(root: Path, problem: str) -> Tuple[int, Path]:
    base = root / "outputs" / problem / "iterations"
    base.mkdir(parents=True, exist_ok=True)
    nums = []
    for p in base.iterdir():
        if p.is_dir():
            m = re.fullmatch(r"iter_(\d+)", p.name)
            if m:
                nums.append(int(m.group(1)))
    idx = (max(nums) + 1) if nums else 1
    tag = f"iter_{idx:02d}"
    iter_dir = base / tag
    iter_dir.mkdir(parents=True, exist_ok=True)
    return idx, iter_dir


def latest_iteration_dir(root: Path, problem: str) -> Optional[Path]:
    base = root / "outputs" / problem / "iterations"
    if not base.exists():
        return None

    usable = []
    for p in base.iterdir():
        if not p.is_dir():
            continue
        m = re.fullmatch(r"iter_(\d+)", p.name)
        if not m:
            continue
        tb_path = p / "generated_tb.v"
        if tb_path.exists() and tb_path.stat().st_size > 0:
            usable.append((int(m.group(1)), p))

    if not usable:
        return None
    return sorted(usable)[-1][1]


def default_status() -> dict:
    return {
        "counts": {"pass": 0, "fail": 0, "compile_error": 0, "run_error": 0, "unknown": 0},
        "total": 0,
        "golden": False,
        "raw": {},
    }


def build_initial_prompt(
    root: Path,
    problem_dir: Path,
    problem: str,
    spec_text: str,
    rtl_files: List[Path],
    soft_constraints: str,
    target_tb: Path,
) -> str:
    rel = lambda p: p.relative_to(root)
    rtl_listing = "\n".join(f"- {rel(p)}" for p in rtl_files)
    soft_text = soft_constraints.strip() or "(empty)"
    return f"""
Follow AGENTS.md exactly.

Task: generate a complete self-checking Verilog/SystemVerilog testbench for {problem}.

Project root: {root}
Problem directory: {problem_dir}
Spec directory: {problem_dir / 'spec'}
RTL directory: {problem_dir / 'rtl'}
Soft constraints file: {root / 'soft_constraints' / 'global_soft_constraints.md'}
Target output testbench path: {target_tb}

Requirements:
- Read everything under spec/ as problem specification.
- Inspect all RTL files under rtl/.
- Preserve compatibility with iverilog using -g2012.
- Emit TB_PASS and TB_FAIL markers clearly in stdout.
- Write the full generated testbench ONLY to: {target_tb}
- Do not put the testbench in any other location.
- If helper notes are needed, keep them inside the same iteration directory.
- Do not change simulation harness scripts in this first generation step.
- If soft constraints are empty or missing, proceed without them.

Specification content:
{spec_text}

RTL files:
{rtl_listing}

Soft constraints:
{soft_text}
""".strip() + "\n"


def build_refinement_prompt(
    root: Path,
    problem_dir: Path,
    problem: str,
    spec_text: str,
    rtl_files: List[Path],
    soft_constraints: str,
    prev_tb: Path,
    summary_path: Path,
    collected_path: Path,
    target_tb: Path,
) -> str:
    rel = lambda p: p.relative_to(root)
    rtl_listing = "\n".join(f"- {rel(p)}" for p in rtl_files)
    summary_text = safe_read_text(summary_path, default="{}") or "{}"
    collected_text = safe_read_text(collected_path, default="{}") or "{}"
    prev_tb_text = safe_read_text(prev_tb, default="")
    soft_text = soft_constraints.strip() or "(empty)"
    return f"""
Follow AGENTS.md exactly.

Task: refine the previously generated testbench for {problem} based on simulation feedback.

Project root: {root}
Problem directory: {problem_dir}
Spec directory: {problem_dir / 'spec'}
RTL directory: {problem_dir / 'rtl'}
Previous testbench path: {prev_tb}
Simulation summary path: {summary_path}
Collected results path: {collected_path}
Target output testbench path: {target_tb}

Requirements:
- Read the spec and all RTL candidates again.
- Read the previous testbench and any available simulation outputs.
- If summary or collected results are missing or empty, proceed with whatever feedback is available.
- Use the simulation feedback to produce a stronger next testbench.
- Preserve compatibility with iverilog using -g2012.
- Preserve TB_PASS and TB_FAIL markers.
- Write the full next-version testbench ONLY to: {target_tb}
- Do not overwrite the previous iteration's testbench.
- Focus on improving the testbench, not rewriting unrelated infrastructure.
- If soft constraints are empty or missing, proceed without them.

Specification content:
{spec_text}

RTL files:
{rtl_listing}

Soft constraints:
{soft_text}

Previous testbench:
```verilog
{prev_tb_text}
```

Simulation summary JSON:
```json
{summary_text}
```

Collected results JSON:
```json
{collected_text}
```
""".strip() + "\n"


def write_prompt(iter_dir: Path, prompt: str) -> Path:
    path = iter_dir / "codex_prompt.txt"
    path.write_text(prompt, encoding="utf-8")
    return path


def run_codex(root: Path, iter_dir: Path, prompt: str) -> Path:
    codex_dir = iter_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    final_msg = codex_dir / "final_message.txt"
    events = codex_dir / "events.jsonl"
    prompt_path = write_prompt(iter_dir, prompt)

    proc = run_cmd(
        [
            "codex",
            "exec",
            "-C",
            str(root),
            "--full-auto",
            "--json",
            "-o",
            str(final_msg),
            "-",
        ],
        cwd=root,
        stdin_text=prompt,
        check=True,
    )

    events.write_text(proc.stdout, encoding="utf-8")
    print(f"[info] Codex prompt written to: {prompt_path}")
    print(f"[info] Codex final message written to: {final_msg}")
    print(f"[info] Codex event log written to: {events}")
    return final_msg


def run_simulation_pipeline(root: Path, problem: str, tag: str, tb_path: Path) -> Path:
    run_cmd(
        [
            "python3", "scripts/run_simulation.py",
            "--problem", problem,
            "--tb", str(tb_path),
            "--root", str(root),
            "--tag", tag,
        ],
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
    return root / "outputs" / problem / "iterations" / tag / "simulation" / "summaries" / "simulation_summary.json"


def read_summary_status(summary_path: Path) -> dict:
    if not summary_path.exists():
        return default_status()

    try:
        data = json.loads(read_text(summary_path))
    except Exception:
        return default_status()

    results = data.get("results", [])
    counts = {"pass": 0, "fail": 0, "compile_error": 0, "run_error": 0, "unknown": 0}

    for r in results:
        status = r.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1

    total = len(results)
    golden = (
        total > 0 and
        counts.get("pass", 0) == 1 and
        counts.get("fail", 0) == total - 1 and
        counts.get("compile_error", 0) == 0 and
        counts.get("run_error", 0) == 0 and
        counts.get("unknown", 0) == 0
    )
    return {"counts": counts, "total": total, "golden": golden, "raw": data}


def write_iteration_metadata(
    iter_dir: Path,
    problem: str,
    tb_path: Path,
    prompt_path: Path,
    source_iter: Optional[Path],
    summary: Optional[dict] = None,
) -> None:
    meta = {
        "problem": problem,
        "generated_tb": str(tb_path),
        "prompt_file": str(prompt_path),
        "source_iteration": str(source_iter) if source_iter else None,
    }
    if summary is not None:
        meta["summary"] = summary
    (iter_dir / "iteration_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Automated Codex-driven verifier loop")
    ap.add_argument("--problem", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--max-iters", type=int, default=5)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    problem = args.problem
    problem_dir = resolve_problem_dir(root, problem)
    spec_dir = problem_dir / "spec"
    rtl_dir = problem_dir / "rtl"
    spec_text = collect_spec_text(spec_dir)
    rtl_files = list_rtl_files(rtl_dir)
    soft_constraints = read_soft_constraints(root)

    prev_iter = latest_iteration_dir(root, problem)

    for _ in range(args.max_iters):
        idx, iter_dir = next_iteration_dir(root, problem)
        tag = f"iter_{idx:02d}"
        tb_path = iter_dir / "generated_tb.v"

        print(f"\n[info] Starting {tag}")
        print(f"[info] Problem dir: {problem_dir}")
        print(f"[info] Spec dir: {spec_dir}")
        print(f"[info] RTL dir: {rtl_dir}")
        print(f"[info] Target testbench: {tb_path}")

        if prev_iter is None:
            prompt = build_initial_prompt(
                root,
                problem_dir,
                problem,
                spec_text,
                rtl_files,
                soft_constraints,
                tb_path,
            )
        else:
            prev_tb = prev_iter / "generated_tb.v"
            summary_path = prev_iter / "simulation" / "summaries" / "simulation_summary.json"
            collected_path = prev_iter / "analysis" / "collected_results.json"
            prompt = build_refinement_prompt(
                root,
                problem_dir,
                problem,
                spec_text,
                rtl_files,
                soft_constraints,
                prev_tb,
                summary_path,
                collected_path,
                tb_path,
            )

        prompt_path = write_prompt(iter_dir, prompt)
        run_codex(root, iter_dir, prompt)

        if not tb_path.exists() or tb_path.stat().st_size == 0:
            raise FileNotFoundError(
                f"Codex did not create the expected testbench at {tb_path}. "
                f"Check codex/final_message.txt and codex/events.jsonl"
            )

        summary_path = run_simulation_pipeline(root, problem, tag, tb_path)
        status = read_summary_status(summary_path)
        write_iteration_metadata(iter_dir, problem, tb_path, prompt_path, prev_iter, status)

        print(f"[info] {tag} counts: {status['counts']}")
        print(f"[info] Golden found: {status['golden']}")

        if status["golden"]:
            final_dir = root / "outputs" / problem / "final"
            final_dir.mkdir(parents=True, exist_ok=True)
            final_tb = final_dir / "golden_tb.v"
            final_tb.write_text(read_text(tb_path), encoding="utf-8")
            print(f"[success] Golden testbench written to: {final_tb}")
            return

        prev_iter = iter_dir

    print("[done] Reached max iterations without finding a golden testbench.")


if __name__ == "__main__":
    main()