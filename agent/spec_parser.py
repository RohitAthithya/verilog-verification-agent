import re

# need not be  a fixed format, so the spec can go directly to the LLM
def parse_spec(spec_text: str) -> dict:
    text = spec_text.strip()

    ports = []
    for line in text.splitlines():
        line = line.strip()
        match = re.search(
            r"(input|output|inout)\s+([A-Za-z_][A-Za-z0-9_]*)",
            line,
            re.IGNORECASE,
        )
        if match:
            ports.append(
                {
                    "direction": match.group(1).lower(),
                    "name": match.group(2),
                }
            )

    has_clock = bool(re.search(r"\b(clk|clock)\b", text, re.IGNORECASE))
    has_reset = bool(re.search(r"\b(reset|rst)\b", text, re.IGNORECASE))
    likely_sequential = bool(
        re.search(r"\b(cycle|clock|posedge|negedge|state|reset)\b", text, re.IGNORECASE)
    )

    return {
        "raw_text": text,
        "ports": ports,
        "has_clock": has_clock,
        "has_reset": has_reset,
        "likely_sequential": likely_sequential,
    }