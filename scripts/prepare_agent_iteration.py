#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Prepare agent iteration packet from current run artifacts.")
    p.add_argument("--problem", required=True)
    p.add_argument("--root", default=".")
    p.add_argument("--tag", default="manual")
    return p.parse_args()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def safe_read_text(path: Path) -> str:
    return read_text(path) if path.exists() else ""


def summarize_results(sim_summary: dict) -> dict:
    results = sim_summary.get("results", [])
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
    return counts


def collect_examples(sim_summary: dict, limit: int = 5) -> dict:
    results = sim_summary.get("results", [])
    buckets = {
        "pass": [],
        "fail": [],
        "compile_error": [],
        "run_error": [],
        "unknown": [],
    }

    for r in results:
        status = r.get("status", "unknown")
        if status not in buckets:
            buckets[status] = []
        if len(buckets[status]) < limit:
            buckets[status].append(
                {
                    "candidate": r.get("candidate"),
                    "status": status,
                    "run_stdout_excerpt": (r.get("run_stdout") or "")[:500],
                    "compile_stderr_excerpt": (r.get("compile_stderr") or "")[:500],
                    "run_stderr_excerpt": (r.get("run_stderr") or "")[:500],
                }
            )
    return buckets


def make_diagnosis(counts: dict) -> str:
    p = counts.get("pass", 0)
    f = counts.get("fail", 0)
    c = counts.get("compile_error", 0)
    r = counts.get("run_error", 0)
    u = counts.get("unknown", 0)

    if p > 0 and f > 0:
        return "The current testbench is discriminating between candidates. Improve precision and try to isolate the correct RTL."
    if f > 0 and p == 0:
        return "The current testbench is over-constrained or behaviorally incorrect. It rejects all candidates and should be relaxed or corrected."
    if p > 0 and f == 0 and u == 0:
        return "The current testbench is too weak. It allows all candidates to pass and needs stronger checks."
    if u > 0:
        return "The harness executed, but the testbench did not emit reliable TB_PASS/TB_FAIL markers for some runs."
    if c > 0 or r > 0:
        return "The current iteration still has infrastructure or execution issues. Fix compile/runtime problems before improving test quality."
    return "The current iteration needs further analysis."


def build_prompt_packet(problem: str, tag: str, spec_text: str, tb_text: str, counts: dict, examples: dict, diagnosis: str) -> dict:
    return {
        "problem": problem,
        "tag": tag,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "task": "Regenerate a better Verilog testbench using the spec, previous testbench, and simulation feedback.",
        "objective": (
            "Generate a complete Verilog/SystemVerilog testbench that passes the correct RTL implementation "
            "and fails the incorrect RTL implementations."
        ),
        "current_status": counts,
        "diagnosis": diagnosis,
        "instructions": [
            "Read the natural-language specification carefully.",
            "Use the previous generated testbench as a baseline, not as ground truth.",
            "Use the simulation failures to identify likely wrong assumptions.",
            "Preserve compilability with iverilog (-g2012).",
            "Emit TB_PASS when the DUT behavior matches the expected model and TB_FAIL when it does not.",
            "Prefer directed stimulus and explicit checks over weak smoke tests.",
            "Do not remove verdict markers."
        ],
        "spec_text": spec_text,
        "previous_testbench": tb_text,
        "example_results": examples,
    }


def build_prompt_markdown(packet: dict) -> str:
    counts = packet["current_status"]
    lines = [
        f"# Agent Iteration Packet: {packet['problem']}",
        "",
        f"Tag: `{packet['tag']}`",
        f"Timestamp (UTC): `{packet['timestamp_utc']}`",
        "",
        "## Objective",
        "",
        packet["objective"],
        "",
        "## Current Status",
        "",
        f"- Pass: {counts.get('pass', 0)}",
        f"- Fail: {counts.get('fail', 0)}",
        f"- Compile errors: {counts.get('compile_error', 0)}",
        f"- Run errors: {counts.get('run_error', 0)}",
        f"- Unknown: {counts.get('unknown', 0)}",
        "",
        "## Diagnosis",
        "",
        packet["diagnosis"],
        "",
        "## Instructions",
        "",
    ]
    for item in packet["instructions"]:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## Spec Text",
        "",
        "```text",
        packet["spec_text"],
        "```",
        "",
        "## Previous Testbench",
        "",
        "```verilog",
        packet["previous_testbench"],
        "```",
        "",
        "## Example Results",
        "",
        "```json",
        json.dumps(packet["example_results"], indent=2),
        "```",
        "",
    ])
    return "\n".join(lines)


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    problem = args.problem
    tag = args.tag

    preflight_path = root / "logs" / "runs" / f"{problem}_preflight_context.json"
    iter_dir = root / "outputs" / problem / "iterations" / tag
    tb_path = iter_dir / "generated_tb.v"
    sim_summary_path = iter_dir / "simulation" / "summaries" / "simulation_summary.json"
    collected_path = iter_dir / "analysis" / "collected_results.json"

    if not preflight_path.exists():
        raise FileNotFoundError(f"Missing preflight context: {preflight_path}")
    if not sim_summary_path.exists():
        raise FileNotFoundError(f"Missing simulation summary: {sim_summary_path}")

    preflight = read_json(preflight_path)
    sim_summary = read_json(sim_summary_path)
    collected = read_json(collected_path) if collected_path.exists() else {}

    combined_spec_output = preflight.get("combined_spec_output")
    spec_text = ""
    if combined_spec_output and Path(combined_spec_output).exists():
        spec_text = read_text(Path(combined_spec_output))
    else:
        parts = []
        for item in preflight.get("spec_files", []):
            p = Path(item["path"])
            if p.exists():
                parts.append(read_text(p))
        spec_text = "\n\n".join(parts)

    tb_text = safe_read_text(tb_path)
    counts = summarize_results(sim_summary)
    examples = collect_examples(sim_summary, limit=5)
    diagnosis = make_diagnosis(counts)

    packet = build_prompt_packet(
        problem=problem,
        tag=tag,
        spec_text=spec_text,
        tb_text=tb_text,
        counts=counts,
        examples=examples,
        diagnosis=diagnosis,
    )

    agent_dir = iter_dir / "agent_input"
    agent_dir.mkdir(parents=True, exist_ok=True)

    packet_json = agent_dir / "iteration_packet.json"
    packet_md = agent_dir / "iteration_packet.md"
    handoff_txt = agent_dir / "agent_handoff_prompt.txt"

    packet_json.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    packet_md.write_text(build_prompt_markdown(packet), encoding="utf-8")

    handoff_prompt = "\n".join([
        f"Problem: {problem}",
        f"Tag: {tag}",
        "",
        "Task:",
        "Regenerate the Verilog/SystemVerilog testbench for this problem.",
        "",
        "Requirements:",
        "- Read iteration_packet.json or iteration_packet.md.",
        "- Use the spec text and previous testbench as inputs.",
        "- Use example failing outputs to identify wrong assumptions.",
        "- Preserve TB_PASS and TB_FAIL markers.",
        "- Produce a complete compilable testbench for iverilog -g2012.",
        "",
        f"Primary packet: {packet_json}",
        f"Readable packet: {packet_md}",
    ])
    handoff_txt.write_text(handoff_prompt, encoding="utf-8")

    print(f"[info] Preflight context: {preflight_path}")
    print(f"[info] Simulation summary: {sim_summary_path}")
    print(f"[info] Collected results: {collected_path if collected_path.exists() else 'not found'}")
    print(f"[info] Agent packet JSON written to: {packet_json}")
    print(f"[info] Agent packet Markdown written to: {packet_md}")
    print(f"[info] Agent handoff prompt written to: {handoff_txt}")
    print(f"[info] Diagnosis: {diagnosis}")


if __name__ == "__main__":
    main()