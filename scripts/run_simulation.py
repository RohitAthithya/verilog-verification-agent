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


def load_preflight(root: Path, problem: str):
    path = root / "logs" / "runs" / f"{problem}_preflight_context.json"

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("problem", problem)
                data.setdefault("preflight_available", True)
                return data
            print(f"[warn] Preflight context at {path} is not a JSON object; falling back to inferred context.")
        except Exception as e:
            print(f"[warn] Failed to parse preflight context {path}: {e}; falling back to inferred context.")

    print(f"Preflight context not found: {path}, continuing with inferred context.")

    candidates = [
        root / "problems" / problem,
        root / problem,
    ]

    problem_dir = None
    for cand in candidates:
        if cand.exists():
            problem_dir = cand
            break

    if problem_dir is None:
        problem_dir = root / "problems" / problem

    spec_dir = problem_dir / "spec"
    rtl_dir = problem_dir / "rtl"

    rtl_files = []
    if rtl_dir.exists():
        rtl_files = sorted(
            str(p) for p in rtl_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".v", ".sv"}
        )

    inferred = {
        "problem": problem,
        "preflight_available": False,
        "problem_dir": str(problem_dir),
        "spec_dir": str(spec_dir),
        "rtl_dir": str(rtl_dir),
        "rtl_files": rtl_files,
        "rtl_candidates": rtl_files,
    }

    return inferred

    main()