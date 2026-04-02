import re
import torch

from agent.config import (
    PROMPTS_ROOT,
    MAX_NEW_TOKENS,
    TEMPERATURE,
    TOP_P,
    DO_SAMPLE,
)


def _load_prompt_template(filename: str) -> str:
    prompt_path = PROMPTS_ROOT / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def _format_rtl_candidates_for_prompt(rtl_files: list) -> str:
    blocks = []
    for idx, rtl in enumerate(rtl_files, start=1):
        block = f"""
Candidate RTL {idx}
Filename: {rtl['filename']}
Module name: {rtl.get('module_name')}
Ports: {rtl.get('ports')}

Verilog source:
{rtl['source']}
""".strip()
        blocks.append(block)

    return "\n\n" + ("\n\n" + ("-" * 80) + "\n\n").join(blocks)


def build_generation_prompt(
    spec_text: str,
    parsed_spec: dict,
    rtl_files: list,
    previous_results=None,
    previous_analysis=None,
):
    template = _load_prompt_template("generate_tb_prompt.txt")

    rtl_block = _format_rtl_candidates_for_prompt(rtl_files)

    previous_results_str = "None" if previous_results is None else str(previous_results)
    previous_analysis_str = "None" if previous_analysis is None else str(previous_analysis)

    prompt = template.format(
        spec_text=spec_text,
        parsed_spec=parsed_spec,
        rtl_candidates=rtl_block,
        previous_results=previous_results_str,
        previous_analysis=previous_analysis_str,
    )

    return prompt


def _extract_verilog_from_response(response_text: str) -> str:
    fenced = re.findall(
        r"```(?:verilog)?\s*(.*?)```",
        response_text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        return fenced[0].strip()
    return response_text.strip()


def _generate_text(tokenizer, model, prompt: str) -> str:
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            do_sample=DO_SAMPLE,
            pad_token_id=tokenizer.eos_token_id,
        )

    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)

    if decoded.startswith(prompt):
        return decoded[len(prompt):].strip()

    return decoded.strip()


def generate_testbench(
    spec_text: str,
    parsed_spec: dict,
    rtl_files: list,
    tokenizer,
    model,
    previous_results=None,
    previous_analysis=None,
):
    prompt = build_generation_prompt(
        spec_text=spec_text,
        parsed_spec=parsed_spec,
        rtl_files=rtl_files,
        previous_results=previous_results,
        previous_analysis=previous_analysis,
    )

    raw_output = _generate_text(tokenizer, model, prompt)
    verilog_tb = _extract_verilog_from_response(raw_output)

    if "`timescale" not in verilog_tb:
        verilog_tb = "`timescale 1ns/1ps\n\n" + verilog_tb

    return verilog_tb, prompt, raw_output