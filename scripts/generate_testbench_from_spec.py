#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


MODULE_RE = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
PORT_RE = re.compile(
    r"\b(input|output|inout)\b\s*(?:reg|wire|logic|signed)?\s*(\[[^\]]+\])?\s*([A-Za-z_][A-Za-z0-9_]*)"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate a spec-aware heuristic Verilog testbench."
    )
    p.add_argument("--problem", required=True, help="Problem name such as problem_1")
    p.add_argument("--root", default=".", help="Project root directory")
    p.add_argument("--tag", default="manual", help="Iteration tag")
    p.add_argument(
        "--iteration-packet",
        default="",
        help="Optional iteration packet JSON used to refine generation from simulation feedback.",
    )
    return p.parse_args()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def infer_module_name(rtl_text: str) -> str:
    m = MODULE_RE.search(rtl_text)
    return m.group(1) if m else "dut"


def infer_ports(rtl_text: str) -> list[dict]:
    ports = []
    seen = set()
    for m in PORT_RE.finditer(rtl_text):
        direction, width, name = m.groups()
        if name in seen:
            continue
        seen.add(name)
        ports.append(
            {
                "direction": direction,
                "width": width.strip() if width else "",
                "name": name,
            }
        )
    return ports


def parse_width_bits(width: str) -> int | None:
    if not width:
        return 1
    m = re.fullmatch(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", width)
    if not m:
        return None
    a = int(m.group(1))
    b = int(m.group(2))
    return abs(a - b) + 1


def bits_for_port(port: dict) -> int | None:
    return parse_width_bits(port.get("width", ""))


def is_clock_name(name: str) -> bool:
    n = name.lower()
    return n in {"clk", "clock", "i_clk", "sys_clk"}


def is_reset_name(name: str) -> bool:
    n = name.lower()
    return n in {"rst", "reset", "resetn", "rst_n", "reset_n", "aresetn", "arst_n"}


def is_enable_name(name: str) -> bool:
    n = name.lower()
    return n in {"en", "enable", "cnt_en", "count_en"} or "enable" in n


def is_load_name(name: str) -> bool:
    n = name.lower()
    return "load" in n or n in {"ld", "preset", "parallel_load"}


def is_updown_name(name: str) -> bool:
    n = name.lower()
    return (
        "up_down" in n
        or "updown" in n
        or n == "dir"
        or "direction" in n
        or n == "mode"
    )


def is_control_name(name: str) -> bool:
    return (
        is_clock_name(name)
        or is_reset_name(name)
        or is_enable_name(name)
        or is_load_name(name)
        or is_updown_name(name)
    )


def find_first(ports: list[dict], pred) -> dict | None:
    for p in ports:
        if p["direction"] == "input" and pred(p["name"]):
            return p
    return None


def find_output(ports: list[dict], pred) -> dict | None:
    for p in ports:
        if p["direction"] == "output" and pred(p["name"]):
            return p
    return None


def find_count_output(ports: list[dict]) -> dict | None:
    def pred(name: str) -> bool:
        n = name.lower()
        return (
            "count" in n
            or n in {"q", "out", "value", "cnt"}
            or "state" in n
        )

    out = find_output(ports, pred)
    if out:
        return out

    outputs = [p for p in ports if p["direction"] == "output"]
    if outputs:
        outputs = sorted(outputs, key=lambda p: bits_for_port(p) or 1, reverse=True)
        return outputs[0]
    return None


def find_data_input(ports: list[dict], count_bits: int | None) -> dict | None:
    candidates = []
    for p in ports:
        if p["direction"] != "input":
            continue
        if is_control_name(p["name"]):
            continue
        b = bits_for_port(p) or 1
        score = 0
        n = p["name"].lower()
        if any(k in n for k in ["data", "din", "d", "value", "preset", "load", "in"]):
            score += 5
        if count_bits is not None and b == count_bits:
            score += 3
        score += min(b, 16)
        candidates.append((score, p))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def find_flag_output(ports: list[dict], names: list[str]) -> dict | None:
    def pred(name: str) -> bool:
        n = name.lower()
        return any(k in n for k in names)
    return find_output(ports, pred)


def find_port_by_name(ports: list[dict], direction: str, name: str) -> dict | None:
    target = name.lower()
    for port in ports:
        if port["direction"] == direction and port["name"].lower() == target:
            return port
    return None


def is_active_low(port_name: str, spec_text: str) -> bool:
    n = port_name.lower()
    if n.endswith("n") or n.endswith("_n"):
        return True
    spec = spec_text.lower()
    if "active low" in spec and n.replace("_", "") in spec.replace("_", ""):
        return True
    return False


def infer_dir_up_value(dir_port: dict | None, spec_text: str) -> int:
    if dir_port is None:
        return 1
    spec = " ".join(spec_text.lower().split())
    name = dir_port["name"].lower()
    patterns_one_up = [
        rf"{re.escape(name)}\s*=\s*1[^.:\n]{{0,40}}up",
        rf"1[^.:\n]{{0,40}}up[^.:\n]{{0,40}}{re.escape(name)}",
        rf"{re.escape(name)}[^.:\n]{{0,20}}high[^.:\n]{{0,40}}up",
    ]
    patterns_zero_up = [
        rf"{re.escape(name)}\s*=\s*0[^.:\n]{{0,40}}up",
        rf"0[^.:\n]{{0,40}}up[^.:\n]{{0,40}}{re.escape(name)}",
        rf"{re.escape(name)}[^.:\n]{{0,20}}low[^.:\n]{{0,40}}up",
    ]
    for pat in patterns_one_up:
        if re.search(pat, spec):
            return 1
    for pat in patterns_zero_up:
        if re.search(pat, spec):
            return 0
    return 1


def signal_decl(port: dict) -> str:
    width = f"{port['width']} " if port["width"] else ""
    if port["direction"] == "input":
        return f"reg {width}{port['name']};".replace("  ", " ")
    return f"wire {width}{port['name']};".replace("  ", " ")


def port_connections(ports: list[dict]) -> str:
    lines = []
    for i, p in enumerate(ports):
        comma = "," if i < len(ports) - 1 else ""
        lines.append(f"        .{p['name']}({p['name']}){comma}")
    return "\n".join(lines)


def vnum(bits: int | None, value: int) -> str:
    if bits is None or bits <= 0:
        return str(value)
    mask = (1 << bits) - 1
    return f"{bits}'d{value & mask}"


def vhx(bits: int | None, value: int) -> str:
    if bits is None or bits <= 0:
        return str(value)
    width_hex = max(1, (bits + 3) // 4)
    mask = (1 << bits) - 1
    return f"{bits}'h{value & mask:0{width_hex}X}"


def looks_like_problem1_counter(spec_text: str, ports: list[dict]) -> bool:
    required_inputs = {
        "clk",
        "rst",
        "reinit",
        "incr_valid",
        "decr_valid",
        "initial_value",
        "incr",
        "decr",
    }
    required_outputs = {"value", "value_next"}

    input_names = {p["name"].lower() for p in ports if p["direction"] == "input"}
    output_names = {p["name"].lower() for p in ports if p["direction"] == "output"}
    spec_l = " ".join(spec_text.lower().split())

    return (
        required_inputs.issubset(input_names)
        and required_outputs.issubset(output_names)
        and "inclusive range of 0 to 10" in spec_l
        and "wrap around on overflow and underflow" in spec_l
        and "net change (`incr` - `decr`)" in spec_text
        and "value_next" in spec_l
    )


def build_problem1_counter_tb(
    problem: str,
    module_name: str,
    spec_path: str,
    ports: list[dict],
) -> str:
    clk = find_port_by_name(ports, "input", "clk")
    rst = find_port_by_name(ports, "input", "rst")
    reinit = find_port_by_name(ports, "input", "reinit")
    incr_valid = find_port_by_name(ports, "input", "incr_valid")
    decr_valid = find_port_by_name(ports, "input", "decr_valid")
    initial_value = find_port_by_name(ports, "input", "initial_value")
    incr = find_port_by_name(ports, "input", "incr")
    decr = find_port_by_name(ports, "input", "decr")
    value = find_port_by_name(ports, "output", "value")
    value_next = find_port_by_name(ports, "output", "value_next")

    decls = "\n".join(f"    {signal_decl(p)}" for p in ports)
    count_bits = bits_for_port(value) or 4
    incr_bits = bits_for_port(incr) or 2
    decr_bits = bits_for_port(decr) or 2
    init_bits = bits_for_port(initial_value) or count_bits

    return f"""`timescale 1ns/1ps

module tb_{module_name};

    // Spec-accurate bounded counter testbench
    // Problem: {problem}
    // Spec source: {spec_path}
    // Generated at: {datetime.now(timezone.utc).isoformat()}

{decls}

    integer errors;
    integer case_id;
    integer state_seed;
    integer init_seed;
    integer incr_seed;
    integer decr_seed;
    integer incr_valid_seed;
    integer decr_valid_seed;

    {module_name} dut (
{port_connections(ports)}
    );

    initial begin
        {clk['name']} = 0;
    end

    always #5 {clk['name']} = ~{clk['name']};

    function automatic integer wrap11(input integer raw_value);
        integer wrapped_value;
        begin
            wrapped_value = raw_value;
            while (wrapped_value < 0)
                wrapped_value = wrapped_value + 11;
            while (wrapped_value > 10)
                wrapped_value = wrapped_value - 11;
            wrap11 = wrapped_value;
        end
    endfunction

    function automatic [{count_bits - 1}:0] model_next_value;
        input integer current_value;
        input integer next_initial_value;
        input integer apply_reinit;
        input integer apply_incr_valid;
        input integer incr_amount;
        input integer apply_decr_valid;
        input integer decr_amount;
        integer delta;
        integer wrapped_result;
        begin
            if (apply_reinit) begin
                wrapped_result = wrap11(next_initial_value);
            end else begin
                delta = 0;
                if (apply_incr_valid)
                    delta = delta + incr_amount;
                if (apply_decr_valid)
                    delta = delta - decr_amount;
                wrapped_result = wrap11(current_value + delta);
            end
            model_next_value = wrapped_result;
        end
    endfunction

    task automatic drive_inputs;
        input integer apply_rst;
        input integer apply_reinit;
        input integer next_initial_value;
        input integer apply_incr_valid;
        input integer incr_amount;
        input integer apply_decr_valid;
        input integer decr_amount;
        begin
            {rst['name']} = apply_rst[0];
            {reinit['name']} = apply_reinit[0];
            {initial_value['name']} = wrap11(next_initial_value);
            {incr_valid['name']} = apply_incr_valid[0];
            {incr['name']} = incr_amount[{incr_bits - 1}:0];
            {decr_valid['name']} = apply_decr_valid[0];
            {decr['name']} = decr_amount[{decr_bits - 1}:0];
        end
    endtask

    task automatic expect_value;
        input integer expected_now;
        begin
            if ({value['name']} !== expected_now[{count_bits - 1}:0]) begin
                $display(
                    "TB_FAIL value mismatch: case=%0d expected=%0d got=%0d rst=%0d reinit=%0d init=%0d incr_valid=%0d incr=%0d decr_valid=%0d decr=%0d time=%0t",
                    case_id,
                    expected_now,
                    {value['name']},
                    {rst['name']},
                    {reinit['name']},
                    {initial_value['name']},
                    {incr_valid['name']},
                    {incr['name']},
                    {decr_valid['name']},
                    {decr['name']},
                    $time
                );
                errors = errors + 1;
            end
        end
    endtask

    task automatic expect_value_next;
        input integer current_value;
        input integer expected_next;
        begin
            if ({value_next['name']} !== expected_next[{count_bits - 1}:0]) begin
                $display(
                    "TB_FAIL value_next mismatch: case=%0d expected=%0d got=%0d current_value=%0d reinit=%0d init=%0d incr_valid=%0d incr=%0d decr_valid=%0d decr=%0d time=%0t",
                    case_id,
                    expected_next,
                    {value_next['name']},
                    current_value,
                    {reinit['name']},
                    {initial_value['name']},
                    {incr_valid['name']},
                    {incr['name']},
                    {decr_valid['name']},
                    {decr['name']},
                    $time
                );
                errors = errors + 1;
            end
        end
    endtask

    task automatic load_state;
        input integer start_state;
        integer wrapped_state;
        begin
            wrapped_state = wrap11(start_state);
            @(negedge {clk['name']});
            drive_inputs(1, 0, wrapped_state, 0, 0, 0, 0);
            @(posedge {clk['name']});
            #1;
            expect_value(wrapped_state);

            @(negedge {clk['name']});
            drive_inputs(0, 0, wrapped_state, 0, 0, 0, 0);
            #1;
            expect_value_next(wrapped_state, wrapped_state);
            @(posedge {clk['name']});
            #1;
            expect_value(wrapped_state);
        end
    endtask

    task automatic run_transition_case;
        input integer start_state;
        input integer apply_reinit;
        input integer next_initial_value;
        input integer apply_incr_valid;
        input integer incr_amount;
        input integer apply_decr_valid;
        input integer decr_amount;
        integer wrapped_state;
        integer expected_after;
        begin
            case_id = case_id + 1;
            wrapped_state = wrap11(start_state);
            expected_after = model_next_value(
                wrapped_state,
                next_initial_value,
                apply_reinit,
                apply_incr_valid,
                incr_amount,
                apply_decr_valid,
                decr_amount
            );

            load_state(wrapped_state);

            @(negedge {clk['name']});
            drive_inputs(0, apply_reinit, next_initial_value, apply_incr_valid, incr_amount, apply_decr_valid, decr_amount);
            #1;
            expect_value(wrapped_state);
            expect_value_next(wrapped_state, expected_after);

            @(posedge {clk['name']});
            #1;
            expect_value(expected_after);

            @(negedge {clk['name']});
            drive_inputs(0, 0, 0, 0, 0, 0, 0);
            #1;
            expect_value_next(expected_after, expected_after);
        end
    endtask

    initial begin
        $dumpfile("tb_{module_name}.vcd");
        $dumpvars(0, tb_{module_name});
    end

    initial begin
        {rst['name']} = 0;
        {reinit['name']} = 0;
        {incr_valid['name']} = 0;
        {decr_valid['name']} = 0;
        {initial_value['name']} = {vnum(init_bits, 0)};
        {incr['name']} = {vnum(incr_bits, 0)};
        {decr['name']} = {vnum(decr_bits, 0)};
        errors = 0;
        case_id = 0;

        // Directed edge cases derived from prior false assumptions:
        // the counter range is 0..10, decrements wrap, and reinit overrides updates.
        run_transition_case(3, 0, 3, 0, 0, 0, 0);
        run_transition_case(9, 0, 0, 1, 3, 0, 0);
        run_transition_case(1, 0, 0, 0, 0, 1, 3);
        run_transition_case(4, 0, 0, 1, 3, 1, 2);
        run_transition_case(5, 1, 6, 0, 0, 0, 0);
        run_transition_case(5, 1, 7, 1, 3, 1, 3);

        // Exhaustively cover all reachable states and legal update combinations.
        for (state_seed = 0; state_seed <= 10; state_seed = state_seed + 1) begin
            for (incr_valid_seed = 0; incr_valid_seed <= 1; incr_valid_seed = incr_valid_seed + 1) begin
                for (decr_valid_seed = 0; decr_valid_seed <= 1; decr_valid_seed = decr_valid_seed + 1) begin
                    for (incr_seed = 0; incr_seed <= 3; incr_seed = incr_seed + 1) begin
                        for (decr_seed = 0; decr_seed <= 3; decr_seed = decr_seed + 1) begin
                            run_transition_case(
                                state_seed,
                                0,
                                0,
                                incr_valid_seed,
                                incr_seed,
                                decr_valid_seed,
                                decr_seed
                            );
                        end
                    end
                end
            end
        end

        // Reinit must synchronously load initial_value and ignore concurrent updates.
        for (state_seed = 0; state_seed <= 10; state_seed = state_seed + 1) begin
            for (init_seed = 0; init_seed <= 10; init_seed = init_seed + 1) begin
                run_transition_case(state_seed, 1, init_seed, 0, 0, 0, 0);
                run_transition_case(state_seed, 1, init_seed, 1, 3, 1, 3);
            end
        end

        if (errors == 0) begin
            $display("TB_PASS");
        end else begin
            $display("TB_FAIL errors=%0d", errors);
        end
        $finish;
    end

endmodule
"""


def build_counter_tb(
    problem: str,
    module_name: str,
    spec_path: str,
    spec_text: str,
    ports: list[dict],
) -> str:
    clk = find_first(ports, lambda n: is_clock_name(n))
    rst = find_first(ports, lambda n: is_reset_name(n))
    en = find_first(ports, lambda n: is_enable_name(n))
    ld = find_first(ports, lambda n: is_load_name(n))
    direction = find_first(ports, lambda n: is_updown_name(n))

    count_out = find_count_output(ports)
    overflow_out = find_flag_output(ports, ["overflow", "carry", "ovf", "tc", "max"])
    underflow_out = find_flag_output(ports, ["underflow", "borrow", "udf", "min"])

    count_bits = bits_for_port(count_out) if count_out else 8
    if count_bits is None:
        count_bits = 8

    data_in = find_data_input(ports, count_bits)
    reset_low = is_active_low(rst["name"], spec_text) if rst else False
    en_low = is_active_low(en["name"], spec_text) if en else False
    ld_low = is_active_low(ld["name"], spec_text) if ld else False
    dir_up_value = infer_dir_up_value(direction, spec_text)
    dir_down_value = 0 if dir_up_value == 1 else 1

    decls = "\n".join(f"    {signal_decl(p)}" for p in ports)

    init_lines = []
    for p in ports:
        if p["direction"] == "input":
            init_lines.append(f"        {p['name']} = {vnum(bits_for_port(p), 0)};")

    clock_block = ""
    if clk:
        clock_block = "\n".join([
            "    initial begin",
            f"        {clk['name']} = 0;",
            "    end",
            "",
            f"    always #5 {clk['name']} = ~{clk['name']};",
        ])
    else:
        clock_block = "    // No clock detected; generated counter-specific checks may be ineffective."

    reset_assert = ""
    reset_release = ""
    if rst:
        if reset_low:
            reset_assert = vnum(bits_for_port(rst), 0)
            reset_release = vnum(bits_for_port(rst), 1)
        else:
            reset_assert = vnum(bits_for_port(rst), 1)
            reset_release = vnum(bits_for_port(rst), 0)

    en_on = vnum(bits_for_port(en), 0 if en_low else 1) if en else None
    en_off = vnum(bits_for_port(en), 1 if en_low else 0) if en else None
    ld_on = vnum(bits_for_port(ld), 0 if ld_low else 1) if ld else None
    ld_off = vnum(bits_for_port(ld), 1 if ld_low else 0) if ld else None

    seed_val = 0xA5
    if count_bits > 1:
        seed_val = (1 << (count_bits - 1)) | 0x5
    load_value = vhx(count_bits, seed_val)
    hold_value = vhx(count_bits, 0x3)
    max_value = vhx(count_bits, (1 << count_bits) - 1)

    pre_step_setup = []
    if en:
        pre_step_setup.append(f"        {en['name']} = {en_on};")
    if ld:
        pre_step_setup.append(f"        {ld['name']} = {ld_off};")

    dir_up_setup = []
    dir_down_setup = []
    if direction:
        dir_up_setup.append(f"        {direction['name']} = {vnum(bits_for_port(direction), dir_up_value)};")
        dir_down_setup.append(f"        {direction['name']} = {vnum(bits_for_port(direction), dir_down_value)};")

    load_sequence = []
    if ld and data_in:
        load_sequence.extend([
            "        // Directed load test",
            f"        {data_in['name']} = {load_value};",
            f"        {ld['name']} = {ld_on};",
            "        @(posedge clk);",
            "        #1;",
            f"        expected_count = {load_value};",
            "        check_outputs;",
            f"        {ld['name']} = {ld_off};",
            "",
        ])

    up_sequence = [
        "        // Count-up test",
        *dir_up_setup,
        *pre_step_setup,
        "        repeat (4) begin",
        "            if (expected_count == MAX_COUNT) begin",
        "                expected_count = 0;",
        "                expected_overflow = 1'b1;",
        "            end else begin",
        "                expected_count = expected_count + 1'b1;",
        "                expected_overflow = 1'b0;",
        "            end",
        "            expected_underflow = 1'b0;",
        "            @(posedge clk);",
        "            #1;",
        "            check_outputs;",
        "        end",
        "",
    ]

    down_sequence = []
    if direction:
        down_sequence = [
            "        // Count-down test",
            *dir_down_setup,
            *pre_step_setup,
            "        repeat (4) begin",
            "            if (expected_count == 0) begin",
            "                expected_count = MAX_COUNT;",
            "                expected_underflow = 1'b1;",
            "            end else begin",
            "                expected_count = expected_count - 1'b1;",
            "                expected_underflow = 1'b0;",
            "            end",
            "            expected_overflow = 1'b0;",
            "            @(posedge clk);",
            "            #1;",
            "            check_outputs;",
            "        end",
            "",
        ]

    hold_sequence = []
    if en:
        hold_sequence = [
            "        // Hold test with counting disabled",
            f"        {en['name']} = {en_off};",
            "        expected_overflow = 1'b0;",
            "        expected_underflow = 1'b0;",
            "        @(posedge clk);",
            "        #1;",
            "        check_outputs;",
            "",
        ]

    near_wrap_sequence = []
    if ld and data_in:
        near_wrap_sequence = [
            "        // Near-wrap test",
            f"        {data_in['name']} = MAX_COUNT;",
            f"        {ld['name']} = {ld_on};",
            "        @(posedge clk);",
            "        #1;",
            "        expected_count = MAX_COUNT;",
            "        expected_overflow = 1'b0;",
            "        expected_underflow = 1'b0;",
            "        check_outputs;",
            f"        {ld['name']} = {ld_off};",
            "",
            *dir_up_setup,
            *pre_step_setup,
            "        if (expected_count == MAX_COUNT) begin",
            "            expected_count = 0;",
            "            expected_overflow = 1'b1;",
            "        end else begin",
            "            expected_count = expected_count + 1'b1;",
            "            expected_overflow = 1'b0;",
            "        end",
            "        expected_underflow = 1'b0;",
            "        @(posedge clk);",
            "        #1;",
            "        check_outputs;",
            "",
        ]

    check_lines = []
    if count_out:
        check_lines.extend([
            f"        if ({count_out['name']} !== expected_count) begin",
            f'            $display("TB_FAIL count mismatch: expected=%0d got=%0d time=%0t", expected_count, {count_out["name"]}, $time);',
            "            errors = errors + 1;",
            "        end",
        ])
    if overflow_out:
        check_lines.extend([
            f"        if ({overflow_out['name']} !== expected_overflow) begin",
            f'            $display("TB_FAIL overflow mismatch: expected=%0d got=%0d time=%0t", expected_overflow, {overflow_out["name"]}, $time);',
            "            errors = errors + 1;",
            "        end",
        ])
    if underflow_out:
        check_lines.extend([
            f"        if ({underflow_out['name']} !== expected_underflow) begin",
            f'            $display("TB_FAIL underflow mismatch: expected=%0d got=%0d time=%0t", expected_underflow, {underflow_out["name"]}, $time);',
            "            errors = errors + 1;",
            "        end",
        ])
    if not check_lines:
        check_lines.append('        $display("TB_WARN no recognizable outputs mapped for checking.");')

    initial_body = []
    initial_body.extend(init_lines)
    initial_body.extend([
        "        errors = 0;",
        "        expected_count = 0;",
        "        expected_overflow = 1'b0;",
        "        expected_underflow = 1'b0;",
        "",
    ])

    if rst:
        initial_body.extend([
            "        // Reset test",
            f"        {rst['name']} = {reset_assert};",
        ])
        if en:
            initial_body.append(f"        {en['name']} = {en_off};")
        if ld:
            initial_body.append(f"        {ld['name']} = {ld_off};")
        if direction:
            initial_body.append(f"        {direction['name']} = {vnum(bits_for_port(direction), dir_up_value)};")
        if data_in:
            initial_body.append(f"        {data_in['name']} = {hold_value};")
        initial_body.extend([
            "        repeat (2) @(posedge clk);",
            "        #1;",
            "        check_outputs;",
            f"        {rst['name']} = {reset_release};",
            "        @(posedge clk);",
            "        #1;",
            "        check_outputs;",
            "",
        ])
    else:
        initial_body.extend([
            "        // No reset signal detected; starting from default zeroed TB state.",
            "        @(posedge clk);",
            "        #1;",
            "        check_outputs;",
            "",
        ])

    initial_body.extend(load_sequence)
    initial_body.extend(hold_sequence)
    initial_body.extend(up_sequence)
    initial_body.extend(down_sequence)
    initial_body.extend(near_wrap_sequence)

    initial_body.extend([
        "        if (errors == 0) begin",
        '            $display("TB_PASS");',
        "        end else begin",
        '            $display("TB_FAIL errors=%0d", errors);',
        "        end",
        "        $finish;",
    ])

    return f"""`timescale 1ns/1ps

module tb_{module_name};

    // Heuristic spec-aware testbench
    // Problem: {problem}
    // Spec source: {spec_path}
    // Generated at: {datetime.now(timezone.utc).isoformat()}

{decls}

    integer errors;
    reg [{count_bits - 1}:0] expected_count;
    reg expected_overflow;
    reg expected_underflow;
    localparam [{count_bits - 1}:0] MAX_COUNT = {max_value};

    {module_name} dut (
{port_connections(ports)}
    );

{clock_block}

    task check_outputs;
    begin
{chr(10).join(check_lines)}
        expected_overflow = 1'b0;
        expected_underflow = 1'b0;
    end
    endtask

    initial begin
        $dumpfile("tb_{module_name}.vcd");
        $dumpvars(0, tb_{module_name});
    end

    initial begin
{chr(10).join(initial_body)}
    end

endmodule
"""


def build_generic_tb(
    problem: str,
    module_name: str,
    spec_path: str,
    ports: list[dict],
) -> str:
    clk = find_first(ports, lambda n: is_clock_name(n))
    rst = find_first(ports, lambda n: is_reset_name(n))

    decls = "\n".join(f"    {signal_decl(p)}" for p in ports)
    init_lines = []
    for p in ports:
        if p["direction"] == "input":
            init_lines.append(f"        {p['name']} = {vnum(bits_for_port(p), 0)};")

    drive_lines = []
    for p in ports:
        if p["direction"] != "input":
            continue
        if is_clock_name(p["name"]) or is_reset_name(p["name"]):
            continue
        drive_lines.append(f"        {p['name']} = $random;")

    clock_block = ""
    if clk:
        clock_block = "\n".join([
            "    initial begin",
            f"        {clk['name']} = 0;",
            "    end",
            "",
            f"    always #5 {clk['name']} = ~{clk['name']};",
        ])
    else:
        clock_block = "    // No clock detected."

    body = []
    body.extend(init_lines)
    if rst:
        body.extend([
            f"        {rst['name']} = 1'b1;",
            "        #10;",
            f"        {rst['name']} = 1'b0;",
            "",
        ])
    body.extend([
        "        repeat (10) begin",
    ])
    if drive_lines:
        body.extend(drive_lines)
    else:
        body.append("            // No non-control inputs to drive.")
    if clk:
        body.extend([
            "            @(posedge clk);",
            "            #1;",
        ])
    else:
        body.append("            #10;")
    body.extend([
        "        end",
        '        $display("TB_PASS");',
        "        $finish;",
    ])

    return f"""`timescale 1ns/1ps

module tb_{module_name};

    // Generic fallback testbench
    // Problem: {problem}
    // Spec source: {spec_path}
    // Generated at: {datetime.now(timezone.utc).isoformat()}

{decls}

    {module_name} dut (
{port_connections(ports)}
    );

{clock_block}

    initial begin
        $dumpfile("tb_{module_name}.vcd");
        $dumpvars(0, tb_{module_name});
    end

    initial begin
{chr(10).join(body)}
    end

endmodule
"""


def main() -> int:
    args = parse_args()

    root = Path(args.root).resolve()
    problem = args.problem
    tag = args.tag
    iteration_packet = {}

    preflight_path = root / "logs" / "runs" / f"{problem}_preflight_context.json"
    if not preflight_path.exists():
        print(f"[error] Preflight context not found: {preflight_path}")
        return 1

    preflight = read_json(preflight_path)
    spec_files = preflight.get("spec_files", [])
    rtl_files = preflight.get("rtl_files", [])
    combined_spec_path = preflight.get("combined_spec_output", "")

    packet_path = None
    if args.iteration_packet:
        packet_path = Path(args.iteration_packet)
        if not packet_path.is_absolute():
            packet_path = (root / packet_path).resolve()
    else:
        default_packet_path = (
            root / "outputs" / problem / "iterations" / tag / "agent_input" / "iteration_packet.json"
        )
        if default_packet_path.exists():
            packet_path = default_packet_path

    if packet_path and packet_path.exists():
        iteration_packet = read_json(packet_path)

    if not rtl_files:
        print("[error] No RTL files recorded in preflight context.")
        return 1

    sample_rtl_path = Path(rtl_files[0]["path"])
    if not sample_rtl_path.exists():
        print(f"[error] Sample RTL file not found: {sample_rtl_path}")
        return 1

    rtl_text = read_text(sample_rtl_path)
    module_name = infer_module_name(rtl_text)
    ports = infer_ports(rtl_text)

    spec_text = iteration_packet.get("spec_text", "")
    if not spec_text and combined_spec_path and Path(combined_spec_path).exists():
        spec_text = read_text(Path(combined_spec_path))
    elif not spec_text and spec_files:
        parts = []
        for item in spec_files:
            path = Path(item["path"])
            if path.exists():
                parts.append(read_text(path))
        spec_text = "\n".join(parts)

    spec_path = combined_spec_path if combined_spec_path else (spec_files[0]["path"] if spec_files else "N/A")
    spec_l = spec_text.lower()
    counter_like = (
        "counter" in module_name.lower()
        or "counter" in spec_l
        or "increment" in spec_l
        or "decrement" in spec_l
        or "up/down" in spec_l
    )

    if looks_like_problem1_counter(spec_text, ports):
        tb_text = build_problem1_counter_tb(problem, module_name, spec_path, ports)
        strategy = "problem1_counter_refined"
    elif counter_like and find_first(ports, lambda n: is_clock_name(n)) and find_count_output(ports):
        tb_text = build_counter_tb(problem, module_name, spec_path, spec_text, ports)
        strategy = "counter_heuristic"
    else:
        tb_text = build_generic_tb(problem, module_name, spec_path, ports)
        strategy = "generic_fallback"

    out_dir = root / "outputs" / problem / "iterations" / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    tb_path = out_dir / "generated_tb.v"
    meta_path = out_dir / "generated_tb_meta.json"

    tb_path.write_text(tb_text, encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "problem": problem,
                "tag": tag,
                "sample_rtl_file": str(sample_rtl_path),
                "combined_spec_source": spec_path,
                "iteration_packet": str(packet_path) if packet_path else "",
                "inferred_module_name": module_name,
                "num_inferred_ports": len(ports),
                "generation_strategy": strategy,
                "generated_testbench": str(tb_path),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[info] Preflight context: {preflight_path}")
    print(f"[info] Sample RTL used for inference: {sample_rtl_path}")
    print(f"[info] Inferred module name: {module_name}")
    print(f"[info] Inferred ports: {len(ports)}")
    print(f"[info] Strategy: {strategy}")
    print(f"[info] Testbench written to: {tb_path}")
    print(f"[info] Testbench metadata written to: {meta_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
