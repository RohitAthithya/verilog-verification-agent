from pathlib import Path
import re


def _extract_module_name(verilog_text: str):
    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)", verilog_text)
    return match.group(1) if match else None


def _extract_port_names(verilog_text: str):
    matches = re.findall(
        r"\b(input|output|inout)\b(?:\s+(?:reg|wire|logic))?(?:\s*\[[^\]]+\])?\s+([A-Za-z_][A-Za-z0-9_]*)",
        verilog_text,
    )
    return [{"direction": d, "name": n} for d, n in matches]


def read_rtl_files(rtl_dir: str) -> list:
    rtl_path = Path(rtl_dir)

    if not rtl_path.exists():
        raise FileNotFoundError(f"RTL directory not found: {rtl_dir}")

    rtl_files = []
    for file_path in sorted(rtl_path.glob("*.v")):
        source = file_path.read_text(encoding="utf-8", errors="ignore")

        rtl_files.append(
            {
                "path": str(file_path),
                "filename": file_path.name,
                "module_name": _extract_module_name(source),
                "ports": _extract_port_names(source),
                "source": source,
            }
        )

    if not rtl_files:
        raise ValueError(f"No Verilog files found in: {rtl_dir}")

    return rtl_files