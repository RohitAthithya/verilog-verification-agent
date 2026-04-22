from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


SUPPORTED_SPEC_SUFFIXES = {".md", ".txt", ".rst"}
SUPPORTED_RTL_SUFFIXES = {".v", ".sv"}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def resolve_problem_dir(root: Path, problem: str) -> Path:
    candidates = [
        root / "problems" / problem,
        root / problem,
    ]

    for candidate in candidates:
        if (candidate / "spec").is_dir() and (candidate / "rtl").is_dir():
            return candidate

    return candidates[0]


def discover_problem_context(root: Path, problem: str) -> dict:
    problem_dir = resolve_problem_dir(root, problem)
    spec_dir = problem_dir / "spec"
    rtl_dir = problem_dir / "rtl"

    spec_files = []
    if spec_dir.exists():
        for path in sorted(spec_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SPEC_SUFFIXES:
                continue

            content = _read_text(path)
            spec_files.append(
                {
                    "file_name": path.name,
                    "path": str(path),
                    "suffix": path.suffix.lower(),
                    "num_chars": len(content),
                }
            )

    rtl_files = []
    if rtl_dir.exists():
        for path in sorted(rtl_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_RTL_SUFFIXES:
                continue

            content = _read_text(path)
            rtl_files.append(
                {
                    "file_name": path.name,
                    "path": str(path),
                    "num_chars": len(content),
                }
            )

    combined_spec_output = root / "outputs" / problem / "reports" / "combined_spec_context.md"

    return {
        "problem": problem,
        "project_root": str(root),
        "problem_dir": str(problem_dir),
        "spec_dir": str(spec_dir),
        "rtl_dir": str(rtl_dir),
        "spec_files": spec_files,
        "rtl_files": rtl_files,
        "combined_spec_output": str(combined_spec_output) if combined_spec_output.exists() else "",
        "preflight_available": False,
        "context_source": "inferred",
    }


def load_problem_context(
    root: Path,
    problem: str,
    warn: Callable[[str], None] | None = None,
) -> tuple[dict, Path]:
    preflight_path = root / "logs" / "runs" / f"{problem}_preflight_context.json"

    if preflight_path.exists():
        try:
            data = _read_json(preflight_path)
            if isinstance(data, dict):
                data.setdefault("problem", problem)
                data.setdefault("preflight_available", True)
                data.setdefault("context_source", "preflight")
                return data, preflight_path

            if warn is not None:
                warn(
                    f"[warn] Preflight context at {preflight_path} is not a JSON object; "
                    "using inferred problem context instead."
                )
        except Exception as exc:
            if warn is not None:
                warn(
                    f"[warn] Failed to parse preflight context {preflight_path}: {exc}; "
                    "using inferred problem context instead."
                )
    elif warn is not None:
        warn(
            f"[warn] Preflight context not found: {preflight_path}; "
            "using inferred problem context instead."
        )

    return discover_problem_context(root, problem), preflight_path


def read_spec_text_from_context(context: dict) -> str:
    combined_spec_output = context.get("combined_spec_output", "")
    if combined_spec_output:
        combined_path = Path(combined_spec_output)
        if combined_path.exists():
            return combined_path.read_text(encoding="utf-8", errors="replace")

    parts = []
    for item in context.get("spec_files", []):
        path_text = item.get("path") if isinstance(item, dict) else str(item)
        if not path_text:
            continue

        path = Path(path_text)
        if path.exists():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))

    return "\n\n".join(parts)
