import json
from datetime import datetime
from pathlib import Path

from agent.config import (
    DATA_ROOT,
    RUNS_ROOT,
    DEFAULT_PROBLEM,
    MAX_ITERATIONS,
    TB_OUTPUT_NAME,
    SUMMARY_FILE_NAME,
    ACTIVE_MODEL_LABEL,
)
from agent.model_loader import load_model
from agent.spec_parser import parse_spec
from agent.rtl_reader import read_rtl_files
from agent.tb_generator import generate_testbench
from agent.sim_runner import run_simulation
from agent.result_analyzer import analyze_results


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str):
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main(problem_name: str = DEFAULT_PROBLEM):
    problem_dir = DATA_ROOT / problem_name
    spec_path = problem_dir / "spec" / "spec.txt"
    rtl_dir = problem_dir / "rtl"

    if not spec_path.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")
    if not rtl_dir.exists():
        raise FileNotFoundError(f"RTL directory not found: {rtl_dir}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_ROOT / problem_name / run_id
    ensure_dir(run_dir)

    print(f"[INFO] Loading model: {ACTIVE_MODEL_LABEL}")
    tokenizer, model = load_model()

    print(f"[INFO] Reading spec: {spec_path}")
    spec_text = spec_path.read_text(encoding="utf-8", errors="ignore")

    print(f"[INFO] Reading RTL candidates from: {rtl_dir}")
    rtl_files = read_rtl_files(str(rtl_dir))

    parsed_spec = parse_spec(spec_text)
    write_json(run_dir / "parsed_spec.json", parsed_spec)

    previous_results = None
    previous_analysis = None
    best_testbench = None
    best_analysis = None

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"[INFO] Iteration {iteration}/{MAX_ITERATIONS}")

        testbench_text, prompt_text, raw_model_output = generate_testbench(
            spec_text=spec_text,
            parsed_spec=parsed_spec,
            rtl_files=rtl_files,
            tokenizer=tokenizer,
            model=model,
            previous_results=previous_results,
            previous_analysis=previous_analysis,
        )

        iter_dir = run_dir / f"iter_{iteration:02d}"
        ensure_dir(iter_dir)

        write_text(iter_dir / TB_OUTPUT_NAME, testbench_text)
        write_text(iter_dir / "prompt.txt", prompt_text)
        write_text(iter_dir / "raw_model_output.txt", raw_model_output)

        sim_results = run_simulation(testbench_text, rtl_files)
        analysis = analyze_results(sim_results)

        write_json(iter_dir / "sim_results.json", sim_results)
        write_json(iter_dir / "analysis.json", analysis)

        best_testbench = testbench_text
        best_analysis = analysis

        print(f"[INFO] {analysis['summary']}")

        if analysis["good_enough"]:
            print("[INFO] Stopping early: exactly one RTL passed.")
            break

        previous_results = sim_results
        previous_analysis = analysis

    summary = {
        "problem": problem_name,
        "model": ACTIVE_MODEL_LABEL,
        "run_id": run_id,
        "final_analysis": best_analysis,
    }
    write_json(run_dir / SUMMARY_FILE_NAME, summary)

    final_tb_path = run_dir / "final_generated_tb.v"
    write_text(final_tb_path, best_testbench if best_testbench else "")

    print(f"[INFO] Run complete. Outputs saved in: {run_dir}")


if __name__ == "__main__":
    main()