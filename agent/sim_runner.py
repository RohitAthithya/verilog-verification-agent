import subprocess
import tempfile
from pathlib import Path

from agent.config import IVERILOG_BIN, VVP_BIN


def _run_cmd(cmd, cwd=None):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "cmd": cmd,
    }


def run_simulation(testbench_text: str, rtl_files: list) -> dict:
    results = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        tb_path = tmpdir / "generated_tb.v"
        tb_path.write_text(testbench_text, encoding="utf-8")

        for rtl in rtl_files:
            output_file = tmpdir / f"{Path(rtl['filename']).stem}.out"

            compile_cmd = [
                IVERILOG_BIN,
                "-o",
                str(output_file),
                str(tb_path),
                rtl["path"],
            ]
            compile_result = _run_cmd(compile_cmd)

            if compile_result["returncode"] != 0:
                results[rtl["filename"]] = {
                    "compiled": False,
                    "passed": False,
                    "compile_result": compile_result,
                    "run_result": None,
                }
                continue

            run_cmd = [VVP_BIN, str(output_file)]
            run_result = _run_cmd(run_cmd)

            stdout = run_result["stdout"].lower()
            stderr = run_result["stderr"].lower()

            passed = (
                run_result["returncode"] == 0
                and "fail" not in stdout
                and "error" not in stdout
                and "fail" not in stderr
                and "error" not in stderr
            )

            results[rtl["filename"]] = {
                "compiled": True,
                "passed": passed,
                "compile_result": compile_result,
                "run_result": run_result,
            }

    return results