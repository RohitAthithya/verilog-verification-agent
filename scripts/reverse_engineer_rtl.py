#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from problem_context import load_problem_context, read_spec_text_from_context
from rtl_utils import (
    Port,
    count_regex,
    extract_ports,
    format_decl,
    instantiate_ports,
    is_active_low_name,
    is_clock_name,
    is_reset_name,
    module_name_from_text,
    port_names_csv,
    reg_decl,
    strip_comments,
    width_to_bits,
    wire_decl,
)

TASK_RE = re.compile(r"task(?:\s+automatic)?\s+(\w+)\s*;(.*?)endtask", re.S)
TASK_INPUT_RE = re.compile(
    r"\binput\b(?:\s+(?:reg|wire|logic|signed|unsigned|integer))*\s*"
    r"(?:\[[^]]+\]\s*)?(\w+)\s*;",
    re.M,
)
TASK_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_$]*)\s*\((.*?)\)\s*;", re.S)
FOR_LOOP_RE = re.compile(
    r"\bfor\s*\(\s*([A-Za-z_][A-Za-z0-9_$]*)\s*=\s*([^;]+?)\s*;"
    r"\s*\1\s*(<=|<)\s*([^;]+?)\s*;"
)
SPEC_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reverse engineer an RTL candidate from spec + golden TB, validate it "
            "against the golden TB, compare it to the winning mutant, and emit a "
            "comparative study."
        )
    )
    parser.add_argument("--problem", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--winner-tag",
        default="",
        help="Solved iteration tag to use when locating the winning mutant. Defaults to latest solved iteration.",
    )
    parser.add_argument(
        "--max-refine-iters",
        type=int,
        default=3,
        help="Maximum reverse-engineering generation/refinement attempts.",
    )
    parser.add_argument(
        "--existing-reverse-rtl",
        default="",
        help="Optional existing RTL to seed or test the reverse-engineering flow without Codex generation.",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path) -> dict:
    return json.loads(read_text(path))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text_block(text: str, max_chars: int = 6000) -> str:
    compact = text.strip()
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "\n...[truncated]"


def shorten_output(text: str, max_lines: int = 12, max_chars: int = 2000) -> str:
    trimmed = normalize_text_block(text, max_chars=max_chars)
    lines = trimmed.splitlines()
    if len(lines) <= max_lines:
        return trimmed
    return "\n".join(lines[:max_lines]) + "\n...[truncated]"


def strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip() + "\n"
    return text


def parse_verilog_int(token: str) -> int | None:
    cleaned = token.strip().replace("_", "")
    if not cleaned:
        return None

    plain_match = re.fullmatch(r"-?\d+", cleaned)
    if plain_match:
        return int(cleaned, 10)

    based_match = re.fullmatch(
        r"(?:(\d+))?'([sS])?([dDhHbBoO])([0-9a-fA-FxXzZ+-]+)",
        cleaned,
    )
    if not based_match:
        return None

    _, _, base_char, digits = based_match.groups()
    if any(ch in digits.lower() for ch in {"x", "z"}):
        return None

    base_map = {
        "d": 10,
        "h": 16,
        "b": 2,
        "o": 8,
    }
    return int(digits, base_map[base_char.lower()])


def split_call_args(arg_blob: str) -> list[str]:
    args: list[str] = []
    current: list[str] = []
    depth = 0

    for char in arg_blob:
        if char == "," and depth == 0:
            piece = "".join(current).strip()
            if piece:
                args.append(piece)
            current = []
            continue

        current.append(char)
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)

    tail = "".join(current).strip()
    if tail:
        args.append(tail)
    return args


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def name_tokens(name: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", name.lower()) if token]


def resolve_expr_range(expr: str, loop_ranges: dict[str, tuple[int, int]]) -> tuple[int, int] | None:
    compact = expr.strip()
    if not compact:
        return None

    value = parse_verilog_int(compact)
    if value is not None:
        return value, value

    slice_stripped = re.sub(r"\[[^]]+]", "", compact).strip()
    if slice_stripped in loop_ranges:
        return loop_ranges[slice_stripped]

    return None


def update_domain(
    domains: dict[str, dict],
    port_name: str,
    low: int,
    high: int,
    source: str,
) -> None:
    entry = domains.setdefault(
        port_name,
        {
            "ranges": [],
            "values": set(),
            "sources": set(),
        },
    )
    entry["sources"].add(source)
    if low == high:
        entry["values"].add(low)
    else:
        entry["ranges"].append((min(low, high), max(low, high)))


def finalize_domain_entry(entry: dict) -> dict | None:
    ranges = list(entry.get("ranges", []))
    values = sorted(entry.get("values", set()))
    sources = sorted(entry.get("sources", set()))

    if ranges:
        mins = [low for low, _ in ranges]
        maxs = [high for _, high in ranges]
        if values:
            mins.append(min(values))
            maxs.append(max(values))
        return {
            "kind": "range",
            "min": min(mins),
            "max": max(maxs),
            "values": values,
            "source": ", ".join(sources),
        }

    if values:
        if len(values) == 1:
            return {
                "kind": "constant",
                "value": values[0],
                "values": values,
                "source": ", ".join(sources),
            }
        return {
            "kind": "enum",
            "values": values,
            "source": ", ".join(sources),
        }

    return None


def infer_loop_ranges(text: str) -> dict[str, tuple[int, int]]:
    loop_ranges: dict[str, tuple[int, int]] = {}
    cleaned = strip_comments(text)

    for match in FOR_LOOP_RE.finditer(cleaned):
        variable, start_expr, operator, end_expr = match.groups()
        start = parse_verilog_int(start_expr)
        end = parse_verilog_int(end_expr)
        if start is None or end is None:
            continue
        if operator == "<":
            end -= 1
        loop_ranges[variable] = (min(start, end), max(start, end))

    return loop_ranges


def infer_domains_from_golden_tb(golden_tb_text: str, ports: list[Port]) -> dict[str, dict]:
    cleaned = strip_comments(golden_tb_text)
    port_names = {port.name for port in ports if port.direction == "input"}
    domains: dict[str, dict] = {}
    loop_ranges = infer_loop_ranges(cleaned)

    assign_re = re.compile(
        r"\b(" + "|".join(re.escape(name) for name in sorted(port_names, key=len, reverse=True)) + r")\b"
        r"\s*=\s*([^;]+);"
    ) if port_names else None

    if assign_re is not None:
        for match in assign_re.finditer(cleaned):
            port_name, expr = match.groups()
            resolved = resolve_expr_range(expr, loop_ranges)
            if resolved is None:
                continue
            update_domain(domains, port_name, resolved[0], resolved[1], "golden_tb_assignment")

    tasks: dict[str, dict] = {}
    for task_match in TASK_RE.finditer(cleaned):
        task_name, task_body = task_match.groups()
        params = TASK_INPUT_RE.findall(task_body)
        param_index = {name: idx for idx, name in enumerate(params)}
        mappings: list[tuple[str, int]] = []

        if assign_re is not None:
            for assign_match in assign_re.finditer(task_body):
                port_name, expr = assign_match.groups()
                expr_name = re.sub(r"\[[^]]+]", "", expr).strip()
                if expr_name in param_index:
                    mappings.append((port_name, param_index[expr_name]))

        if mappings:
            tasks[task_name] = {
                "params": params,
                "mappings": mappings,
            }

    for call_match in TASK_CALL_RE.finditer(cleaned):
        task_name, arg_blob = call_match.groups()
        task_info = tasks.get(task_name)
        if task_info is None:
            continue

        args = split_call_args(arg_blob)
        for port_name, arg_index in task_info["mappings"]:
            if arg_index >= len(args):
                continue
            resolved = resolve_expr_range(args[arg_index], loop_ranges)
            if resolved is None:
                continue
            update_domain(domains, port_name, resolved[0], resolved[1], "golden_tb_task_call")

    finalized: dict[str, dict] = {}
    for port_name, entry in domains.items():
        final_entry = finalize_domain_entry(entry)
        if final_entry is not None:
            finalized[port_name] = final_entry
    return finalized


def infer_domains_from_spec(spec_text: str, ports: list[Port]) -> dict[str, dict]:
    domains: dict[str, dict] = {}
    sentences = [piece.strip() for piece in SPEC_SENTENCE_SPLIT_RE.split(spec_text) if piece.strip()]

    for port in ports:
        if port.direction != "input" or is_clock_name(port.name):
            continue

        normalized = normalize_name(port.name)
        tokens = name_tokens(port.name)
        for sentence in sentences:
            lowered = sentence.lower()
            lowered_norm = normalize_name(lowered)

            if normalized not in lowered_norm and not any(token in lowered for token in tokens):
                continue

            numbers = [int(item) for item in re.findall(r"\b\d+\b", lowered)]
            if not numbers:
                continue

            if any(word in lowered for word in ["range", "between", "from", "inclusive"]):
                if len(numbers) >= 2:
                    update_domain(
                        domains,
                        port.name,
                        min(numbers[0], numbers[1]),
                        max(numbers[0], numbers[1]),
                        "spec_text_range",
                    )
            elif any(word in lowered for word in ["max", "maximum", "at most"]):
                update_domain(
                    domains,
                    port.name,
                    0,
                    max(numbers),
                    "spec_text_maximum",
                )

    finalized: dict[str, dict] = {}
    for port_name, entry in domains.items():
        final_entry = finalize_domain_entry(entry)
        if final_entry is not None:
            finalized[port_name] = final_entry
    return finalized


def infer_input_constraints(
    *,
    ports: list[Port],
    spec_text: str,
    golden_tb_text: str,
) -> dict[str, dict]:
    tb_domains = infer_domains_from_golden_tb(golden_tb_text, ports)
    spec_domains = infer_domains_from_spec(spec_text, ports)
    constraints: dict[str, dict] = {}

    for port in ports:
        if port.direction != "input" or is_clock_name(port.name):
            continue

        if is_reset_name(port.name) and (port.bits or 1) == 1:
            constraints[port.name] = {
                "kind": "reset_bool",
                "source": "control_heuristic",
            }
            continue

        if port.name in tb_domains:
            constraints[port.name] = tb_domains[port.name]
            continue

        if port.name in spec_domains:
            constraints[port.name] = spec_domains[port.name]
            continue

        if (port.bits or 1) == 1:
            constraints[port.name] = {
                "kind": "range",
                "min": 0,
                "max": 1,
                "source": "single_bit_default",
            }
            continue

        constraints[port.name] = {
            "kind": "constant",
            "value": 0,
            "source": "conservative_zero_fallback",
        }

    return constraints


def render_constraint_summary(constraints: dict[str, dict]) -> str:
    parts = []
    for port_name in sorted(constraints):
        entry = constraints[port_name]
        kind = entry.get("kind")
        source = entry.get("source", "unknown")
        if kind == "range":
            parts.append(f"{port_name}={entry['min']}..{entry['max']} ({source})")
        elif kind == "enum":
            values = ",".join(str(value) for value in entry.get("values", []))
            parts.append(f"{port_name} in {{{values}}} ({source})")
        elif kind == "constant":
            parts.append(f"{port_name}={entry['value']} ({source})")
        elif kind == "reset_bool":
            parts.append(f"{port_name}=boolean-reset ({source})")
    return "; ".join(parts)


def rename_top_module(text: str, expected_name: str) -> str:
    return re.sub(
        r"(\bmodule\s+)([A-Za-z_][A-Za-z0-9_$]*)",
        rf"\1{expected_name}",
        text,
        count=1,
    )


def sanitize_reverse_rtl(text: str, expected_module_name: str) -> str:
    normalized = strip_code_fences(text).strip() + "\n"
    try:
        actual_name = module_name_from_text(normalized)
        if actual_name != expected_module_name:
            normalized = rename_top_module(normalized, expected_module_name)
    except ValueError:
        return normalized
    return normalized


def latest_solved_iteration(root: Path, problem: str, explicit_tag: str = "") -> tuple[str, dict]:
    if explicit_tag:
        tags = [explicit_tag]
    else:
        iterations_dir = root / "outputs" / problem / "iterations"
        tags = []
        if iterations_dir.exists():
            tags = sorted(
                [
                    path.name
                    for path in iterations_dir.iterdir()
                    if path.is_dir() and re.fullmatch(r"iter_\d+", path.name)
                ],
                reverse=True,
            )

    for tag in tags:
        collected_path = (
            root
            / "outputs"
            / problem
            / "iterations"
            / tag
            / "analysis"
            / "collected_results.json"
        )
        if not collected_path.exists():
            continue

        collected = read_json(collected_path)
        passed = collected.get("passed_candidates", [])
        if collected.get("status") == "solved" and len(passed) == 1:
            return tag, collected

    raise FileNotFoundError(
        f"Unable to locate a solved iteration for {problem}. "
        "Expected a collected_results.json file with exactly one passing candidate."
    )


def resolve_winner_rtl(root: Path, problem: str, collected: dict) -> tuple[str, Path]:
    passed = collected.get("passed_candidates", [])
    if len(passed) != 1:
        raise ValueError(
            f"Expected exactly one winning mutant, found {len(passed)} entries: {passed}"
        )

    winner_name = passed[0]
    winner_path = root / "problems" / problem / "rtl" / f"{winner_name}.v"
    if not winner_path.exists():
        winner_path = root / "problems" / problem / "rtl" / f"{winner_name}.sv"
    if not winner_path.exists():
        raise FileNotFoundError(f"Winning mutant RTL not found for {winner_name}")
    return winner_name, winner_path


def build_interface_block(ports: list[Port]) -> str:
    lines = []
    for port in ports:
        width = f" {port.width}" if port.width else ""
        lines.append(f"- {port.direction}{width} {port.name}")
    return "\n".join(lines)


def build_initial_prompt(
    *,
    problem: str,
    spec_text: str,
    golden_tb_text: str,
    original_module_name: str,
    reverse_module_name: str,
    ports: list[Port],
    output_path: Path,
) -> str:
    return "\n".join(
        [
            "Follow AGENTS.md exactly.",
            "",
            f"Task: reverse engineer an RTL implementation for {problem} from the spec and the golden testbench.",
            "",
            "Requirements:",
            f"- Write the complete reverse-engineered RTL ONLY to: {output_path}",
            f"- The module name MUST be `{reverse_module_name}`.",
            f"- The original winning RTL module name is `{original_module_name}`. Do not emit a wrapper with that original name here.",
            "- Match the original port order, directions, and widths exactly.",
            "- Produce synthesizable Verilog/SystemVerilog compatible with iverilog -g2012.",
            "- Use the spec and the golden testbench as behavioral ground truth.",
            "- Do not generate a testbench, markdown, or prose. Write only the RTL.",
            "",
            "Exact port contract:",
            build_interface_block(ports),
            "",
            "Specification:",
            "```text",
            spec_text.rstrip(),
            "```",
            "",
            "Golden testbench:",
            "```verilog",
            golden_tb_text.rstrip(),
            "```",
        ]
    ) + "\n"


def build_refinement_prompt(
    *,
    problem: str,
    spec_text: str,
    golden_tb_text: str,
    previous_rtl_text: str,
    reverse_module_name: str,
    ports: list[Port],
    output_path: Path,
    validation_payload: dict,
) -> str:
    return "\n".join(
        [
            "Follow AGENTS.md exactly.",
            "",
            f"Task: refine the reverse-engineered RTL for {problem} so it passes the golden testbench.",
            "",
            "Requirements:",
            f"- Write the complete refined RTL ONLY to: {output_path}",
            f"- Keep the module name exactly `{reverse_module_name}`.",
            "- Keep the original port order, directions, and widths unchanged.",
            "- Preserve iverilog -g2012 compatibility.",
            "- Use the validation feedback below to correct behavioral mistakes.",
            "- Do not generate a wrapper, a testbench, or prose. Write only the RTL.",
            "",
            "Exact port contract:",
            build_interface_block(ports),
            "",
            "Previous reverse-engineered RTL:",
            "```verilog",
            previous_rtl_text.rstrip(),
            "```",
            "",
            "Latest validation feedback:",
            "```json",
            json.dumps(validation_payload, indent=2),
            "```",
            "",
            "Specification:",
            "```text",
            spec_text.rstrip(),
            "```",
            "",
            "Golden testbench:",
            "```verilog",
            normalize_text_block(golden_tb_text, max_chars=12000),
            "```",
        ]
    ) + "\n"


def run_codex_prompt(root: Path, attempt_dir: Path, prompt: str, label: str) -> dict:
    prompt_path = attempt_dir / "prompt.txt"
    codex_dir = attempt_dir / "codex"
    ensure_dir(codex_dir)

    final_message_path = codex_dir / "final_message.txt"
    events_path = codex_dir / "events.jsonl"
    stderr_path = codex_dir / "stderr.log"

    prompt_path.write_text(prompt, encoding="utf-8")

    cmd = [
        "codex",
        "exec",
        "-C",
        str(root),
        "--full-auto",
        "--json",
        "-o",
        str(final_message_path),
        "-",
    ]

    print(f"[info] {label}: running Codex reverse-engineering prompt")
    print(f"[run] {' '.join(cmd)}")

    proc = subprocess.run(
        cmd,
        cwd=str(root),
        input=prompt,
        text=True,
        capture_output=True,
    )

    events_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")

    if proc.returncode != 0:
        raise RuntimeError(
            f"Codex reverse-engineering step failed ({proc.returncode}). "
            f"Inspect {events_path} and {stderr_path}."
        )

    print(f"[info] {label}: prompt written to {prompt_path}")
    print(f"[info] {label}: Codex logs written to {codex_dir}")

    return {
        "prompt_path": str(prompt_path),
        "final_message_path": str(final_message_path),
        "events_path": str(events_path),
        "stderr_path": str(stderr_path),
    }


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    print(f"[run] {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)


def status_from_outputs(returncode: int, stdout: str, stderr: str) -> str:
    combined = f"{stdout}\n{stderr}"
    if returncode != 0:
        return "run_error"
    if "TB_FAIL" in combined:
        return "fail"
    if "TB_PASS" in combined:
        return "pass"
    return "unknown"


def build_wrapper_text(original_module_name: str, reverse_module_name: str, ports: list[Port]) -> str:
    decls = "\n".join(f"    {format_decl(port)}" for port in ports)
    conns = instantiate_ports(ports)
    return "\n".join(
        [
            f"module {original_module_name}({port_names_csv(ports)});",
            decls,
            "",
            f"    {reverse_module_name} impl (",
            conns,
            "    );",
            "endmodule",
            "",
        ]
    )


def comparison_connections(ports: list[Port], output_suffix: str) -> str:
    lines = []
    for index, port in enumerate(ports):
        comma = "," if index < len(ports) - 1 else ""
        signal_name = port.name if port.direction == "input" else f"{port.name}{output_suffix}"
        lines.append(f"        .{port.name}({signal_name}){comma}")
    return "\n".join(lines)


def validate_reverse_candidate(
    *,
    root: Path,
    attempt_dir: Path,
    reverse_rtl_path: Path,
    wrapper_path: Path,
    golden_tb_path: Path,
) -> dict:
    build_dir = attempt_dir / "validation"
    ensure_dir(build_dir)

    out_path = build_dir / "golden_tb_validation.out"
    compile_cmd = [
        "iverilog",
        "-g2012",
        "-o",
        str(out_path),
        str(reverse_rtl_path),
        str(wrapper_path),
        str(golden_tb_path),
    ]
    compile_proc = run_cmd(compile_cmd, cwd=root)

    compile_stdout = compile_proc.stdout or ""
    compile_stderr = compile_proc.stderr or ""
    run_stdout = ""
    run_stderr = ""
    run_rc = None

    if compile_proc.returncode != 0:
        status = "compile_error"
    else:
        run_cmdline = ["vvp", str(out_path)]
        run_proc = run_cmd(run_cmdline, cwd=root)
        run_rc = run_proc.returncode
        run_stdout = run_proc.stdout or ""
        run_stderr = run_proc.stderr or ""
        status = status_from_outputs(run_proc.returncode, run_stdout, run_stderr)

    payload = {
        "timestamp_utc": utc_now(),
        "reverse_rtl_path": str(reverse_rtl_path),
        "wrapper_path": str(wrapper_path),
        "golden_tb_path": str(golden_tb_path),
        "compile_cmd": compile_cmd,
        "compile_rc": compile_proc.returncode,
        "compile_stdout": compile_stdout,
        "compile_stderr": compile_stderr,
        "run_rc": run_rc,
        "run_stdout": run_stdout,
        "run_stderr": run_stderr,
        "status": status,
    }

    write_json(build_dir / "validation_result.json", payload)
    return payload


def width_random_expr(width: str) -> str:
    bits = width_to_bits(width) or 1
    chunks = max(1, math.ceil(bits / 32))
    if chunks == 1:
        return "$random"
    return "{ " + ", ".join("$random" for _ in range(chunks)) + " }"


def build_comparison_tb(
    *,
    problem: str,
    winner_module_name: str,
    reverse_module_name: str,
    ports: list[Port],
    input_constraints: dict[str, dict],
    cycles: int = 250,
) -> str:
    input_ports = [port for port in ports if port.direction == "input"]
    output_ports = [port for port in ports if port.direction == "output"]
    clock_ports = [
        port
        for port in input_ports
        if is_clock_name(port.name) and (port.bits or 1) == 1
    ]
    reset_ports = [port for port in input_ports if is_reset_name(port.name)]
    random_ports = [port for port in input_ports if port not in clock_ports]

    decls = []
    for port in input_ports:
        decls.append(f"    {reg_decl(port)}")
    for port in output_ports:
        decls.append(f"    {wire_decl(Port(port.direction, f'{port.name}_winner', port.width))}")
        decls.append(f"    {wire_decl(Port(port.direction, f'{port.name}_rvs', port.width))}")

    winner_connections = comparison_connections(ports, "_winner")
    reverse_connections = comparison_connections(ports, "_rvs")

    init_lines = []
    for port in input_ports:
        if port in clock_ports:
            init_lines.append(f"        {port.name} = 1'b0;")
        elif port in reset_ports:
            asserted = "1'b0" if is_active_low_name(port.name) else "1'b1"
            init_lines.append(f"        {port.name} = {asserted};")
        else:
            init_lines.append(f"        {port.name} = '0;")

    clock_blocks = []
    base_periods = [5, 7, 11, 13]
    for index, port in enumerate(clock_ports):
        period = base_periods[index % len(base_periods)]
        clock_blocks.extend(
            [
                "    initial begin",
                f"        {port.name} = 1'b0;",
                f"        forever #{period} {port.name} = ~{port.name};",
                "    end",
                "",
            ]
        )

    drive_lines = []
    for port in random_ports:
        constraint = input_constraints.get(port.name, {})
        if port in reset_ports and (port.bits or 1) == 1:
            if is_active_low_name(port.name):
                drive_lines.append(
                    f"        {port.name} = ($random % 11 == 0) ? 1'b0 : 1'b1;"
                )
            else:
                drive_lines.append(
                    f"        {port.name} = ($random % 11 == 0) ? 1'b1 : 1'b0;"
                )
        elif constraint.get("kind") == "range":
            low = int(constraint["min"])
            high = int(constraint["max"])
            if low == high:
                drive_lines.append(f"        {port.name} = {low};")
            elif low == 0 and high == 1 and (port.bits or 1) == 1:
                drive_lines.append(f"        {port.name} = $random;")
            else:
                span = high - low + 1
                drive_lines.append(
                    f"        {port.name} = ((($random % {span}) + {span}) % {span}) + {low};"
                )
        elif constraint.get("kind") == "enum":
            values = list(constraint.get("values", []))
            if len(values) == 1:
                drive_lines.append(f"        {port.name} = {values[0]};")
            elif values:
                drive_lines.append(
                    f"        rand_sel = ((($random % {len(values)}) + {len(values)}) % {len(values)});"
                )
                drive_lines.append("        case (rand_sel)")
                for index, value in enumerate(values[:-1]):
                    drive_lines.append(f"            {index}: {port.name} = {value};")
                drive_lines.append(f"            default: {port.name} = {values[-1]};")
                drive_lines.append("        endcase")
        elif constraint.get("kind") == "constant":
            drive_lines.append(f"        {port.name} = {int(constraint['value'])};")
        else:
            drive_lines.append(f"        {port.name} = {width_random_expr(port.width)};")

    deassert_lines = []
    for port in reset_ports:
        if (port.bits or 1) != 1:
            continue
        value = "1'b1" if is_active_low_name(port.name) else "1'b0"
        deassert_lines.append(f"        {port.name} = {value};")

    compare_lines = []
    if output_ports:
        for port in output_ports:
            compare_lines.extend(
                [
                    f"        if ({port.name}_winner !== {port.name}_rvs) begin",
                    "            mismatch_count = mismatch_count + 1;",
                    "            $display(",
                    f'                "TB_FAIL problem={problem} phase=%0s step=%0d signal={port.name} winner=%0h reverse=%0h",',
                    f"                phase, step_count, {port.name}_winner, {port.name}_rvs",
                    "            );",
                    "            $finish;",
                    "        end",
                ]
            )
    else:
        compare_lines.append("        // No output ports were found, so only compilation is being compared.")

    stimulus_lines = [
        "    initial begin",
        "        mismatch_count = 0;",
        "        step_count = 0;",
        *init_lines,
        "",
        "        repeat (3) begin",
        "            #17;",
        '            check_outputs("reset_phase");',
        "        end",
    ]
    if deassert_lines:
        stimulus_lines.extend(["", *deassert_lines])
    stimulus_lines.extend(
        [
            "",
            f"        repeat ({cycles}) begin",
            "            #17;",
            "            drive_inputs();",
            "            #1;",
            "            step_count = step_count + 1;",
            '            check_outputs("random_phase");',
            "        end",
            "",
            '        $display("TB_PASS functional_compare problem=%0s steps=%0d", "' + problem + '", step_count);',
            "        $finish;",
            "    end",
        ]
    )

    return "\n".join(
        [
            "module tb;",
            "",
            *decls,
            "    integer mismatch_count;",
            "    integer step_count;",
            "    integer rand_sel;",
            "",
            f"    {winner_module_name} winner_dut (",
            winner_connections,
            "    );",
            "",
            f"    {reverse_module_name} reverse_dut (",
            reverse_connections,
            "    );",
            "",
            *clock_blocks,
            "    task automatic drive_inputs;",
            "    begin",
            *(drive_lines or ["        // No non-clock inputs to randomize."]),
            "    end",
            "    endtask",
            "",
            "    task automatic check_outputs;",
            "        input [255:0] phase;",
            "    begin",
            *compare_lines,
            "    end",
            "    endtask",
            "",
            *stimulus_lines,
            "endmodule",
            "",
        ]
    )


def run_functional_comparison(
    *,
    root: Path,
    final_dir: Path,
    compare_tb_path: Path,
    winner_rtl_path: Path,
    reverse_rtl_path: Path,
) -> dict:
    compare_dir = final_dir / "functional_comparison"
    ensure_dir(compare_dir)

    out_path = compare_dir / "winner_vs_reverse.out"
    compile_cmd = [
        "iverilog",
        "-g2012",
        "-o",
        str(out_path),
        str(winner_rtl_path),
        str(reverse_rtl_path),
        str(compare_tb_path),
    ]
    compile_proc = run_cmd(compile_cmd, cwd=root)

    compile_stdout = compile_proc.stdout or ""
    compile_stderr = compile_proc.stderr or ""
    run_stdout = ""
    run_stderr = ""
    run_rc = None

    if compile_proc.returncode != 0:
        status = "compile_error"
    else:
        run_proc = run_cmd(["vvp", str(out_path)], cwd=root)
        run_rc = run_proc.returncode
        run_stdout = run_proc.stdout or ""
        run_stderr = run_proc.stderr or ""
        status = status_from_outputs(run_proc.returncode, run_stdout, run_stderr)

    payload = {
        "timestamp_utc": utc_now(),
        "compare_tb_path": str(compare_tb_path),
        "winner_rtl_path": str(winner_rtl_path),
        "reverse_rtl_path": str(reverse_rtl_path),
        "compile_cmd": compile_cmd,
        "compile_rc": compile_proc.returncode,
        "compile_stdout": compile_stdout,
        "compile_stderr": compile_stderr,
        "run_rc": run_rc,
        "run_stdout": run_stdout,
        "run_stderr": run_stderr,
        "status": status,
    }

    write_json(compare_dir / "comparison_result.json", payload)
    return payload


def structural_stats(text: str) -> dict:
    cleaned = strip_comments(text)
    non_empty_lines = [line for line in cleaned.splitlines() if line.strip()]
    return {
        "non_empty_lines": len(non_empty_lines),
        "always": count_regex(cleaned, r"\balways\b"),
        "always_ff": count_regex(cleaned, r"\balways_ff\b"),
        "always_comb": count_regex(cleaned, r"\balways_comb\b"),
        "assign": count_regex(cleaned, r"^\s*assign\b"),
        "if": count_regex(cleaned, r"\bif\b"),
        "case": count_regex(cleaned, r"\bcase(?:x|z)?\b"),
    }


def dynamic_categories(spec_text: str, golden_tb_text: str, reverse_rtl_text: str, ports: list[Port]) -> list[str]:
    corpus = " ".join([spec_text.lower(), golden_tb_text.lower(), reverse_rtl_text.lower()])
    categories = [
        "Interface Contract",
        "Golden Testbench Validation",
        "Differential Functional Comparison",
    ]

    if any(is_clock_name(port.name) for port in ports):
        categories.append("Clocking and State Update")
    if any(is_reset_name(port.name) for port in ports) or "reset" in corpus or " rst" in corpus:
        categories.append("Reset and Initialization")
    if any(token in corpus for token in ["reinit", "load", "preset", "initial_value", "seed"]):
        categories.append("Load/Reinitialization Priority")
    if any(token in corpus for token in ["wrap", "overflow", "underflow", "modulo", "modulus"]):
        categories.append("Boundary and Wraparound Behavior")
    if any(token in corpus for token in ["incr", "decr", "increment", "decrement", "up", "down"]):
        categories.append("Directional or Arithmetic Update Rules")
    if any(token in corpus for token in ["ready", "credit", "stall", "full", "empty", "handshake"]):
        categories.append("Handshake and Flow-Control Semantics")
    elif "valid" in corpus:
        categories.append("Control/Validity Gating")
    if any(port.name.lower().endswith("_next") for port in ports) or "value_next" in corpus or "next state" in corpus:
        categories.append("Next-State Visibility")

    categories.append("Structural Realization")
    return categories


def interface_comparison(
    winner_ports: list[Port],
    reverse_ports: list[Port],
    parse_error: str = "",
) -> dict:
    winner_triplets = [(port.direction, port.name, port.width) for port in winner_ports]
    reverse_triplets = [(port.direction, port.name, port.width) for port in reverse_ports]
    return {
        "exact_match": winner_triplets == reverse_triplets and not parse_error,
        "winner_ports": winner_triplets,
        "reverse_ports": reverse_triplets,
        "reverse_parse_error": parse_error,
    }


def validation_excerpt(payload: dict) -> str:
    if payload["status"] == "compile_error":
        return shorten_output(payload.get("compile_stderr", "") or payload.get("compile_stdout", ""))
    return shorten_output(
        "\n".join(
            [
                payload.get("run_stdout", ""),
                payload.get("run_stderr", ""),
            ]
        )
    )


def similarity_summary(validation_status: str, comparison_status: str, interface_exact: bool) -> dict:
    score = 0
    if interface_exact:
        score += 20
    if validation_status == "pass":
        score += 35
    if comparison_status == "pass":
        score += 45

    if score >= 90:
        label = "high"
    elif score >= 60:
        label = "moderate"
    else:
        label = "low"

    return {
        "score": score,
        "label": label,
    }


def build_study_markdown(
    *,
    problem: str,
    winner_name: str,
    winner_rtl_path: Path,
    reverse_rtl_path: Path,
    winning_tag: str,
    validation_payload: dict,
    comparison_payload: dict,
    categories: list[str],
    interface_info: dict,
    winner_stats: dict,
    reverse_stats: dict,
    similarity: dict,
    reverse_attempts: list[dict],
    comparison_constraints: dict[str, dict],
) -> str:
    lines = [
        f"# Reverse-Engineering Comparative Study: {problem}",
        "",
        "## Context",
        f"- Winning iteration tag: `{winning_tag}`",
        f"- Winning mutant: `{winner_name}`",
        f"- Winning mutant RTL: `{winner_rtl_path}`",
        f"- Reverse-engineered RTL: `{reverse_rtl_path}`",
        f"- Reverse-engineering attempts: {len(reverse_attempts)}",
        f"- Golden TB validation status: `{validation_payload['status']}`",
        f"- Differential comparison status: `{comparison_payload.get('status', 'not_run')}`",
        "",
    ]

    for category in categories:
        lines.extend([f"## {category}"])

        if category == "Interface Contract":
            lines.append(
                f"- Exact port-contract match between winning mutant and reverse-engineered RTL: "
                f"{'yes' if interface_info['exact_match'] else 'no'}."
            )
            if interface_info["exact_match"]:
                lines.append("- Port order, names, directions, and widths align exactly.")
            elif interface_info.get("reverse_parse_error"):
                lines.append(
                    f"- Reverse RTL port parsing failed: `{interface_info['reverse_parse_error']}`"
                )
            else:
                lines.append("- Port contract mismatch detected. Inspect the winner/reverse port lists in the JSON summary.")

        elif category == "Golden Testbench Validation":
            lines.append(
                f"- The reverse-engineered RTL {'passes' if validation_payload['status'] == 'pass' else 'does not pass'} the golden TB."
            )
            lines.append(
                f"- Most relevant validation evidence: `{validation_excerpt(validation_payload) or 'no stdout/stderr captured'}`"
            )

        elif category == "Differential Functional Comparison":
            status = comparison_payload.get("status", "not_run")
            lines.append(
                f"- Winner-vs-reverse side-by-side simulation status: `{status}`."
            )
            lines.append(
                f"- Most relevant comparison evidence: `{validation_excerpt(comparison_payload) or 'comparison was not executed'}`"
            )
            if comparison_constraints:
                lines.append(
                    f"- Input-domain constraints applied during differential comparison: "
                    f"`{render_constraint_summary(comparison_constraints)}`"
                )

        elif category == "Clocking and State Update":
            lines.append("- The study detected clocked behavior from the interface/spec/TB context.")
            lines.append(
                f"- Reverse RTL structural hint: always/always_ff blocks = {reverse_stats['always']}/{reverse_stats['always_ff']}."
            )
            lines.append(
                "- Functional alignment for state updates is judged primarily from the golden TB result and the side-by-side comparison."
            )

        elif category == "Reset and Initialization":
            lines.append("- Reset-like ports were detected and included in both the golden TB and the differential comparison stimulus.")
            lines.append(
                "- Agreement here is treated as functional evidence rather than text-only inference, because the winning mutant is netlist-like."
            )

        elif category == "Load/Reinitialization Priority":
            lines.append(
                "- Load/reinit behavior appears to be part of the problem contract based on the spec/TB keywords."
            )
            lines.append(
                "- The reverse-engineered RTL is considered aligned only if the golden TB accepted it and the side-by-side comparison found no mismatch."
            )

        elif category == "Boundary and Wraparound Behavior":
            lines.append(
                "- Boundary behavior was selected dynamically because wrap/overflow/underflow terminology appears in the spec/TB context."
            )
            lines.append(
                "- Matching behavior is supported by the reverse RTL passing the golden TB and by the absence of winner-vs-reverse mismatches."
            )

        elif category == "Directional or Arithmetic Update Rules":
            lines.append(
                "- Arithmetic or directional update behavior was selected dynamically from the spec/TB vocabulary."
            )
            lines.append(
                "- Functional agreement is assessed from executable checks rather than attempting to semantically decompile the winning mutant netlist."
            )

        elif category == "Handshake and Flow-Control Semantics":
            lines.append(
                "- Handshake/flow-control signals were detected from the port names and problem language."
            )
            lines.append(
                "- The side-by-side comparison injected randomized input activity so that winner/reverse agreement is based on observed behavior."
            )

        elif category == "Control/Validity Gating":
            lines.append(
                "- Validity-style control signals were detected from the spec/TB/RTL context, so gating behavior was examined explicitly."
            )
            lines.append(
                "- The study treats agreement here as executable evidence from the golden TB and side-by-side comparison rather than as a naming-only guess."
            )

        elif category == "Next-State Visibility":
            lines.append(
                "- The problem exposes a next-state style signal or wording, so this category was added dynamically."
            )
            lines.append(
                "- Agreement in this category is backed by the golden TB and differential simulation, not by superficial code similarity."
            )

        elif category == "Structural Realization":
            lines.append(
                f"- Winning mutant structural stats: lines={winner_stats['non_empty_lines']}, "
                f"always={winner_stats['always']}, always_ff={winner_stats['always_ff']}, assign={winner_stats['assign']}."
            )
            lines.append(
                f"- Reverse RTL structural stats: lines={reverse_stats['non_empty_lines']}, "
                f"always={reverse_stats['always']}, always_ff={reverse_stats['always_ff']}, assign={reverse_stats['assign']}."
            )
            lines.append(
                "- Structural similarity may be low even when functional similarity is high, because the winning mutant is often gate/netlist-like while the reverse RTL is behavioral."
            )

        lines.append("")

    lines.extend(
        [
            "## Inference",
            (
                f"- Overall functional similarity between `{reverse_rtl_path.name}` and `{winner_rtl_path.name}` is "
                f"assessed as **{similarity['label']}** with a score of {similarity['score']}/100."
            ),
            "- The comparative study is complete. Review the validation evidence, differential comparison evidence, and similarity score to decide whether the reverse-engineered RTL is close enough to the winning mutant for this problem.",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    problem = args.problem

    try:
        final_dir = root / "outputs" / problem / "final"
        reverse_root = final_dir / "reverse_engineering"
        ensure_dir(final_dir)
        ensure_dir(reverse_root)

        preflight, preflight_path = load_problem_context(root, problem, warn=print)
        spec_text = read_spec_text_from_context(preflight)
        winning_tag, collected = latest_solved_iteration(root, problem, args.winner_tag)
        winner_name, winner_rtl_path = resolve_winner_rtl(root, problem, collected)

        golden_tb_path = final_dir / "golden_tb.v"
        if not golden_tb_path.exists():
            raise FileNotFoundError(f"Golden testbench not found: {golden_tb_path}")

        winner_rtl_text = read_text(winner_rtl_path)
        golden_tb_text = read_text(golden_tb_path)
        winner_module_name = module_name_from_text(winner_rtl_text)
        winner_ports = extract_ports(winner_rtl_text)
        reverse_module_name = f"{winner_module_name}_rvs_engr"

        print(f"[info] Preflight context: {preflight_path}")
        print(f"[info] Solved iteration: {winning_tag}")
        print(f"[info] Winning mutant: {winner_name} ({winner_rtl_path})")
        print(f"[info] Golden testbench: {golden_tb_path}")

        reverse_attempts: list[dict] = []
        latest_validation_payload: dict | None = None
        best_reverse_rtl_path: Path | None = None
        best_wrapper_path: Path | None = None

        previous_rtl_text = ""

        for attempt_index in range(1, args.max_refine_iters + 1):
            label = f"attempt_{attempt_index:02d}"
            attempt_dir = reverse_root / label
            ensure_dir(attempt_dir)

            reverse_rtl_path = attempt_dir / f"rvs_engr_rtl_{problem}.v"
            wrapper_path = attempt_dir / f"rvs_engr_wrapper_{problem}.v"

            if attempt_index == 1 and args.existing_reverse_rtl:
                seed_path = Path(args.existing_reverse_rtl)
                if not seed_path.is_absolute():
                    seed_path = (root / seed_path).resolve()
                if not seed_path.exists():
                    raise FileNotFoundError(f"Existing reverse RTL seed not found: {seed_path}")

                seed_text = sanitize_reverse_rtl(read_text(seed_path), reverse_module_name)
                reverse_rtl_path.write_text(seed_text, encoding="utf-8")
                seed_info = {
                    "seed_path": str(seed_path),
                    "copied_to": str(reverse_rtl_path),
                }
                write_json(attempt_dir / "seed_info.json", seed_info)
                print(f"[info] {label}: seeded reverse RTL from {seed_path}")
            else:
                if attempt_index == 1:
                    prompt = build_initial_prompt(
                        problem=problem,
                        spec_text=spec_text,
                        golden_tb_text=golden_tb_text,
                        original_module_name=winner_module_name,
                        reverse_module_name=reverse_module_name,
                        ports=winner_ports,
                        output_path=reverse_rtl_path,
                    )
                else:
                    prompt = build_refinement_prompt(
                        problem=problem,
                        spec_text=spec_text,
                        golden_tb_text=golden_tb_text,
                        previous_rtl_text=previous_rtl_text,
                        reverse_module_name=reverse_module_name,
                        ports=winner_ports,
                        output_path=reverse_rtl_path,
                        validation_payload=latest_validation_payload or {},
                    )

                codex_meta = run_codex_prompt(root, attempt_dir, prompt, label)
                if not reverse_rtl_path.exists():
                    raise FileNotFoundError(
                        f"{label}: Codex did not write the reverse-engineered RTL to {reverse_rtl_path}"
                    )
                attempt_meta = attempt_dir / "codex_meta.json"
                write_json(attempt_meta, codex_meta)

            reverse_text = sanitize_reverse_rtl(read_text(reverse_rtl_path), reverse_module_name)
            reverse_rtl_path.write_text(reverse_text, encoding="utf-8")
            wrapper_path.write_text(
                build_wrapper_text(winner_module_name, reverse_module_name, winner_ports),
                encoding="utf-8",
            )

            latest_validation_payload = validate_reverse_candidate(
                root=root,
                attempt_dir=attempt_dir,
                reverse_rtl_path=reverse_rtl_path,
                wrapper_path=wrapper_path,
                golden_tb_path=golden_tb_path,
            )
            previous_rtl_text = reverse_text
            best_reverse_rtl_path = reverse_rtl_path
            best_wrapper_path = wrapper_path

            reverse_attempts.append(
                {
                    "attempt": label,
                    "reverse_rtl_path": str(reverse_rtl_path),
                    "wrapper_path": str(wrapper_path),
                    "validation_status": latest_validation_payload["status"],
                }
            )

            print(f"[info] {label}: golden TB validation status = {latest_validation_payload['status']}")

            if latest_validation_payload["status"] == "pass":
                break

        if best_reverse_rtl_path is None or best_wrapper_path is None or latest_validation_payload is None:
            raise RuntimeError("Reverse-engineering stage did not produce any candidate RTL.")

        final_reverse_rtl = final_dir / f"rvs_engr_rtl_{problem}.v"
        final_wrapper_rtl = final_dir / f"rvs_engr_wrapper_{problem}.v"
        shutil.copy2(best_reverse_rtl_path, final_reverse_rtl)
        shutil.copy2(best_wrapper_path, final_wrapper_rtl)

        comparison_payload = {
            "status": "not_run",
            "compile_stdout": "",
            "compile_stderr": "",
            "run_stdout": "",
            "run_stderr": "",
        }

        reverse_rtl_text = read_text(final_reverse_rtl)
        reverse_parse_error = ""
        try:
            reverse_ports = extract_ports(reverse_rtl_text)
        except ValueError as exc:
            reverse_ports = []
            reverse_parse_error = str(exc)

        compare_tb_path = final_dir / f"rvs_engr_compare_tb_{problem}.v"
        comparison_constraints = infer_input_constraints(
            ports=winner_ports,
            spec_text=spec_text,
            golden_tb_text=golden_tb_text,
        )
        compare_tb_path.write_text(
            build_comparison_tb(
                problem=problem,
                winner_module_name=winner_module_name,
                reverse_module_name=reverse_module_name,
                ports=winner_ports,
                input_constraints=comparison_constraints,
            ),
            encoding="utf-8",
        )

        if latest_validation_payload["status"] == "pass":
            comparison_payload = run_functional_comparison(
                root=root,
                final_dir=final_dir,
                compare_tb_path=compare_tb_path,
                winner_rtl_path=winner_rtl_path,
                reverse_rtl_path=final_reverse_rtl,
            )
            print(f"[info] functional comparison status = {comparison_payload['status']}")
        else:
            print(
                "[warn] Skipping functional comparison because the reverse-engineered RTL never passed the golden TB."
            )

        categories = dynamic_categories(spec_text, golden_tb_text, reverse_rtl_text, winner_ports)
        interface_info = interface_comparison(winner_ports, reverse_ports, reverse_parse_error)
        winner_stats = structural_stats(winner_rtl_text)
        reverse_stats = structural_stats(reverse_rtl_text)
        similarity = similarity_summary(
            latest_validation_payload["status"],
            comparison_payload.get("status", "not_run"),
            interface_info["exact_match"],
        )

        summary_payload = {
            "timestamp_utc": utc_now(),
            "problem": problem,
            "winning_tag": winning_tag,
            "winning_mutant": winner_name,
            "winning_mutant_rtl": str(winner_rtl_path),
            "reverse_rtl_path": str(final_reverse_rtl),
            "wrapper_rtl_path": str(final_wrapper_rtl),
            "golden_tb_path": str(golden_tb_path),
            "validation": latest_validation_payload,
            "functional_comparison": comparison_payload,
            "attempts": reverse_attempts,
            "comparison_input_constraints": comparison_constraints,
            "categories": categories,
            "interface": interface_info,
            "winner_stats": winner_stats,
            "reverse_stats": reverse_stats,
            "similarity": similarity,
        }

        summary_json_path = final_dir / "reverse_engineering_summary.json"
        write_json(summary_json_path, summary_payload)

        study_md_path = final_dir / "reverse_engineering_comparative_study.md"
        study_md_path.write_text(
            build_study_markdown(
                problem=problem,
                winner_name=winner_name,
                winner_rtl_path=winner_rtl_path,
                reverse_rtl_path=final_reverse_rtl,
                winning_tag=winning_tag,
                validation_payload=latest_validation_payload,
                comparison_payload=comparison_payload,
                categories=categories,
                interface_info=interface_info,
                winner_stats=winner_stats,
                reverse_stats=reverse_stats,
                similarity=similarity,
                reverse_attempts=reverse_attempts,
                comparison_constraints=comparison_constraints,
            ),
            encoding="utf-8",
        )

        print(f"[info] Reverse-engineered RTL written to: {final_reverse_rtl}")
        print(f"[info] Wrapper RTL written to: {final_wrapper_rtl}")
        print(f"[info] Functional comparison TB written to: {compare_tb_path}")
        print(f"[info] Reverse-engineering summary written to: {summary_json_path}")
        print(f"[info] Comparative study written to: {study_md_path}")

        print("[info] Reverse-engineering comparative study completed.")
        return 0

    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
